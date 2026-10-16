import csv
import io
import platform
import shutil
import subprocess


def detect():
    result = {
        "platform": platform.system(),
        "machine": platform.machine(),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "gpus": [],
        "error": None,
    }
    try:
        p = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        for row in csv.reader(io.StringIO(p.stdout)):
            i, name, total, free, driver = [s.strip() for s in row]
            result["gpus"].append(
                {
                    "index": int(i),
                    "name": name,
                    "total_mb": int(total),
                    "free_mb": int(free),
                    "driver": driver,
                }
            )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        result["error"] = f"NVIDIA/CUDA indisponível: {exc}"
    return result


def recommendation(hardware, engines):
    free = max((g["free_mb"] for g in hardware["gpus"]), default=0)
    return next(
        (
            e
            for e in ["latentsync-1.6", "latentsync-1.5", "musetalk-1.5"]
            if free >= engines[e].min_vram_mb + 512
        ),
        None,
    )
