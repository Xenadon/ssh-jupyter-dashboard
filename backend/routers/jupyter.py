"""
Jupyter router — handles:
  POST /api/jupyter/start
  POST /api/jupyter/stop
"""

import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from backend.ssh_manager import ssh_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class StartJupyterRequest(BaseModel):
    work_dir: str = "~"
    init_script: str = ""
    target_port: str = ""
    extra_options: str = ""


class StopRequest(BaseModel):
    local_port: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/api/jupyter/start")
async def start_jupyter(req: StartJupyterRequest):
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            ssh_session.start_jupyter,
            req.work_dir,
            req.target_port,
            req.extra_options
        )
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/jupyter/stop")
async def stop_jupyter(req: StopRequest):
    ssh_session.stop_jupyter(req.local_port)
    return {"status": "success"}
