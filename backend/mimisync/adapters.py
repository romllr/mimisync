import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from .catalog import ENGINES
from .process import run


class Adapter(Protocol):
    def command(
        self, python: Path, source: Path, work: Path, params: dict, gpu: int
    ) -> list[str]: ...


@dataclass
class MuseTalk15:
    def command(self, python, source, work, params, gpu):
        config = work / "inference.json"
        # JSON is a YAML subset accepted by OmegaConf; paths never become YAML syntax.
        config.write_text(
            json.dumps(
                {
                    "job": {
                        "video_path": str(work / "input.mp4"),
                        "audio_path": str(work / "audio.wav"),
                        "result_name": str(work / "generated.mp4"),
                    }
                }
            )
        )
        return [
            str(python),
            "-m",
            "scripts.inference",
            "--version",
            "v15",
            "--inference_config",
            str(config),
            "--result_dir",
            str(work / "results"),
            "--unet_model_path",
            "models/musetalkV15/unet.pth",
            "--unet_config",
            "models/musetalkV15/musetalk.json",
            "--gpu_id",
            str(gpu),
            "--batch_size",
            str(params["batch_size"]),
            "--extra_margin",
            str(params["extra_margin"]),
            "--left_cheek_width",
            str(params["cheek_width"]),
            "--right_cheek_width",
            str(params["cheek_width"]),
            "--parsing_mode",
            params["parsing_mode"],
            "--use_float16",
        ]


@dataclass
class LatentSync:
    version: str

    def command(self, python, source, work, params, gpu):
        return [
            str(python),
            "-m",
            "scripts.inference",
            "--unet_config_path",
            ENGINES[self.version].config,
            "--inference_ckpt_path",
            "checkpoints/latentsync_unet.pt",
            "--video_path",
            str(work / "input.mp4"),
            "--audio_path",
            str(work / "audio.wav"),
            "--video_out_path",
            str(work / "generated.mp4"),
            "--temp_dir",
            str(work / "temp"),
            "--inference_steps",
            str(params["steps"]),
            "--guidance_scale",
            str(params["guidance"]),
            "--seed",
            str(params["seed"]),
        ]


ADAPTERS = {
    "musetalk-1.5": MuseTalk15(),
    "latentsync-1.5": LatentSync("latentsync-1.5"),
    "latentsync-1.6": LatentSync("latentsync-1.6"),
}


def infer(models, id, work, params, gpu, log, cancel):
    source = models.path(id) / "source"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    env["HF_HUB_OFFLINE"] = "1"
    run(
        ADAPTERS[id].command(models.python(id), source, work, params, 0),
        source,
        log,
        cancel,
        env,
    )
    output = work / "generated.mp4"
    # MuseTalk can swallow per-task exceptions; an exit code alone is insufficient.
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("O motor não produziu vídeo; consulte os logs de inferência")
    return output
