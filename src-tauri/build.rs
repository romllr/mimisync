use std::{fs, io, path::Path};
fn append(
    tree: &mut tar::Builder<flate2::write::GzEncoder<fs::File>>,
    root: &Path,
    directory: &Path,
) -> io::Result<()> {
    for entry in fs::read_dir(directory)? {
        let path = entry?.path();
        if path.is_dir() {
            let name = path.file_name().unwrap().to_string_lossy();
            if !name.starts_with('.') && name != "__pycache__" && !name.ends_with(".egg-info") {
                append(tree, root, &path)?;
            }
        } else if matches!(
            path.extension().and_then(|e| e.to_str()),
            Some("py" | "toml" | "lock" | "md")
        ) {
            tree.append_path_with_name(&path, path.strip_prefix(root).unwrap())?;
        }
    }
    Ok(())
}
fn main() {
    println!("cargo:rerun-if-changed=../backend");
    println!("cargo:rerun-if-changed=../runtime/bootstrap.sh");
    let out = std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap());
    let output = fs::File::create(out.join("backend.tar.gz")).unwrap();
    let encoder = flate2::write::GzEncoder::new(output, flate2::Compression::default());
    let mut tree = tar::Builder::new(encoder);
    append(&mut tree, Path::new(".."), Path::new("../backend")).unwrap();
    tree.append_path_with_name("../runtime/bootstrap.sh", "bootstrap.sh")
        .unwrap();
    tree.into_inner().unwrap().finish().unwrap();
    tauri_build::build()
}
