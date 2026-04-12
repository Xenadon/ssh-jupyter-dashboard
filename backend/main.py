"""
FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app with lifespan
  - Add CORS middleware
  - Register routers
  - Mount frontend static files
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Configure logging before importing anything else
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# config_manager import triggers migration of legacy config.json on first run
from backend import config_manager  # noqa: E402  (import after logging setup)
from backend.ssh_manager import ssh_session
from backend.routers import ssh, jupyter, config, sftp


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle manager."""
    logger.info("[APP] Starting up…")
    yield
    logger.info("[APP] Shutting down — closing SSH connections")
    ssh_session.close_all()


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ssh.router)
app.include_router(jupyter.router)
app.include_router(config.router)
app.include_router(sftp.router)


# ── Frontend static files ──────────────────────────────────────────────────────

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
FRONTEND_DIST = os.path.join(_PROJECT_ROOT, "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="assets"
    )

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


# ── Dev entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    app_cfg = config_manager.get_app_config()
    server = app_cfg.get("server", {})
    host = server.get("host", "127.0.0.1")
    port = server.get("port", 8000)
    print(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
