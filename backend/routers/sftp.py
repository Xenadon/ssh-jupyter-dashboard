"""
SFTP router — handles all /api/sftp/* endpoints.

Also contains:
  - SFTPRequestManager  (request cancellation for rapid navigation)
  - format_size         (human-readable byte sizes)
  - stream_file_generator (async streaming download helper)
"""

import asyncio
import base64
import logging
import os
import shutil
import tempfile
import time
from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.ssh_manager import ssh_session
from backend import config_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Utilities ──────────────────────────────────────────────────────────────────

def format_size(bytes: int) -> str:
    """Format bytes to human-readable string."""
    if bytes == 0:
        return '0 B'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = bytes
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.1f} {units[unit_index]}"


class SFTPRequestManager:
    """Manages ongoing SFTP requests to cancel previous ones when new requests arrive."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def run_with_cancel(self, request_type: str, coro) -> any:
        """Run a coroutine, cancelling any previous request of the same type."""
        start_time = time.time()
        logger.info(f"[SFTP REQUEST START] {request_type}")

        async with self._lock:
            if request_type in self._tasks:
                existing_task = self._tasks[request_type]
                if not existing_task.done():
                    logger.info(f"[SFTP REQUEST CANCEL] Cancelling previous {request_type} request")
                    existing_task.cancel()
                    try:
                        await existing_task
                    except asyncio.CancelledError:
                        pass

            task = asyncio.create_task(coro)
            self._tasks[request_type] = task

        try:
            result = await task
            elapsed = time.time() - start_time
            logger.info(f"[SFTP REQUEST COMPLETE] {request_type} - {elapsed:.3f}s")
            return result
        except asyncio.CancelledError:
            logger.info(f"[SFTP REQUEST CANCELLED] {request_type}")
            raise
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[SFTP REQUEST ERROR] {request_type} - {elapsed:.3f}s - {e}")
            raise
        finally:
            async with self._lock:
                if request_type in self._tasks and self._tasks[request_type] is task:
                    del self._tasks[request_type]


sftp_request_manager = SFTPRequestManager()


async def stream_file_generator(remote_path: str, chunk_size: int = 65536):
    """Async generator: downloads file via SFTP to a temp location then streams it."""
    logger.info(f"[SFTP STREAM START] download - path: {remote_path}, chunk_size: {chunk_size}")
    start_time = time.time()
    temp_dir = tempfile.mkdtemp()
    local_path = os.path.join(temp_dir, os.path.basename(remote_path))
    loop = asyncio.get_event_loop()

    try:
        logger.info(f"[SFTP OPERATION] download - remote: {remote_path}, local: {local_path}")
        await loop.run_in_executor(None, ssh_session.sftp_download, remote_path, local_path)

        total_bytes = 0
        with open(local_path, 'rb') as f:
            while True:
                chunk = await loop.run_in_executor(None, f.read, chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                yield chunk

        elapsed = time.time() - start_time
        logger.info(f"[SFTP STREAM COMPLETE] download - path: {remote_path}, bytes: {total_bytes}, time: {elapsed:.3f}s")
    finally:
        await loop.run_in_executor(None, shutil.rmtree, temp_dir, True)


# ── Request models ─────────────────────────────────────────────────────────────

class SFTPPathRequest(BaseModel):
    path: str


class SFTPRenameRequest(BaseModel):
    old_path: str
    new_path: str


class SFTPMoveRequest(BaseModel):
    src_paths: List[str]
    dst_path: str


class SFTPReadRequest(BaseModel):
    path: str
    offset: int = 0
    length: int = -1
    max_size: int = 0       # 0 means no limit
    check_size: bool = False  # If True, check file size before reading


class SFTPWriteRequest(BaseModel):
    path: str
    content: str
    append: bool = False


class SFTPExistsRequest(BaseModel):
    path: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/api/sftp/list")
async def sftp_list(req: SFTPPathRequest):
    """List directory contents — cancels previous list requests."""
    logger.info(f"[API REQUEST] POST /api/sftp/list - path: {req.path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        async def do_list():
            logger.info(f"[SFTP OPERATION] list_dir - path: {req.path}")
            items, expanded_path = await loop.run_in_executor(None, ssh_session.sftp_list_dir, req.path)
            return {"status": "success", "items": items, "current_path": expanded_path}

        result = await sftp_request_manager.run_with_cancel("list", do_list())
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/list - {elapsed:.3f}s - items: {len(result.get('items', [])) if isinstance(result, dict) else 'N/A'}")
        return result
    except asyncio.CancelledError:
        elapsed = time.time() - start_time
        logger.info(f"[API CANCELLED] POST /api/sftp/list - {elapsed:.3f}s")
        return {"status": "cancelled", "message": "Request was cancelled by a newer request"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/list - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/expand")
async def sftp_expand(req: SFTPPathRequest):
    """Expand path to absolute path — cancels previous expand requests."""
    logger.info(f"[API REQUEST] POST /api/sftp/expand - path: {req.path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        async def do_expand():
            logger.info(f"[SFTP OPERATION] expand_path - path: {req.path}")
            expanded_path = await loop.run_in_executor(None, ssh_session.sftp_expand_path, req.path)
            return {"status": "success", "expanded_path": expanded_path}

        result = await sftp_request_manager.run_with_cancel("expand", do_expand())
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/expand - {elapsed:.3f}s")
        return result
    except asyncio.CancelledError:
        elapsed = time.time() - start_time
        logger.info(f"[API CANCELLED] POST /api/sftp/expand - {elapsed:.3f}s")
        return {"status": "cancelled", "message": "Request was cancelled by a newer request"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/expand - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/exists")
async def sftp_exists(req: SFTPExistsRequest):
    """Check if path exists — cancels previous exists requests."""
    logger.info(f"[API REQUEST] POST /api/sftp/exists - path: {req.path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        async def do_exists():
            logger.info(f"[SFTP OPERATION] exists - path: {req.path}")
            exists = await loop.run_in_executor(None, ssh_session.sftp_exists, req.path)
            is_dir = await loop.run_in_executor(None, ssh_session.sftp_is_dir, req.path) if exists else False
            return {"status": "success", "exists": exists, "is_dir": is_dir}

        result = await sftp_request_manager.run_with_cancel("exists", do_exists())
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/exists - {elapsed:.3f}s")
        return result
    except asyncio.CancelledError:
        elapsed = time.time() - start_time
        logger.info(f"[API CANCELLED] POST /api/sftp/exists - {elapsed:.3f}s")
        return {"status": "cancelled", "message": "Request was cancelled by a newer request"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/exists - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/read")
async def sftp_read(req: SFTPReadRequest):
    """Read file content (text or binary)."""
    logger.info(f"[API REQUEST] POST /api/sftp/read - path: {req.path}, offset: {req.offset}, length: {req.length}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        if req.check_size and req.max_size > 0:
            logger.info(f"[SFTP OPERATION] get_file_size - path: {req.path}")
            file_size = await loop.run_in_executor(None, ssh_session.sftp_get_file_size, req.path)
            if file_size > req.max_size:
                elapsed = time.time() - start_time
                logger.warning(f"[API COMPLETE] POST /api/sftp/read - {elapsed:.3f}s - FILE_TOO_LARGE")
                return {
                    "status": "error",
                    "code": "FILE_TOO_LARGE",
                    "size": file_size,
                    "max_size": req.max_size,
                    "message": f"File size ({format_size(file_size)}) exceeds maximum ({format_size(req.max_size)})"
                }

        logger.info(f"[SFTP OPERATION] read_file - path: {req.path}, offset: {req.offset}, length: {req.length}")
        content = await loop.run_in_executor(
            None, lambda: ssh_session.sftp_read_file(req.path, req.offset, req.length)
        )
        try:
            text_content = content.decode('utf-8')
            elapsed = time.time() - start_time
            logger.info(f"[API COMPLETE] POST /api/sftp/read - {elapsed:.3f}s - text, length: {len(text_content)}")
            return {"status": "success", "content": text_content, "is_binary": False}
        except UnicodeDecodeError:
            elapsed = time.time() - start_time
            logger.info(f"[API COMPLETE] POST /api/sftp/read - {elapsed:.3f}s - binary, length: {len(content)}")
            return {"status": "success", "content": base64.b64encode(content).decode(), "is_binary": True}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/read - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/file-info")
async def sftp_file_info(req: SFTPPathRequest):
    """Get file information including size, type, and text detection."""
    logger.info(f"[API REQUEST] POST /api/sftp/file-info - path: {req.path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        viewer_config = await loop.run_in_executor(None, config_manager.get_viewer_config)
        text_extensions = viewer_config.get('text_extensions', [])

        logger.info(f"[SFTP OPERATION] get_file_info - path: {req.path}")
        file_info = await loop.run_in_executor(
            None, lambda: ssh_session.sftp_get_file_info(req.path, text_extensions)
        )

        file_info['viewer_config'] = {
            'max_file_size': viewer_config.get('max_file_size', 2097152)
        }

        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/file-info - {elapsed:.3f}s")
        return {"status": "success", **file_info}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/file-info - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/download")
async def sftp_download_post(path: str = Form(...)):
    """Download file from remote server (streamed) — POST form."""
    logger.info(f"[API REQUEST] POST /api/sftp/download - path: {path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        logger.info(f"[SFTP OPERATION] get_file_info - path: {path}")
        file_info = await loop.run_in_executor(
            None, lambda: ssh_session.sftp_get_file_info(path)
        )

        filename = file_info['name']
        mime_type = file_info.get('mime_type', 'application/octet-stream')

        inline_types = ['text/', 'image/', 'application/pdf']
        disposition = 'inline' if any(mime_type.startswith(t) for t in inline_types) else 'attachment'

        logger.info(f"[API STREAMING] POST /api/sftp/download - {filename} ({mime_type})")
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/download - setup {elapsed:.3f}s")
        return StreamingResponse(
            stream_file_generator(path),
            media_type=mime_type,
            headers={'Content-Disposition': f'{disposition}; filename="{filename}"'}
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/download - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sftp/download")
async def sftp_download_get(path: str):
    """Download file from remote server via GET (for direct browser access)."""
    logger.info(f"[API REQUEST] GET /api/sftp/download - path: {path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()

        logger.info(f"[SFTP OPERATION] get_file_info - path: {path}")
        file_info = await loop.run_in_executor(
            None, lambda: ssh_session.sftp_get_file_info(path)
        )

        filename = file_info['name']
        mime_type = file_info.get('mime_type', 'application/octet-stream')

        inline_types = ['text/', 'image/', 'application/pdf']
        disposition = 'inline' if any(mime_type.startswith(t) for t in inline_types) else 'attachment'

        logger.info(f"[API STREAMING] GET /api/sftp/download - {filename} ({mime_type})")
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] GET /api/sftp/download - setup {elapsed:.3f}s")
        return StreamingResponse(
            stream_file_generator(path),
            media_type=mime_type,
            headers={'Content-Disposition': f'{disposition}; filename="{filename}"'}
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] GET /api/sftp/download - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/sftp/download/{filename}")
async def sftp_download_with_name(filename: str, path: str):
    """Download file with filename in URL path (for better browser tab title).

    The filename parameter is cosmetic - the actual file path comes from query parameter.
    """
    # Simply delegate to the existing download handler
    return await sftp_download_get(path)


@router.post("/api/sftp/write")
async def sftp_write(req: SFTPWriteRequest):
    """Write content to file."""
    logger.info(f"[API REQUEST] POST /api/sftp/write - path: {req.path}, append: {req.append}, bytes: {len(req.content)}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        content_bytes = req.content.encode('utf-8')
        logger.info(f"[SFTP OPERATION] write_file - path: {req.path}, append: {req.append}, bytes: {len(content_bytes)}")
        await loop.run_in_executor(
            None, lambda: ssh_session.sftp_write_file(req.path, content_bytes, req.append)
        )
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/write - {elapsed:.3f}s")
        return {"status": "success"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/write - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/mkdir")
async def sftp_mkdir(req: SFTPPathRequest):
    """Create directory."""
    logger.info(f"[API REQUEST] POST /api/sftp/mkdir - path: {req.path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        logger.info(f"[SFTP OPERATION] mkdir - path: {req.path}")
        await loop.run_in_executor(None, ssh_session.sftp_mkdir, req.path)
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/mkdir - {elapsed:.3f}s")
        return {"status": "success"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/mkdir - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/remove")
async def sftp_remove(req: SFTPPathRequest):
    """Remove file or directory."""
    logger.info(f"[API REQUEST] POST /api/sftp/remove - path: {req.path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        logger.info(f"[SFTP OPERATION] remove - path: {req.path}")
        await loop.run_in_executor(None, ssh_session.sftp_remove, req.path)
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/remove - {elapsed:.3f}s")
        return {"status": "success"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/remove - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/rename")
async def sftp_rename(req: SFTPRenameRequest):
    """Rename/move file or directory."""
    logger.info(f"[API REQUEST] POST /api/sftp/rename - from: {req.old_path}, to: {req.new_path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        logger.info(f"[SFTP OPERATION] rename - from: {req.old_path}, to: {req.new_path}")
        await loop.run_in_executor(
            None, lambda: ssh_session.sftp_rename(req.old_path, req.new_path)
        )
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/rename - {elapsed:.3f}s")
        return {"status": "success"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/rename - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/copy")
async def sftp_copy(req: SFTPRenameRequest):
    """Copy file or directory."""
    logger.info(f"[API REQUEST] POST /api/sftp/copy - from: {req.old_path}, to: {req.new_path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        logger.info(f"[SFTP OPERATION] copy - from: {req.old_path}, to: {req.new_path}")
        await loop.run_in_executor(
            None, lambda: ssh_session.sftp_copy(req.old_path, req.new_path)
        )
        elapsed = time.time() - start_time
        logger.info(f"[API COMPLETE] POST /api/sftp/copy - {elapsed:.3f}s")
        return {"status": "success"}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/copy - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/move")
async def sftp_move(req: SFTPMoveRequest):
    """Move multiple files to destination directory."""
    logger.info(f"[API REQUEST] POST /api/sftp/move - files: {len(req.src_paths)}, to: {req.dst_path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        results = []
        for src_path in req.src_paths:
            filename = os.path.basename(src_path)
            dst_full_path = os.path.join(req.dst_path, filename).replace('\\', '/')
            try:
                logger.info(f"[SFTP OPERATION] move - from: {src_path}, to: {dst_full_path}")
                await loop.run_in_executor(
                    None, lambda s=src_path, d=dst_full_path: ssh_session.sftp_rename(s, d)
                )
                results.append({"src": src_path, "dst": dst_full_path, "status": "success"})
            except Exception as e:
                results.append({"src": src_path, "dst": dst_full_path, "status": "error", "message": str(e)})
        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"[API COMPLETE] POST /api/sftp/move - {elapsed:.3f}s - {success_count}/{len(req.src_paths)} succeeded")
        return {"status": "success", "results": results}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/move - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/sftp/upload")
async def sftp_upload(
    file: UploadFile = File(...),
    path: str = Form(...),
    filename: Optional[str] = Form(None)
):
    """Upload file to remote server."""
    target_filename = filename or file.filename
    logger.info(f"[API REQUEST] POST /api/sftp/upload - filename: {target_filename}, path: {path}")
    start_time = time.time()
    try:
        loop = asyncio.get_event_loop()
        remote_path = os.path.join(path, target_filename).replace('\\', '/')

        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, target_filename)

        try:
            with open(temp_path, 'wb') as f:
                content = await file.read()
                f.write(content)
                logger.info(f"[UPLOAD TEMP] Saved {len(content)} bytes to temp file")

            logger.info(f"[SFTP OPERATION] upload - local: {temp_path}, remote: {remote_path}")
            await loop.run_in_executor(
                None, lambda: ssh_session.sftp_upload(temp_path, remote_path)
            )

            elapsed = time.time() - start_time
            logger.info(f"[API COMPLETE] POST /api/sftp/upload - {elapsed:.3f}s - {remote_path}")
            return {"status": "success", "path": remote_path}
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API ERROR] POST /api/sftp/upload - {elapsed:.3f}s - {e}")
        return {"status": "error", "message": str(e)}
