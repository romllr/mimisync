from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Engine:
    id: str
    name: str
    repository: str
    commit: str
    checkpoint_repo: str
    min_vram_mb: int
    face_resolution: int
    license: str
    config: str = ""


ENGINES = {
    "musetalk-1.5": Engine(
        "musetalk-1.5",
        "MuseTalk 1.5",
        "https://github.com/TMElyralab/MuseTalk.git",
        "0a89dec45a0192b824e3cf4daf96c239440c5ed8",
        "TMElyralab/MuseTalk",
        6144,
        256,
        "MIT; revisar licenças dos pesos auxiliares. VRAM de 6 GB é estimativa conservadora, não mínimo oficial.",
    ),
    "latentsync-1.5": Engine(
        "latentsync-1.5",
        "LatentSync 1.5",
        "https://github.com/bytedance/LatentSync.git",
        "7b380d6adde7aa23cba4a53bb15cd5cfb3c168e7",
        "ByteDance/LatentSync-1.5",
        8192,
        256,
        "Apache-2.0; pesos InsightFace têm restrições de uso não comercial.",
        "configs/unet/stage2.yaml",
    ),
    "latentsync-1.6": Engine(
        "latentsync-1.6",
        "LatentSync 1.6",
        "https://github.com/bytedance/LatentSync.git",
        "a229c3948406bc2cf6eaf4873e662e70c6a04746",
        "ByteDance/LatentSync-1.6",
        18432,
        512,
        "Apache-2.0; pesos InsightFace têm restrições de uso não comercial.",
        "configs/unet/stage2_512.yaml",
    ),
}
PRESETS = {
    "fast": {"steps": 20, "guidance": 1.5, "batch_size": 8, "crf": 20},
    "balanced": {"steps": 30, "guidance": 1.5, "batch_size": 4, "crf": 18},
    "quality": {"steps": 50, "guidance": 1.5, "batch_size": 2, "crf": 16},
}


def catalog():
    return [asdict(e) for e in ENGINES.values()]
