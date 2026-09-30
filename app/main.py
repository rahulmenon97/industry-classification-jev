from contextlib import asynccontextmanager
from threading import Lock
from urllib.parse import urlparse
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.clients import ProviderClients
from app.config import ROOT, Settings
from app.models import Run, RunRequest
from app.database import Database
from app.service import PipelineService
from app.taxonomy import Taxonomy, TaxonomyError


def create_app(settings=None, clients=None):
    settings = settings or Settings()
    database = Database(settings.database_path)
    clients = clients or ProviderClients(settings)
    service = PipelineService(settings, database, clients)
    lock = Lock()

    def taxonomy_problem():
        try:
            Taxonomy("industry_v2")
        except TaxonomyError as error:
            return str(error)
        return None

    @asynccontextmanager
    async def lifespan(app):
        app.state.taxonomy_error = taxonomy_problem()
        database.recover()
        yield

    api = FastAPI(title="Industry Explorer", version="0.1.0", lifespan=lifespan)
    api.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @api.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method == "POST"
            and origin
            and urlparse(origin).netloc != request.headers.get("host")
        ):
            return Response("Cross-origin requests are not allowed", status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    api.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")

    @api.get("/")
    def index():
        return FileResponse(ROOT / "app/static/index.html")

    @api.get("/api/health")
    def health():
        api.state.taxonomy_error = taxonomy_problem()
        return {
            "ready": clients.ready() and api.state.taxonomy_error is None,
            "taxonomy_default": "industry_v2",
            "taxonomy_error": api.state.taxonomy_error,
        }

    @api.post("/api/runs", response_model=Run)
    def run(body: RunRequest):
        if not clients.ready():
            raise HTTPException(
                503, "Configure EXA_API_KEY and TYPESAFE_API_KEY in .env.local, then restart."
            )
        if not lock.acquire(blocking=False):
            raise HTTPException(
                409, "A classification is already running. Try again after it completes."
            )
        try:
            return service.execute(body)
        except TaxonomyError as error:
            raise HTTPException(503, str(error)) from None
        finally:
            lock.release()

    @api.get("/api/runs")
    def history(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return database.list(limit, offset)

    @api.get("/api/runs/{run_id}", response_model=Run)
    def get(run_id: UUID):
        result = database.get(str(run_id))
        if not result:
            raise HTTPException(404, "Run not found")
        return result

    @api.get("/api/runs/{run_id}/export")
    def export(run_id: UUID):
        return Response(
            get(run_id).model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="run-{run_id}.json"'},
        )

    return api
