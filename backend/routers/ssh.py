"""
SSH router — handles:
  WebSocket /ws/stream
  POST     /api/connect
  POST     /api/disconnect
  GET      /api/status
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.ssh_manager import ssh_session
from backend import config_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    hostname: str
    username: str
    password: str
    auth_code: str = "1"  # Default to '1' (Duo Push)
    init_script: str = ""


# ── WebSocket ──────────────────────────────────────────────────────────────────

@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    print("⚡ [WebSocket] Client Connected")

    async def receive_from_client():
        try:
            while True:
                data = await websocket.receive_text()
                ssh_session.send_shell_input(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️ [WebSocket RX Error]: {e}")

    async def send_to_client():
        try:
            while True:
                output = ssh_session.read_shell_output()
                if output:
                    await websocket.send_text(output)
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️ [WebSocket TX Error]: {e}")

    receiver = asyncio.create_task(receive_from_client())
    sender = asyncio.create_task(send_to_client())

    try:
        await asyncio.gather(receiver, sender)
    except (Exception, asyncio.CancelledError):
        pass
    finally:
        receiver.cancel()
        sender.cancel()
        await asyncio.gather(receiver, sender, return_exceptions=True)


# ── REST endpoints ─────────────────────────────────────────────────────────────

@router.post("/api/connect")
async def connect_ssh(req: ConnectRequest):
    # Singleton Check: If already connected to this user/host, skip SSH handshake
    if ssh_session.is_connected_to(req.hostname, req.username):
        print(f"✨ [API] Resuming existing session for {req.username}@{req.hostname}")
        saved_rows = config_manager.get_presets(req.hostname, req.username)
        return {
            "status": "success",
            "message": "Session Resumed",
            "saved_instances": saved_rows
        }

    # New connection
    success, msg = ssh_session.connect(
        req.hostname,
        req.username,
        req.password,
        req.auth_code,
        req.init_script
    )

    if success:
        # Persist SSH credentials
        config_manager.save_ssh_config(req.hostname, req.username, req.password)
        # Persist init_script
        config_manager.save_presets_config({"init_script": req.init_script})

        saved_rows = config_manager.get_presets(req.hostname, req.username)
        return {
            "status": "success",
            "message": "Connected",
            "saved_instances": saved_rows
        }
    else:
        return {"status": "error", "message": msg}


@router.post("/api/disconnect")
async def disconnect_ssh():
    try:
        ssh_session.close_all()
        return {"status": "success", "message": "Disconnected and cleaned up"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/status")
async def get_server_status():
    """
    Return current server state:
    - SSH connection status (connected, host, user)
    - Running Jupyter instances
    - Instance presets for the current session
    """
    ssh_connected = ssh_session.is_connected()

    presets = []
    if ssh_connected and ssh_session.current_host and ssh_session.current_user:
        presets = config_manager.get_presets(ssh_session.current_host, ssh_session.current_user)

    jupyter_instances = []
    if ssh_connected:
        for port, pid in ssh_session.jupyter_pids.items():
            jupyter_instances.append({
                "local_port": port,
                "pid": pid,
                "running": ssh_session.is_jupyter_running(port)
            })

    return {
        "status": "success",
        "ssh": {
            "connected": ssh_connected,
            "host": ssh_session.current_host,
            "user": ssh_session.current_user
        },
        "instance_presets": presets,
        "jupyter_instances": jupyter_instances
    }
