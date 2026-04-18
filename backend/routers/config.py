"""
Config router — handles:
  GET  /api/config
  POST /api/config/server
  POST /api/config/save_instances
"""

import asyncio
import logging
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from backend import config_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class ServerConfigRequest(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class InstanceRowModel(BaseModel):
    dir: str
    port: str
    options: str


class EditorConfigRequest(BaseModel):
    theme: str = "vs"
    fontSize: int = 14
    fontFamily: str = "monospace"
    language: str = ""


class SavePresetsRequest(BaseModel):
    host: str
    user: str
    instances: List[InstanceRowModel]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/config")
async def get_config():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, config_manager.load_config_for_api)


@router.post("/api/config/server")
async def save_server_config(req: ServerConfigRequest):
    """Save server configuration"""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: config_manager.save_app_config({
                "server": {
                    "host": req.host,
                    "port": req.port
                }
            })
        )
        return {"status": "success", "message": f"Server config saved: {req.host}:{req.port}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/config/editor")
async def save_editor_config(req: EditorConfigRequest):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: config_manager.save_app_config({
                "editor": req.model_dump()
            })
        )
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/config/save_instances")
async def save_instances(req: SavePresetsRequest):
    loop = asyncio.get_event_loop()
    key = f"{req.user}@{req.host}"
    instances_data = [i.dict() for i in req.instances]
    await loop.run_in_executor(
        None,
        lambda: config_manager.save_presets_config({
            "instance_presets": {
                key: instances_data
            }
        })
    )
    return {"status": "success"}
