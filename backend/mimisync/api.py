import hmac
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .catalog import ENGINES, catalog
from .hardware import detect, recommendation
from .media import probe
from .models import Models
from .store import Store
from .service import Worker


class Params(BaseModel):
    steps: int | None = Field(None, ge=20, le=50)
    guidance: float | None = Field(None, ge=1, le=3)
    batch_size: int | None = Field(None, ge=1, le=16)
    extra_margin: int = Field(10, ge=0, le=40)
    cheek_width: int = Field(90, ge=20, le=150)
    parsing_mode: Literal["jaw", "neck", "raw"] = "jaw"
    seed: int = Field(1247, ge=0, le=2147483647)


class Render(BaseModel):
    model: str
    video_id: str
    audio_id: str
    preset: Literal["fast", "balanced", "quality"] = "balanced"
    preview: bool = False
    start: float = Field(0, ge=0)
    preview_seconds: float = Field(5, ge=1, le=15)
    params: Params = Field(default_factory=Params)


class Install(BaseModel):
    action: Literal["install", "environment", "checkpoints", "remove"]
    licenses_reviewed: bool = False


def create_app(root: Path | None = None, token: str | None = None):
    root = (
        root
        or Path(
            os.environ.get("MIMISYNC_DATA", str(Path.home() / ".local/share/mimisync"))
        )
    ).resolve()
    root.mkdir(parents=True, exist_ok=True)
    token = token or os.environ.get("MIMISYNC_TOKEN")
    if not token or len(token) < 32:
        raise ValueError("MIMISYNC_TOKEN deve conter pelo menos 32 caracteres")
    store, models = Store(root / "state.db"), Models(root / "models")
    worker = Worker(root, store, models)

    @asynccontextmanager
    async def lifespan(app):
        yield
        worker.close()

    app = FastAPI(
        lifespan=lifespan,
        title="Mimisync",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store, app.state.worker, app.state.models = store, worker, models

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        # Query tokens are limited to media GET for HTML video playback.
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if request.method in ("GET", "HEAD") and (
            request.url.path.endswith("/file") or request.url.path.endswith("/result")
        ):
            supplied = supplied or request.query_params.get("token", "")
        if not hmac.compare_digest(supplied, token):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Não autorizado"}, status_code=401)
        return await call_next(request)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Registro não encontrado"}, status_code=404)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.2.0"}

    @app.get("/system")
    def system():
        hw = detect()
        return {**hw, "recommendation": recommendation(hw, ENGINES)}

    @app.get("/models")
    def list_models():
        return [{**e, **models.status(e["id"])} for e in catalog()]

    @app.get("/models/{id}/preflight")
    def preflight(id: str):
        if id not in ENGINES:
            raise HTTPException(404, "Modelo desconhecido")
        return models.preflight(id)

    @app.post("/models/{id}/actions", status_code=202)
    def install(id: str, request: Install):
        if id not in ENGINES:
            raise HTTPException(404, "Modelo desconhecido")
        if request.action != "remove":
            if not request.licenses_reviewed:
                raise HTTPException(
                    400, "Leia docs/MODELS.md e revise as licenças antes de instalar"
                )
            check = models.preflight(id)
            if check["issues"]:
                raise HTTPException(409, "; ".join(check["issues"]))
        return worker.submit(request.action, model=id)

    @app.get("/media")
    def list_media():
        return [
            {k: v for k, v in m.items() if k != "path"} for m in store.list("media")
        ]

    @app.post("/media", status_code=201)
    def upload(file: UploadFile = File(...)):
        name = Path(file.filename or "media").name
        ext = Path(name).suffix.lower()
        if ext not in (".mp4", ".mov", ".mp3", ".wav"):
            raise HTTPException(415, "Use MP4/MOV/MP3/WAV")
        id = uuid.uuid4().hex
        folder = root / "media"
        folder.mkdir(exist_ok=True)
        target = folder / (id + ext)
        try:
            with target.open("wb") as f:
                shutil.copyfileobj(file.file, f, 1024 * 1024)
            info = probe(target)
            is_video = ext in (".mp4", ".mov")
            if (
                info["duration"] <= 0
                or (is_video and not info["has_video"])
                or (not is_video and not info["has_audio"])
            ):
                raise ValueError("Arquivo sem fluxo de mídia compatível")
            if is_video and (info["width"] % 2 or info["height"] % 2):
                raise ValueError(
                    "Dimensões ímpares não suportadas na exportação H.264 atual"
                )
            record = store.put(
                "media",
                {
                    "id": id,
                    "name": name,
                    "kind": "video" if is_video else "audio",
                    "path": str(target),
                    **info,
                },
            )
            return {k: v for k, v in record.items() if k != "path"}
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(422, f"Mídia inválida: {exc}")
        finally:
            file.file.close()

    @app.get("/media/{id}/file")
    def media_file(id: str):
        m = store.get("media", id)
        return FileResponse(m["path"])

    @app.get("/jobs")
    def jobs():
        return store.list("jobs")

    @app.post("/jobs", status_code=202)
    def render(request: Render):
        data = request.model_dump()
        if request.model not in ENGINES:
            raise HTTPException(400, "Modelo desconhecido")
        video, audio = (
            store.get("media", request.video_id),
            store.get("media", request.audio_id),
        )
        if video["kind"] != "video" or audio["kind"] != "audio":
            raise HTTPException(400, "Selecione um vídeo e um áudio")
        if request.start >= min(video["duration"], audio["duration"]):
            raise HTTPException(400, "Início fora da duração disponível")
        if not models.status(request.model)["ready"]:
            raise HTTPException(409, "Instale e verifique o modelo antes de renderizar")
        data["params"] = request.params.model_dump(exclude_none=True)
        return worker.submit("render", **data)

    @app.post("/jobs/{id}/cancel")
    def cancel(id: str):
        return worker.cancel(id)

    @app.get("/jobs/{id}/logs")
    def logs(id: str):
        store.get("jobs", id)
        p = root / "logs" / f"{id}.log"
        if not p.exists():
            return {"text": ""}
        with p.open("rb") as f:
            f.seek(max(0, p.stat().st_size - 64 * 1024))
            return {"text": f.read().decode("utf-8", errors="replace")}

    @app.get("/jobs/{id}/result")
    def result(id: str):
        job = store.get("jobs", id)
        if job["status"] != "completed" or not job.get("output"):
            raise HTTPException(409, "Resultado indisponível")
        return FileResponse(
            job["output"], media_type="video/mp4", filename=f"mimisync-{id[:8]}.mp4"
        )

    return app
