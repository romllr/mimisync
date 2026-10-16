#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
source_root="$1"
version="$2"
case "$version" in *[!0-9.]*|'') echo 'Versão inválida'; exit 1;; esac
release_root="/opt/mimisync/releases/$version"
echo 'Instalando ferramentas de áudio, vídeo e compilação...'
dpkg --configure -a
apt-get update
apt-get install -y --no-install-recommends ca-certificates ffmpeg git build-essential python3-dev python3-venv libgl1 libglib2.0-0
if ! id mimisync >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash mimisync
fi
install -d "$release_root" /opt/mimisync/controller
cp -a "$source_root/backend" "$release_root/"
echo 'Preparando o processador local...'
if [ ! -x /opt/mimisync/controller/bin/python ]; then
  python3 -m venv /opt/mimisync/controller
fi
python_bin=/opt/mimisync/controller/bin/python
"$python_bin" -m pip install --disable-pip-version-check -r "$release_root/backend/requirements.lock"
"$python_bin" -m pip install --disable-pip-version-check 'uv==0.12.23'
"$python_bin" -m pip install --disable-pip-version-check --no-deps "$release_root/backend"
"$python_bin" -c "import mimisync.api; import shutil; assert shutil.which('ffmpeg') and shutil.which('ffprobe')"
chown -R mimisync:mimisync /opt/mimisync
printf '%s\n' "$version" > "$release_root/installed-version"
echo 'Componentes locais preparados.'
