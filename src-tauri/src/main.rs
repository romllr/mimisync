#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod setup;
mod setup_protocol;
#[cfg(target_os = "windows")]
mod windows_setup;
use futures_util::StreamExt;
use serde::Serialize;
use std::{
    io::Write,
    process::{Child, ChildStdin, Command, Stdio},
    sync::Mutex,
};
use tauri::State;
use tokio::io::AsyncWriteExt;

struct Backend {
    child: Mutex<Option<Child>>,
    input: Mutex<Option<ChildStdin>>,
    token: String,
    client: reqwest::Client,
    root: std::path::PathBuf,
}
impl Backend {
    fn shutdown(&self) {
        if let Ok(mut input) = self.input.lock() {
            input.take();
        }
        if let Ok(mut child) = self.child.lock() {
            if let Some(mut p) = child.take() {
                // Give the Python lifespan handler time to cancel its process group.
                for _ in 0..50 {
                    if matches!(p.try_wait(), Ok(Some(_))) {
                        return;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(100));
                }
                let _ = p.kill();
                let _ = p.wait();
            }
        }
    }
}
impl Drop for Backend {
    fn drop(&mut self) {
        self.shutdown();
    }
}
#[derive(Serialize)]
struct Connection {
    url: String,
    token: String,
}
const BASE: &str = "http://127.0.0.1:47831";
fn route(path: &str) -> Result<String, String> {
    if !path.starts_with('/')
        || path.contains("..")
        || path.contains('?')
        || path.contains('#')
        || path.contains('\\')
    {
        return Err("Rota inválida".into());
    }
    Ok(format!("{BASE}{path}"))
}
async fn response_json(response: reqwest::Response) -> Result<serde_json::Value, String> {
    let status = response.status();
    let value: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(value
            .get("detail")
            .map(|v| v.to_string())
            .unwrap_or_else(|| status.to_string()));
    }
    Ok(value)
}
#[tauri::command]
fn connection(state: State<Backend>) -> Connection {
    Connection {
        url: BASE.into(),
        token: state.token.clone(),
    }
}
#[tauri::command]
async fn api(
    state: State<'_, Backend>,
    method: String,
    path: String,
    body: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    let method = match method.as_str() {
        "GET" => reqwest::Method::GET,
        "POST" => reqwest::Method::POST,
        _ => return Err("Método inválido".into()),
    };
    let mut request = state
        .client
        .request(method, route(&path)?)
        .bearer_auth(&state.token);
    if let Some(value) = body {
        request = request.json(&value);
    }
    response_json(
        request
            .send()
            .await
            .map_err(|e| format!("Backend indisponível: {e}"))?,
    )
    .await
}
#[tauri::command]
async fn import_media(
    state: State<'_, Backend>,
    path: String,
) -> Result<serde_json::Value, String> {
    let file_path = std::path::Path::new(&path);
    let name = file_path
        .file_name()
        .ok_or("Nome inválido")?
        .to_string_lossy()
        .to_string();
    let ext = file_path
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();
    if !["mp4", "mov", "mp3", "wav"].contains(&ext.as_str()) {
        return Err("Formato inválido".into());
    }
    let file = tokio::fs::File::open(file_path)
        .await
        .map_err(|e| e.to_string())?;
    let size = file.metadata().await.map_err(|e| e.to_string())?.len();
    let stream = tokio_util::io::ReaderStream::new(file);
    let part =
        reqwest::multipart::Part::stream_with_length(reqwest::Body::wrap_stream(stream), size)
            .file_name(name);
    let response = state
        .client
        .post(format!("{BASE}/media"))
        .bearer_auth(&state.token)
        .multipart(reqwest::multipart::Form::new().part("file", part))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    response_json(response).await
}
#[tauri::command]
async fn export_result(state: State<'_, Backend>, id: String, path: String) -> Result<(), String> {
    if id.len() != 32 || !id.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("ID inválido".into());
    }
    let response = state
        .client
        .get(format!("{BASE}/jobs/{id}/result"))
        .bearer_auth(&state.token)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    if !response.status().is_success() {
        return Err("Resultado indisponível".into());
    }
    let target = std::path::PathBuf::from(path);
    let temporary = target.with_extension(format!("{}.partial", uuid::Uuid::new_v4()));
    let operation = async {
        let mut file = tokio::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .await?;
        let mut chunks = response.bytes_stream();
        while let Some(chunk) = chunks.next().await {
            file.write_all(&chunk.map_err(std::io::Error::other)?)
                .await?;
        }
        file.sync_all().await?;
        drop(file);
        tokio::fs::rename(&temporary, &target).await
    }
    .await;
    if operation.is_err() {
        let _ = tokio::fs::remove_file(&temporary).await;
    }
    operation.map_err(|e| e.to_string())
}
fn backend(root: std::path::PathBuf) -> Result<Backend, String> {
    Ok(Backend {
        child: Mutex::new(None),
        input: Mutex::new(None),
        root,
        token: format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        ),
        client: reqwest::Client::builder()
            .no_proxy()
            .connect_timeout(std::time::Duration::from_secs(2))
            .build()
            .map_err(|e| e.to_string())?,
    })
}
#[tauri::command]
async fn backend_start(state: State<'_, Backend>) -> Result<(), String> {
    {
        let mut guard = state.child.lock().map_err(|e| e.to_string())?;
        if guard
            .as_mut()
            .is_some_and(|p| p.try_wait().is_ok_and(|s| s.is_some()))
        {
            guard.take();
        }
        if guard.is_none() {
            let mut cmd;
            if cfg!(target_os = "windows") {
                cmd = setup::command("wsl.exe");
                if let Ok(project) = std::env::var("MIMISYNC_WSL_PROJECT") {
                    cmd.args([
                        "--cd",
                        &format!("{project}/backend"),
                        "--",
                        "../.venv/bin/python",
                        "-m",
                        "mimisync",
                        "--token-stdin",
                    ]);
                } else {
                    cmd.args([
                        "--distribution",
                        setup::DISTRO,
                        "--user",
                        "mimisync",
                        "--cd",
                        setup::WORK,
                        "--",
                        setup::RUNTIME,
                        "-m",
                        "mimisync",
                        "--token-stdin",
                    ]);
                }
            } else {
                let project = std::env::var("MIMISYNC_PROJECT")
                    .map(std::path::PathBuf::from)
                    .unwrap_or_else(|_| {
                        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                            .parent()
                            .unwrap()
                            .to_owned()
                    });
                cmd = Command::new(project.join(".venv/bin/python"));
                cmd.current_dir(project.join("backend"))
                    .args(["-m", "mimisync", "--token-stdin"]);
            }
            std::fs::create_dir_all(&state.root).map_err(|e| e.to_string())?;
            let log = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(state.root.join("backend.log"))
                .map_err(|e| e.to_string())?;
            let mut child = cmd
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::from(log))
                .spawn()
                .map_err(|e| format!("Não foi possível iniciar o processador local: {e}"))?;
            let mut input = child
                .stdin
                .take()
                .ok_or("Não foi possível conectar ao processador")?;
            if let Err(error) = writeln!(input, "{}", state.token) {
                let _ = child.kill();
                return Err(error.to_string());
            }
            *state.input.lock().map_err(|e| e.to_string())? = Some(input);
            *guard = Some(child);
        }
    }
    for _ in 0..80 {
        if let Ok(response) = state
            .client
            .get(format!("{BASE}/health"))
            .bearer_auth(&state.token)
            .send()
            .await
        {
            if response.status().is_success() {
                return Ok(());
            }
        }
        let ended = state
            .child
            .lock()
            .map_err(|e| e.to_string())?
            .as_mut()
            .is_some_and(|p| p.try_wait().is_ok_and(|s| s.is_some()));
        if ended {
            break;
        }
        tokio::time::sleep(std::time::Duration::from_millis(300)).await;
    }
    let details = std::fs::read_to_string(state.root.join("backend.log")).unwrap_or_default();
    let lines: Vec<&str> = details.lines().rev().take(12).collect();
    Err(format!(
        "O processador local não iniciou. Tente preparar os componentes novamente.\n{}",
        lines.into_iter().rev().collect::<Vec<_>>().join("\n")
    ))
}
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            use tauri::Manager;
            let root = app.path().app_local_data_dir()?;
            app.manage(setup::Installer::new(root.clone()));
            let state = backend(root).map_err(std::io::Error::other)?;
            app.manage(state);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            setup::setup_status,
            setup::setup_inspect,
            setup::setup_prepare,
            setup::setup_windows,
            backend_start,
            connection,
            api,
            import_media,
            export_result
        ])
        .build(tauri::generate_context!())
        .expect("Falha ao iniciar Mimisync")
        .run(|handle, event| {
            if let tauri::RunEvent::Exit = event {
                use tauri::Manager;
                if let Some(state) = handle.try_state::<Backend>() {
                    state.shutdown();
                }
            }
        });
}
