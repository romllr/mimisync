import os
import signal
import subprocess
import threading
from pathlib import Path


class Cancelled(RuntimeError):
    pass


def terminate(proc):
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if proc.poll() is None:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait()


def run(args, cwd: Path, log, cancel: threading.Event | None = None, env=None):
    log("$ " + " ".join(map(str, args)))
    with subprocess.Popen(
        list(map(str, args)),
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=os.name == "posix",
    ) as p:

        def watch():
            if cancel:
                while p.poll() is None:
                    if cancel.wait(0.2):
                        terminate(p)
                        return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            for line in p.stdout:
                log(line.rstrip())
            code = p.wait()
            watcher.join(timeout=1)
            if cancel and cancel.is_set():
                raise Cancelled("Processamento cancelado")
            if code:
                raise RuntimeError(f"Comando falhou (código {code}); consulte os logs")
        finally:
            terminate(p)
