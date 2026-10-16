import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from .catalog import ENGINES
from .hardware import detect
from .process import run


class Models:
    def __init__(self, root):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, id):
        if id not in ENGINES:
            raise ValueError("Modelo desconhecido")
        return self.root / id

    def python(self, id):
        return self.path(id) / "venv/bin/python"

    def status(self, id):
        p = self.path(id)
        state = (
            json.loads((p / "state.json").read_text())
            if (p / "state.json").exists()
            else {}
        )
        return {
            **state,
            "environment_installed": self.python(id).exists()
            and state.get("environment_installed", False),
            "checkpoints_installed": state.get("checkpoints_installed", False),
            "ready": bool(state.get("verified") and self.python(id).exists()),
        }

    def save(self, id, **kwargs):
        p = self.path(id)
        p.mkdir(parents=True, exist_ok=True)
        state = self.status(id)
        state.update(kwargs)
        tmp = p / "state.tmp"
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(p / "state.json")

    def preflight(self, id):
        e = ENGINES[id]
        hw = detect()
        issues = []
        if platform.system() != "Linux" or platform.machine() not in (
            "x86_64",
            "AMD64",
        ):
            issues.append("Use Ubuntu x86_64 no WSL2 com suporte CUDA")
        if not hw["gpus"]:
            issues.append("GPU NVIDIA não encontrada")
        elif max(g["total_mb"] for g in hw["gpus"]) < e.min_vram_mb:
            issues.append(
                f"VRAM insuficiente: recomendado pelo menos {e.min_vram_mb} MiB"
            )
        for name in ("ffmpeg", "ffprobe", "git", "uv"):
            if not shutil.which(name):
                issues.append(f"Instale {name}")
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", str(self.root.resolve())):
            issues.append(
                "Diretório dos modelos deve ter apenas letras ASCII, números, /, _, . e - (limitação dos scripts oficiais)"
            )
        free = shutil.disk_usage(self.root).free
        if free < 20 * 1024**3:
            issues.append("Reserve pelo menos 20 GB livres por ambiente")
        return {
            "issues": issues,
            "license": e.license,
            "repository": e.repository,
            "commit": e.commit,
            "checkpoint_repo": e.checkpoint_repo,
            "hardware": hw,
        }

    def install_environment(self, id, log, cancel):
        check = self.preflight(id)
        if check["issues"]:
            raise RuntimeError("; ".join(check["issues"]))
        p, e = self.path(id), ENGINES[id]
        p.mkdir(parents=True, exist_ok=True)
        self.save(id, verified=False, environment_installed=False)
        source = p / "source"
        if not source.exists():
            run(["git", "clone", "--no-checkout", e.repository, source], p, log, cancel)
        actual_remote = subprocess.check_output(
            ["git", "-C", str(source), "remote", "get-url", "origin"], text=True
        ).strip()
        if actual_remote != e.repository:
            raise RuntimeError(
                "Origem do checkout não corresponde ao repositório oficial"
            )
        run(["git", "checkout", "--detach", e.commit], source, log, cancel)
        run(["uv", "venv", "--clear", "--python", "3.10", p / "venv"], p, log, cancel)
        py = self.python(id)
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                py,
                "pip==24.0",
                "setuptools==69.5.1",
                "wheel==0.43.0",
            ],
            p,
            log,
            cancel,
        )
        if id.startswith("musetalk"):
            run(
                [
                    py,
                    "-m",
                    "pip",
                    "install",
                    "torch==2.0.1",
                    "torchvision==0.15.2",
                    "torchaudio==2.0.2",
                    "--index-url",
                    "https://download.pytorch.org/whl/cu118",
                ],
                source,
                log,
                cancel,
            )
        run([py, "-m", "pip", "install", "-r", "requirements.txt"], source, log, cancel)
        if id.startswith("musetalk"):
            run(
                [
                    py,
                    "-m",
                    "pip",
                    "install",
                    "mmengine==0.10.7",
                    "mmcv==2.0.1",
                    "-f",
                    "https://download.openmmlab.com/mmcv/dist/cu118/torch2.0.0/index.html",
                ],
                source,
                log,
                cancel,
            )
            run(
                [py, "-m", "pip", "install", "mmdet==3.1.0", "mmpose==1.1.0"],
                source,
                log,
                cancel,
            )
        run([py, "-m", "pip", "check"], source, log, cancel)
        freeze = subprocess.check_output(
            [str(py), "-m", "pip", "freeze"], cwd=source, text=True
        )
        (p / "environment.freeze.txt").write_text(freeze)
        self.save(id, environment_installed=True, source_commit=e.commit)
        self.verify(id, log, cancel)

    def download(self, id, log, cancel):
        from huggingface_hub import HfApi, snapshot_download

        p, e = self.path(id), ENGINES[id]
        source = p / "source"
        if not self.status(id)["environment_installed"]:
            raise RuntimeError("Instale primeiro o ambiente do modelo")
        self.save(id, checkpoints_installed=False, verified=False)
        if id.startswith("musetalk"):
            downloads = [
                (e.checkpoint_repo, "models", ["musetalkV15/*"]),
                (
                    "stabilityai/sd-vae-ft-mse",
                    "models/sd-vae",
                    ["config.json", "diffusion_pytorch_model.bin"],
                ),
                (
                    "openai/whisper-tiny",
                    "models/whisper",
                    ["config.json", "pytorch_model.bin", "preprocessor_config.json"],
                ),
                ("yzd-v/DWPose", "models/dwpose", ["dw-ll_ucoco_384.pth"]),
                (
                    "ManyOtherFunctions/face-parse-bisent",
                    "models/face-parse-bisent",
                    ["79999_iter.pth", "resnet18-5c106cde.pth"],
                ),
            ]
        else:
            downloads = [
                (
                    e.checkpoint_repo,
                    "checkpoints",
                    ["latentsync_unet.pt", "whisper/tiny.pt"],
                ),
                (
                    "stabilityai/sd-vae-ft-mse",
                    "vae",
                    ["config.json", "diffusion_pytorch_model.bin"],
                ),
            ]
        previous = (
            json.loads((p / "downloads.json").read_text())
            if (p / "downloads.json").exists()
            else {}
        )
        revisions = {}
        for repo, target, patterns in downloads:
            if cancel.is_set():
                raise RuntimeError("Download cancelado")
            revision = (
                previous.get(repo)
                or HfApi(endpoint="https://huggingface.co").model_info(repo).sha
            )
            revisions[repo] = revision
            # Save revisions before transfer, so retries use exactly the same artifacts.
            (p / "downloads.json").write_text(
                json.dumps({**previous, **revisions}, indent=2)
            )
            log(f"Download oficial: {repo}@{revision}")
            snapshot_download(
                repo_id=repo,
                revision=revision,
                allow_patterns=patterns,
                local_dir=source / target,
                max_workers=2,
                endpoint="https://huggingface.co",
            )
        if id.startswith("musetalk"):
            detector = source / "musetalk/utils/face_detection/detection/sfd/s3fd.pth"
            # This is the exact upstream S3FD URL, with the published hash prefix.
            code = (
                "from torch.hub import download_url_to_file; download_url_to_file('https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth', '"
                + str(detector)
                + "', hash_prefix='619a316812')"
            )
            run([self.python(id), "-c", code], source, log, cancel)
        if not id.startswith("musetalk"):
            # from_pretrained accepts a local directory with this name before HF lookup.
            vae_path = source / "stabilityai/sd-vae-ft-mse"
            vae_path.parent.mkdir(exist_ok=True)
            if not vae_path.exists():
                vae_path.symlink_to("../vae", target_is_directory=True)
            # Official InsightFace downloader; license reviewed before this operation.
            code = "from insightface.app import FaceAnalysis; FaceAnalysis(allowed_modules=['detection','landmark_2d_106'],root='checkpoints/auxiliary',providers=['CUDAExecutionProvider'])"
            run([self.python(id), "-c", code], source, log, cancel)
        records = {}
        for folder in (
            [source / "models", source / "musetalk/utils/face_detection/detection/sfd"]
            if id.startswith("musetalk")
            else [source / "checkpoints", source / "vae"]
        ):
            for file in folder.rglob("*"):
                if (
                    file.is_file()
                    and ".cache" not in file.parts
                    and file.suffix not in (".py", ".pyc")
                ):
                    if cancel.is_set():
                        raise RuntimeError("Download cancelado")
                    with file.open("rb") as stream:
                        digest = (
                            hashlib.file_digest(stream, "sha256").hexdigest()
                            if hasattr(hashlib, "file_digest")
                            else self.hash_file(stream)
                        )
                    records[str(file.relative_to(source))] = {
                        "bytes": file.stat().st_size,
                        "sha256": digest,
                    }
        (p / "artifacts.json").write_text(json.dumps(records, indent=2))
        self.save(id, checkpoints_installed=True, revisions=revisions)
        self.verify(id, log, cancel)

    @staticmethod
    def hash_file(stream):
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()

    def verify(self, id, log, cancel):
        state = self.status(id)
        if not state["environment_installed"] or not state["checkpoints_installed"]:
            return
        source = self.path(id) / "source"
        required = (
            [
                "musetalk/utils/face_detection/detection/sfd/s3fd.pth",
                "models/musetalkV15/unet.pth",
                "models/musetalkV15/musetalk.json",
                "models/sd-vae/diffusion_pytorch_model.bin",
                "models/whisper/pytorch_model.bin",
                "models/dwpose/dw-ll_ucoco_384.pth",
                "models/face-parse-bisent/79999_iter.pth",
                "models/face-parse-bisent/resnet18-5c106cde.pth",
            ]
            if id.startswith("musetalk")
            else [
                "checkpoints/latentsync_unet.pt",
                "checkpoints/whisper/tiny.pt",
                "checkpoints/auxiliary/models/buffalo_l/det_10g.onnx",
                "checkpoints/auxiliary/models/buffalo_l/2d106det.onnx",
            ]
        )
        missing = [
            f
            for f in required
            if not (source / f).is_file() or not (source / f).stat().st_size
        ]
        if missing:
            raise RuntimeError("Checkpoints incompletos: " + ", ".join(missing))
        run(
            [
                self.python(id),
                "-c",
                "import torch; assert torch.cuda.is_available(), 'CUDA indisponível'; x=torch.ones(1, device='cuda'); assert x.add(1).item() == 2; torch.cuda.synchronize(); print(torch.cuda.get_device_name(0))",
            ],
            source,
            log,
            cancel,
        )
        run([self.python(id), "-m", "scripts.inference", "--help"], source, log, cancel)
        self.save(id, verified=True)

    def delete(self, id):
        p = self.path(id)
        if p.exists():
            shutil.rmtree(p)
