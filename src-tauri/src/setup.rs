use crate::setup_protocol::{checksum, decode, read_log_stream};
use futures_util::StreamExt;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    time::Duration,
};
use tauri::State;
use tokio::io::AsyncWriteExt;

pub const DISTRO: &str = "Mimisync-Ubuntu";
pub const VERSION: &str = "0.2.0";
pub const RUNTIME: &str = "/opt/mimisync/controller/bin/python";
pub const WORK: &str = "/opt/mimisync/releases/0.2.0/backend";
const IMAGE: &str = "ubuntu-jammy-wsl-amd64-ubuntu22.04lts.rootfs.tar.gz";
const BASE: &str = "https://cloud-images.ubuntu.com/wsl/jammy/current";

#[derive(Clone, Serialize)]
pub struct Snapshot {
    pub busy: bool,
    pub phase: String,
    pub wsl_available: bool,
    pub runtime_installed: bool,
    pub gpu: Option<String>,
    pub error: Option<String>,
    pub logs: Vec<String>,
    pub downloaded: u64,
    pub total: Option<u64>,
}
#[derive(Clone)]
pub struct Installer {
    pub state: Arc<Mutex<Snapshot>>,
    pub root: PathBuf,
}
impl Installer {
    pub fn new(root: PathBuf) -> Self {
        Self {
            root,
            state: Arc::new(Mutex::new(Snapshot {
                busy: false,
                phase: "checking".into(),
                wsl_available: false,
                runtime_installed: false,
                gpu: None,
                error: None,
                logs: vec![],
                downloaded: 0,
                total: None,
            })),
        }
    }
    fn update(&self, action: impl FnOnce(&mut Snapshot)) {
        if let Ok(mut state) = self.state.lock() {
            action(&mut state);
        }
    }
    fn log(&self, text: impl Into<String>) {
        let text = text.into();
        self.update(|state| {
            state.logs.push(text);
            if state.logs.len() > 400 {
                state.logs.remove(0);
            }
        });
    }
    pub fn begin(&self) -> Result<(), String> {
        let mut state = self.state.lock().map_err(|e| e.to_string())?;
        if state.busy {
            return Err("Já existe uma preparação em andamento".into());
        }
        state.busy = true;
        state.error = None;
        Ok(())
    }
    fn finish(&self, result: Result<(), String>) {
        self.update(|state| {
            state.busy = false;
            if let Err(error) = result {
                state.error = Some(error);
                state.phase = "error".into();
            }
        });
    }
    pub fn inspect(&self) -> Result<(), String> {
        if !cfg!(target_os = "windows") {
            self.update(|s| {
                s.wsl_available = true;
                s.runtime_installed = true;
                s.phase = "development".into();
            });
            return Ok(());
        }
        self.update(|s| s.phase = "checking".into());
        let mut nvidia = command("nvidia-smi");
        nvidia.args(["--query-gpu=name,memory.total", "--format=csv,noheader"]);
        if let Ok(output) = nvidia.output() {
            if output.status.success() {
                self.update(|s| s.gpu = Some(decode(&output.stdout).trim().to_owned()));
            }
        }
        let available = command("wsl.exe")
            .arg("--status")
            .output()
            .is_ok_and(|p| p.status.success());
        let mut installed = false;
        if available {
            installed = wsl("root")
                .args([
                    "test",
                    "-f",
                    "/opt/mimisync/releases/0.2.0/installed-version",
                ])
                .output()
                .is_ok_and(|p| p.status.success());
        }
        self.update(|s| {
            s.wsl_available = available;
            s.runtime_installed = installed;
            s.phase = if installed {
                "ready"
            } else if available {
                "needs_runtime"
            } else {
                "needs_windows"
            }
            .into();
        });
        Ok(())
    }
    async fn download_image(&self) -> Result<PathBuf, String> {
        self.update(|s| {
            s.phase = "download".into();
            s.downloaded = 0;
            s.total = None;
        });
        let client = reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(30))
            .build()
            .map_err(|e| e.to_string())?;
        let response = client
            .get(format!("{BASE}/SHA256SUMS"))
            .send()
            .await
            .map_err(|e| format!("Não foi possível consultar a checksum oficial do Ubuntu: {e}"))?
            .error_for_status()
            .map_err(|e| e.to_string())?;
        let sums = response.text().await.map_err(|e| e.to_string())?;
        let expected = checksum(&sums, IMAGE)?;
        fs::create_dir_all(&self.root).map_err(|e| e.to_string())?;
        let target = self.root.join(IMAGE);
        if target.is_file() {
            let file = target.clone();
            let digest = tauri::async_runtime::spawn_blocking(move || hash_file(&file))
                .await
                .map_err(|e| e.to_string())??;
            if digest == expected {
                self.log("Imagem Ubuntu já verificada.");
                return Ok(target);
            }
        }
        self.log("Baixando o ambiente oficial Ubuntu. Seus vídeos não são enviados.");
        let response = client
            .get(format!("{BASE}/{IMAGE}"))
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?;
        self.update(|s| s.total = response.content_length());
        let temporary = target.with_extension("partial");
        let mut file = tokio::fs::File::create(&temporary)
            .await
            .map_err(|e| e.to_string())?;
        let mut stream = response.bytes_stream();
        let mut hasher = Sha256::new();
        while let Some(bytes) = stream.next().await {
            let bytes = bytes.map_err(|e| format!("Download interrompido: {e}"))?;
            file.write_all(&bytes).await.map_err(|e| e.to_string())?;
            hasher.update(&bytes);
            self.update(|s| s.downloaded += bytes.len() as u64);
        }
        file.sync_all().await.map_err(|e| e.to_string())?;
        drop(file);
        let actual = format!("{:x}", hasher.finalize());
        if actual != expected {
            let _ = tokio::fs::remove_file(&temporary).await;
            return Err("A imagem Ubuntu não passou na verificação SHA-256. Tente novamente; o arquivo foi descartado.".into());
        }
        tokio::fs::rename(&temporary, &target)
            .await
            .map_err(|e| e.to_string())?;
        self.log("SHA-256 do Ubuntu conferido com a fonte oficial.");
        Ok(target)
    }
    async fn prepare(&self) -> Result<(), String> {
        if !cfg!(target_os = "windows") {
            return Err("A preparação automática é destinada ao Windows 11 x64.".into());
        }
        if !self.state.lock().map_err(|e| e.to_string())?.wsl_available {
            return Err(
                "Primeiro habilite os componentes do Windows e reinicie se o sistema pedir.".into(),
            );
        }
        let exists = tauri::async_runtime::spawn_blocking(move || {
            let output = command("wsl.exe")
                .args(["--list", "--quiet"])
                .output()
                .map_err(|e| e.to_string())?;
            if !output.status.success() {
                return Err(decode(&output.stderr));
            }
            Ok(decode(&output.stdout)
                .lines()
                .any(|line| line.trim() == DISTRO))
        })
        .await
        .map_err(|e| e.to_string())??;
        if !exists {
            let image = self.download_image().await?;
            let root = self.root.join("ubuntu");
            fs::create_dir_all(&root).map_err(|e| e.to_string())?;
            self.update(|s| s.phase = "import".into());
            self.log("Criando um ambiente exclusivo do Mimisync...");
            let me = self.clone();
            tauri::async_runtime::spawn_blocking(move || {
                let mut cmd = command("wsl.exe");
                cmd.arg("--import")
                    .arg(DISTRO)
                    .arg(root)
                    .arg(image)
                    .args(["--version", "2"]);
                me.run(cmd)
            })
            .await
            .map_err(|e| e.to_string())??;
        }
        self.update(|s| s.phase = "install".into());
        let me = self.clone();
        tauri::async_runtime::spawn_blocking(move || me.install_runtime())
            .await
            .map_err(|e| e.to_string())??;
        self.inspect()?;
        if !self
            .state
            .lock()
            .map_err(|e| e.to_string())?
            .runtime_installed
        {
            return Err(
                "A preparação não foi confirmada. Consulte os detalhes e tente novamente.".into(),
            );
        }
        Ok(())
    }
    fn install_runtime(&self) -> Result<(), String> {
        let payload = self.root.join(format!("runtime-{VERSION}"));
        fs::create_dir_all(&payload).map_err(|e| e.to_string())?;
        let archive = include_bytes!(concat!(env!("OUT_DIR"), "/backend.tar.gz"));
        let decoder = flate2::read::GzDecoder::new(&archive[..]);
        tar::Archive::new(decoder)
            .unpack(&payload)
            .map_err(|e| e.to_string())?;
        let mut convert = wsl("root");
        convert.args(["wslpath", "-a", "-u"]).arg(&payload);
        let output = convert.output().map_err(|e| e.to_string())?;
        if !output.status.success() {
            return Err(decode(&output.stderr));
        }
        let linux = decode(&output.stdout).trim().to_owned();
        if !linux.starts_with('/') || linux.contains('\n') {
            return Err("Caminho do ambiente não reconhecido pelo Windows.".into());
        }
        let mut bootstrap = wsl("root");
        bootstrap
            .arg("bash")
            .arg(format!("{linux}/bootstrap.sh"))
            .arg(linux)
            .arg(VERSION);
        self.run(bootstrap)?;
        self.log("Verificando GPU e iniciando os componentes locais...");
        Ok(())
    }
    fn run(&self, mut cmd: Command) -> Result<(), String> {
        let mut child = cmd
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;
        let tail = Arc::new(Mutex::new(Vec::<String>::new()));
        let emit = {
            let me = self.clone();
            let tail = tail.clone();
            move |line: String| {
                me.log(line.clone());
                if let Ok(mut lines) = tail.lock() {
                    lines.push(line);
                    if lines.len() > 32 {
                        lines.remove(0);
                    }
                }
            }
        };
        let error = child.stderr.take().unwrap();
        let stderr_emit = emit.clone();
        let reader = std::thread::spawn(move || read_log_stream(error, stderr_emit));
        let stdout_result = read_log_stream(child.stdout.take().unwrap(), emit);
        let status = child.wait().map_err(|e| e.to_string())?;
        let stderr_result = reader
            .join()
            .map_err(|_| "Falha ao coletar a saída da instalação.".to_owned())?;
        if !status.success() {
            let code = status
                .code()
                .map(|c| format!("{c} / 0x{:08X}", c as u32))
                .unwrap_or_else(|| "indisponível".into());
            let details = tail
                .lock()
                .map(|lines| lines.join("\n"))
                .unwrap_or_default();
            return Err(format!("A instalação parou (código {code}).\n{details}"));
        }
        stdout_result.map_err(|e| format!("Não foi possível ler a saída da instalação: {e}"))?;
        stderr_result.map_err(|e| format!("Não foi possível ler os erros da instalação: {e}"))?;
        Ok(())
    }
}

pub fn command(program: &str) -> Command {
    let mut cmd = Command::new(program);
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }
    cmd
}
pub fn wsl(user: &str) -> Command {
    let mut cmd = command("wsl.exe");
    cmd.args(["--distribution", DISTRO, "--user", user, "--"]);
    cmd
}
fn hash_file(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| e.to_string())?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 1024 * 1024];
    loop {
        let n = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

#[tauri::command]
pub fn setup_status(state: State<Installer>) -> Result<Snapshot, String> {
    state
        .state
        .lock()
        .map(|s| s.clone())
        .map_err(|e| e.to_string())
}
#[tauri::command]
pub async fn setup_inspect(state: State<'_, Installer>) -> Result<(), String> {
    let me = state.inner().clone();
    me.begin()?;
    tauri::async_runtime::spawn_blocking(move || {
        let result = me.inspect();
        me.finish(result);
    })
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}
#[tauri::command]
pub fn setup_prepare(state: State<Installer>) -> Result<(), String> {
    let me = state.inner().clone();
    me.begin()?;
    tauri::async_runtime::spawn(async move {
        let result = me.prepare().await;
        me.finish(result);
    });
    Ok(())
}
#[tauri::command]
pub fn setup_windows(state: State<Installer>) -> Result<(), String> {
    if !cfg!(target_os = "windows") {
        return Err("Disponível apenas no Windows 11.".into());
    }
    let me = state.inner().clone();
    me.begin()?;
    me.update(|s| s.phase = "windows".into());
    std::thread::spawn(move || {
        #[cfg(target_os = "windows")]
        let result = crate::windows_setup::install_wsl();
        #[cfg(not(target_os = "windows"))]
        let result: Result<(), String> = Err("Disponível apenas no Windows 11.".into());
        if result.is_ok() {
            me.update(|s| s.phase = "restart".into());
            me.log("Se o Windows solicitou reinicialização, reinicie e abra o Mimisync novamente.");
        }
        me.finish(result);
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wsl_utf16_output() {
        let data: Vec<u8> = "Mimisync-Ubuntu\r\n"
            .encode_utf16()
            .flat_map(u16::to_le_bytes)
            .collect();
        assert_eq!(decode(&data).trim(), DISTRO);
    }
    #[test]
    fn checksum_exact_name() {
        let hash = "a".repeat(64);
        assert_eq!(
            checksum(&format!("{hash} *{IMAGE}\n"), IMAGE).unwrap(),
            hash
        );
        assert!(checksum("bad *wrong.tar.gz", IMAGE).is_err());
        assert!(checksum(&format!("{hash} *wrong.tar.gz"), IMAGE).is_err());
    }
    #[test]
    fn embedded_backend_is_complete() {
        let bytes = include_bytes!(concat!(env!("OUT_DIR"), "/backend.tar.gz"));
        let mut archive = tar::Archive::new(flate2::read::GzDecoder::new(&bytes[..]));
        let names: Vec<String> = archive
            .entries()
            .unwrap()
            .map(|e| e.unwrap().path().unwrap().to_string_lossy().into_owned())
            .collect();
        assert!(names.iter().any(|n| n == "backend/mimisync/__main__.py"));
        assert!(names.iter().any(|n| n == "bootstrap.sh"));
        assert!(!names
            .iter()
            .any(|n| n.contains("__pycache__") || n.contains("egg-info")));
    }
}
