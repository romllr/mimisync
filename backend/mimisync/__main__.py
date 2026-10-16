import argparse
import os
import sys
import threading
from pathlib import Path
import uvicorn
from .api import create_app

# WSL exec does not necessarily load the shell profile installed by uv.
os.environ["PATH"] = (
    str(Path(sys.executable).parent)
    + os.pathsep
    + str(Path.home() / ".local/bin")
    + os.pathsep
    + "/usr/lib/wsl/lib"
    + os.pathsep
    + os.environ.get("PATH", "")
)

parser = argparse.ArgumentParser()
parser.add_argument("--token-file", type=Path)
parser.add_argument("--token-stdin", action="store_true")
parser.add_argument("--port", type=int, default=47831)
args = parser.parse_args()
token = sys.stdin.readline().strip() if args.token_stdin else None
if args.token_file:
    token = args.token_file.read_text().strip()
    args.token_file.unlink()
server = uvicorn.Server(
    uvicorn.Config(
        create_app(token=token), host="127.0.0.1", port=args.port, access_log=False
    )
)
if args.token_stdin:

    def watch_parent():
        sys.stdin.read()
        server.should_exit = True

    threading.Thread(target=watch_parent, daemon=True).start()
server.run()
