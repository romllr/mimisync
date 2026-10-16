"""Package an existing Windows release binary and its Python source backend.

Does not bundle model weights, Python environments or a WSL distribution.
"""

import argparse
import hashlib
import re
import struct
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--exe",
    type=Path,
    default=ROOT / "src-tauri/target/release/mimisync.exe",
)
parser.add_argument("--output", type=Path, default=ROOT / "releases")
parser.add_argument("--cargo-registry", type=Path)
parser.add_argument("--name", default="Mimisync-0.2.0-preview2-windows-x64-portable")
args = parser.parse_args()
if not args.exe.is_file() or args.exe.read_bytes()[:2] != b"MZ":
    raise SystemExit("A Windows PE release executable is required.")
args.output.mkdir(parents=True, exist_ok=True)
name = args.name
if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
    raise SystemExit("A simple archive name is required.")


def imported_dlls(path):
    """Read the PE import table without executing the application."""
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE signature")
    sections, optional_size = struct.unpack_from("<H12xH", data, pe + 6)
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic not in (0x10B, 0x20B):
        raise ValueError("Unsupported PE optional header")
    directories = optional + (112 if magic == 0x20B else 96)
    import_rva = struct.unpack_from("<I", data, directories + 8)[0]
    table = optional + optional_size

    def offset(rva):
        for i in range(sections):
            size, address, raw_size, raw = struct.unpack_from("<IIII", data, table + i * 40 + 8)
            if address <= rva < address + max(size, raw_size):
                return raw + rva - address
        raise ValueError("PE address outside sections")

    if not import_rva:
        return []
    cursor = offset(import_rva)
    names = []
    while any(data[cursor : cursor + 20]):
        name_rva = struct.unpack_from("<I", data, cursor + 12)[0]
        start = offset(name_rva)
        names.append(data[start : data.index(b"\0", start)].decode("ascii"))
        cursor += 20
    return names


imports = imported_dlls(args.exe)
print("Imported DLLs:", ", ".join(imports))
with tempfile.TemporaryDirectory(prefix="mimisync-package-") as temporary:
    staging = Path(temporary) / name
    staging.mkdir()
    shutil.copy2(args.exe, staging / "Mimisync.exe")
    loader = args.exe.with_name("WebView2Loader.dll")
    if "webview2loader.dll" in {dll.lower() for dll in imports}:
        if not loader.is_file():
            raise SystemExit("This executable requires WebView2Loader.dll beside it.")
        shutil.copy2(loader, staging / "WebView2Loader.dll")
    for relative in ("docs",):
        shutil.copytree(
            ROOT / relative,
            staging / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", ".pytest_cache"),
        )
    (staging / "LEIA-ME-PRIMEIRO.txt").write_text(
        f"""MIMISYNC 0.2.0 - PORTATIL - WINDOWS 11 x64
Pacote: {name}

1. Extraia a pasta inteira do ZIP.
2. Abra Mimisync.exe dentro da pasta extraida, nao dentro do ZIP.
3. Siga o assistente que aparece dentro do app.

Nao precisa instalar o aplicativo, Node/Rust nem digitar comandos.
O WebView2 Runtime normalmente ja esta presente no Windows 11.
Esta e uma versao sem instalador do app, nao um ambiente sem dependencias.
Os dados ficam no perfil do Windows; os modelos e ambientes nao ficam no ZIP.
O app prepara Python/FFmpeg em um ambiente WSL2 exclusivo do Mimisync.
Se o Windows pedir autorizacao de administrador ou reinicializacao, conclua
essa etapa e abra o Mimisync novamente. Ele nao reinicia o PC sozinho.

Dentro do estudio, revise as licencas e clique em Instalar modelo no MuseTalk.
O app prepara o ambiente e baixa os checkpoints automaticamente em sequencia.
A primeira instalacao usa internet e pode demorar. Reserve espaco para os pesos.

Requer GPU NVIDIA com driver atualizado. O app nao instala o driver nem altera
configuracoes de BIOS. MuseTalk ~6 GB de VRAM e uma estimativa de triagem;
LatentSync 1.5 requer 8 GB e 1.6 requer 18 GB segundo os autores.

Esta versao foi compilada para Windows, mas ainda precisa dos testes de voces
no Windows real. Nao ha inferencia simulada. Nao e um binario assinado.

Se algo falhar: abra Detalhes da preparacao ou os logs do trabalho no app,
copie a mensagem e envie junto com modelo/preset e sua GPU/VRAM.
Nao envie chaves de acesso ou videos privados.

Licencas e limitacoes: docs/MODELS.md e docs/VALIDATION.md.
""",
        encoding="utf-8",
    )
    notices = staging / "third-party-notices"
    notices.mkdir()
    for package in (ROOT / "node_modules").glob("**/package.json"):
        if "node_modules" not in package.parts:
            continue
        folder = package.parent
        for license in folder.iterdir():
            if license.is_file() and license.name.upper().startswith(
                ("LICENSE", "NOTICE", "COPYING")
            ):
                target = (
                    notices
                    / "npm"
                    / folder.relative_to(ROOT / "node_modules")
                    / license.name
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(license, target)
    if args.cargo_registry:
        for license in args.cargo_registry.glob("*/*/**/*"):
            if license.is_file() and license.name.upper().startswith(
                ("LICENSE", "NOTICE", "COPYING")
            ):
                relative = Path(*license.relative_to(args.cargo_registry).parts[1:])
                target = notices / "cargo" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(license, target)
    (staging / "THIRD-PARTY-NOTICES.txt").write_text(
        "Mimisync uses React, Tauri, Rust crates and other open source dependencies.\nAvailable upstream license/notice files are included in third-party-notices/.\nModel code, checkpoints, WSL, FFmpeg and Python dependencies are installed separately and retain their own licenses. See docs/MODELS.md.\n",
        encoding="utf-8",
    )
    manifest = []
    for file in sorted(staging.rglob("*")):
        if file.is_file():
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            manifest.append(f"{digest}  {file.relative_to(staging).as_posix()}")
    (staging / "SHA256SUMS.txt").write_text("\n".join(manifest) + "\n")
    archive = args.output / (name + ".zip")
    pending = archive.with_suffix(".zip.partial")
    with zipfile.ZipFile(
        pending, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False
    ) as bundle:
        for file in sorted(staging.rglob("*")):
            if file.is_file():
                bundle.write(file, file.relative_to(staging.parent))
    pending.replace(archive)
    print(archive)
    print("bytes:", archive.stat().st_size)
    print("sha256:", hashlib.sha256(archive.read_bytes()).hexdigest())
