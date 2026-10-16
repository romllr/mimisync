import queue
import re
import threading
from . import media
from .adapters import infer
from .catalog import ENGINES, PRESETS
from .hardware import detect
from .process import Cancelled


class Worker:
    def __init__(self, root, store, models):
        self.root, self.store, self.models = root, store, models
        self.queue = queue.Queue()
        self.events = {}
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def close(self):
        with self.lock:
            for event in self.events.values():
                event.set()
        self.queue.put(None)
        self.thread.join(timeout=10)

    def submit(self, kind, **kwargs):
        job = self.store.create(kind, **kwargs)
        with self.lock:
            self.events[job["id"]] = threading.Event()
        self.queue.put(job["id"])
        return job

    def cancel(self, id):
        job = self.store.get("jobs", id)
        if job["status"] not in ("queued", "running"):
            return job
        with self.lock:
            if id in self.events:
                self.events[id].set()
        if job["status"] == "queued":
            return self.store.update(id, status="cancelled", stage="Cancelado")
        return job

    def loop(self):
        while True:
            id = self.queue.get()
            if id is None:
                self.queue.task_done()
                return
            event = self.events[id]
            logpath = self.root / "logs" / f"{id}.log"
            logpath.parent.mkdir(exist_ok=True)

            def log(message):
                with logpath.open("a", encoding="utf-8") as f:
                    f.write(message + "\n")
                match = re.search(r"(\d{1,3})%\|", message)
                if match:
                    self.store.update(id, progress=min(int(match[1]), 100))

            try:
                if event.is_set():
                    continue
                job = self.store.update(id, status="running", stage="Preparando")
                if job["kind"] == "install":
                    self.models.save(
                        job["model"], checkpoints_installed=False, verified=False
                    )
                    self.models.install_environment(job["model"], log, event)
                    self.models.download(job["model"], log, event)
                elif job["kind"] == "environment":
                    self.models.install_environment(job["model"], log, event)
                elif job["kind"] == "checkpoints":
                    self.models.download(job["model"], log, event)
                elif job["kind"] == "remove":
                    self.models.delete(job["model"])
                else:
                    self.render(job, log, event)
                if event.is_set():
                    raise Cancelled("Cancelado")
                self.store.update(
                    id, status="completed", stage="Concluído", progress=100
                )
            except Exception as exc:
                log(f"{type(exc).__name__}: {exc}")
                self.store.update(
                    id,
                    status="cancelled" if event.is_set() else "failed",
                    stage=str(exc),
                    progress=None,
                )
            finally:
                with self.lock:
                    self.events.pop(id, None)
                self.queue.task_done()

    def render(self, job, log, event):
        id, model = job["id"], job["model"]
        if not self.models.status(model)["ready"]:
            raise RuntimeError(
                "Modelo não instalado/verificado; instale ambiente e checkpoints"
            )
        gpus = detect()["gpus"]
        compatible = [g for g in gpus if g["free_mb"] >= ENGINES[model].min_vram_mb]
        if not compatible:
            raise RuntimeError("VRAM livre insuficiente ou GPU NVIDIA indisponível")
        gpu = max(compatible, key=lambda g: g["free_mb"])["index"]
        video = self.store.get("media", job["video_id"])
        audio = self.store.get("media", job["audio_id"])
        work = self.root / "jobs" / id
        work.mkdir(parents=True, exist_ok=True)
        duration = min(video["duration"], audio["duration"]) - job["start"]
        if job["preview"]:
            duration = min(duration, job["preview_seconds"])
        if duration <= 0:
            raise ValueError("Início fora da duração disponível")
        params = {**PRESETS[job["preset"]], **job["params"]}
        self.store.update(id, stage="Preparando áudio e vídeo", duration=duration)
        if model.startswith("latentsync"):
            log(
                "LatentSync processa a 25 FPS. Exportação retorna ao FPS médio original; a cadência original não é recuperada."
            )
        if video["vfr"]:
            log("Entrada possivelmente VFR: saída será CFR no FPS médio original.")
        media.prepare(
            video["path"],
            audio["path"],
            work,
            job["start"],
            duration,
            model.startswith("latentsync"),
            log,
            event,
        )
        self.store.update(
            id, stage="Inferência e composição facial pelo motor oficial", progress=None
        )
        generated = infer(self.models, model, work, params, gpu, log, event)
        generated_info = media.probe(generated)
        if abs(generated_info["duration"] - duration) > max(0.25, duration * 0.02):
            raise RuntimeError(
                "Motor retornou duração inesperada; exportação interrompida para evitar truncamento silencioso"
            )
        self.store.update(id, stage="Exportando H.264", progress=None)
        info = media.export(
            generated,
            audio["path"],
            work / "output.mp4",
            video["path"],
            job["start"],
            duration,
            params["crf"],
            work,
            log,
            event,
        )
        self.store.update(id, output=str(work / "output.mp4"), output_info=info)
