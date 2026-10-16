"""Restore the exact public sample for scanning only; never execute it."""
from pathlib import Path
import hashlib
import subprocess

root = Path('scan-input')
root.mkdir(exist_ok=True)
name = 'Mimisync-0.2.0-windows-x64-test.zip'
path = root / name
with path.open('wb') as output:
    subprocess.run(['git', 'show', f'b0b1beffe29010b1c9f0bb048466b03710b3f58b:downloads/{name}'], stdout=output, check=True)
actual = hashlib.sha256(path.read_bytes()).hexdigest()
expected = '2cc6338ba6efaf0dffd48c44237d8d7c259dd59bee54c881bf01cbf504a3d861'
if actual != expected:
    raise SystemExit('Sample integrity mismatch; stop investigation.')
print('Exact reported ZIP staged for scanning; SHA-256:', actual)
