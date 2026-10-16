import json
import subprocess
from fractions import Fraction
from pathlib import Path
from .process import run


def probe(path: Path):
    p = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    data = json.loads(p.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    rate = (video or {}).get("avg_frame_rate", "0/1")
    return {
        "duration": float(data["format"].get("duration", 0)),
        "width": (video or {}).get("width"),
        "height": (video or {}).get("height"),
        "fps": rate,
        "has_video": video is not None,
        "has_audio": audio is not None,
        "sar": (video or {}).get("sample_aspect_ratio", "1:1"),
        "vfr": bool(video and video.get("avg_frame_rate") != video.get("r_frame_rate")),
    }


def prepare(video, audio, work, start, duration, latent, log, cancel):
    # Controlled ASCII filenames: upstream scripts interpolate paths into shell commands.
    v, a = work / "input.mp4", work / "audio.wav"
    args = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-ss",
        str(start),
        "-i",
        video,
        "-t",
        str(duration),
        "-an",
        "-c:v",
        "libx264",
        "-crf",
        "0",
        "-preset",
        "fast",
    ]
    if latent:
        args += ["-r", "25"]
    run(args + [v], work, log, cancel)
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-ss",
            str(start),
            "-i",
            audio,
            "-t",
            str(duration),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            a,
        ],
        work,
        log,
        cancel,
    )
    return v, a


def export(generated, audio, output, original, start, duration, crf, work, log, cancel):
    info = probe(original)
    if info["width"] % 2 or info["height"] % 2:
        raise ValueError(
            "H.264 yuv420p requer dimensões pares; este arquivo precisa de uma decisão explícita de recorte/padding"
        )
    fps = str(Fraction(info["fps"]))
    # Full-frame blending is performed by each official engine before this export.
    run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            generated,
            "-ss",
            str(start),
            "-i",
            audio,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            str(duration),
            "-vf",
            f"scale={info['width']}:{info['height']}:flags=lanczos,setsar={info['sar'].replace(':', '/')}",
            "-r",
            fps,
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            output,
        ],
        work,
        log,
        cancel,
    )
    final = probe(output)
    if not final["has_video"] or not final["has_audio"] or final["duration"] <= 0:
        raise RuntimeError("Exportação inválida")
    return final
