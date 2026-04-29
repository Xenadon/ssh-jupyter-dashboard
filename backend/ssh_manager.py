"""
SSH connection and Jupyter lifecycle management.
Identical in functionality to the original ssh_manager.py;
moved into the backend/ package.
"""

import paramiko
import threading
import socket
import time
import re
import select
import os
import stat
import logging
from typing import Optional, Callable, List, Dict, Any
from io import BytesIO

# Configure logger
logger = logging.getLogger(__name__)

class PortForwarder(threading.Thread):
    """处理本地端口转发到远程端口的线程"""
    def __init__(self, local_port, remote_port, transport):
        super().__init__()
        self.local_port = local_port
        self.remote_port = remote_port
        self.transport = transport
        self.stop_event = threading.Event()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('127.0.0.1', local_port))
        self.server_socket.listen(1)
        self.daemon = True

    def run(self):
        logger.info(f"[TUNNEL START] Listening on localhost:{self.local_port} -> remote:{self.remote_port}")
        connection_count = 0
        while not self.stop_event.is_set():
            try:
                self.server_socket.settimeout(1.0)
                local_conn, _ = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                remote_channel = self.transport.open_channel(
                    "direct-tcpip",
                    dest_addr=('127.0.0.1', self.remote_port),
                    src_addr=('127.0.0.1', self.local_port)
                )
            except Exception as e:
                logger.error(f"[TUNNEL ERROR] Failed to open remote channel: {e}")
                local_conn.close()
                continue

            if remote_channel is None:
                local_conn.close()
                continue

            connection_count += 1
            logger.debug(f"[TUNNEL] New connection #{connection_count} on port {self.local_port}")
            threading.Thread(target=self._forward, args=(local_conn, remote_channel)).start()
            threading.Thread(target=self._forward, args=(remote_channel, local_conn)).start()

        logger.info(f"[TUNNEL STOP] Stopped listening on port {self.local_port}")

    def _forward(self, source, dest):
        try:
            while not self.stop_event.is_set():
                data = source.recv(1024)
                if not data: break
                dest.send(data)
        except:
            pass
        finally:
            source.close()
            dest.close()

    def stop(self):
        logger.info(f"[TUNNEL STOP] Stopping tunnel on port {self.local_port}")
        self.stop_event.set()
        self.server_socket.close()

class SSHManager:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None
        self.transport = None
        self.active_tunnels = {}
        self.jupyter_pids = {}

        # Track current session identity
        self.current_host = None
        self.current_user = None

        # SFTP client instance
        self.sftp_client = None

    def is_connected_to(self, hostname, username):
        if (self.client and
            self.transport and
            self.transport.is_active() and
            self.current_host == hostname and
            self.current_user == username):
            return True
        return False

    def is_connected(self):
        """检查当前是否有活动的SSH连接"""
        return (
            self.client is not None and
            self.transport is not None and
            self.transport.is_active()
        )

    def is_jupyter_running(self, local_port):
        """检查指定端口的Jupyter是否仍在运行"""
        if local_port not in self.jupyter_pids:
            return False
        pid = self.jupyter_pids[local_port]
        try:
            stdin, stdout, stderr = self.client.exec_command(f"ps -p {pid} -o pid=")
            return stdout.read().strip() != ""
        except Exception:
            return False

    def connect(self, hostname, username, password, auth_code="1", init_script=""):

        # Singleton Check: If calling connect manually on an existing session, verify it's active
        if self.is_connected_to(hostname, username):
             logger.info(f"[SSH CONNECT] Resuming existing session for {username}@{hostname}")
             return True, "Session already active"

        logger.info(f"[SSH CONNECT START] Connecting to {hostname} as {username}...")

        # Clean up previous session if exists
        if self.transport:
            self.close_all()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(15)
            sock.connect((hostname, 22))

            t = paramiko.Transport(sock)
            t.start_client()

            def interactive_handler(title, instructions, prompt_list):
                answers = []
                for prompt_text, echo in prompt_list:
                    prompt_lower = prompt_text.lower()
                    logger.info(f"[SSH AUTH] Server prompt: {prompt_text.strip()}")

                    if "password" in prompt_lower:
                        answers.append(password)
                    elif "1-2" in prompt_lower or "option" in prompt_lower or "passcode" in prompt_lower:
                        logger.info(f"[SSH AUTH] Sending auth code: '{auth_code}'")
                        answers.append(auth_code)
                    else:
                        # Fallback
                        answers.append(password)
                return answers

            try:
                t.auth_interactive(username, interactive_handler)
            except paramiko.AuthenticationException:
                logger.info("[SSH AUTH] Falling back to password authentication")
                t.auth_password(username, password)

            if not t.is_authenticated():
                logger.error("[SSH CONNECT ERROR] Authentication failed")
                return False, "Authentication failed (Check Password or Duo)"

            logger.info("[SSH CONNECT] Authentication successful")

            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client._transport = t
            self.transport = t

            # Initialize SFTP client
            self.sftp_client = paramiko.SFTPClient.from_transport(t)
            logger.info("[SFTP CONNECT] SFTP client initialized")

            # Store session identity
            self.current_host = hostname
            self.current_user = username

            logger.info("[SSH CONNECT] Opening shell channel...")
            self.shell = self.client.invoke_shell(term='xterm')
            self.shell.setblocking(0)

            if init_script and init_script.strip():
                logger.info(f"[SSH CONNECT] Running init script: {init_script}")
                time.sleep(1)
                self.shell.send(init_script + "\n")

            logger.info(f"[SSH CONNECT COMPLETE] Connected to {hostname} as {username}")
            return True, "Connected"

        except Exception as e:
            logger.error(f"[SSH CONNECT ERROR] {e}")
            self.current_host = None
            self.current_user = None
            return False, str(e)

    def send_shell_input(self, text):
        if self.shell:
            logger.debug(f"[SSH SHELL] Sending input: {repr(text[:100])}...")
            self.shell.send(text)

    def read_shell_output(self):
        if self.shell and self.shell.recv_ready():
            raw_data = self.shell.recv(4096)
            try:
                decoded_data = raw_data.decode('utf-8', errors='ignore')
                logger.debug(f"[SSH SHELL] Received output: {len(decoded_data)} chars")
                return decoded_data
            except Exception as e:
                logger.error(f"[SSH SHELL ERROR] Decode error: {e}")
                return None
        return None

    def start_jupyter(self, work_dir, target_port=None, extra_options=""):
        if not self.shell:
             raise Exception("SSH Shell is not connected")

        logger.info(f"[JUPYTER START] Starting Jupyter in {work_dir}, target_port: {target_port}")
        remote_port = 0
        if target_port and str(target_port).isdigit():
            remote_port = int(target_port)
        else:
            find_port_cmd = "python3 -c \"import socket; s=socket.socket(); s.bind(('', 0)); print(s.getsockname()[1]); s.close()\""
            stdin, stdout, stderr = self.client.exec_command(find_port_cmd)
            out = stdout.read().decode().strip()
            if not out.isdigit():
                 raise Exception(f"Failed to find free port: {stderr.read().decode()}")
            remote_port = int(out)

        logger.info(f"[JUPYTER START] Remote port: {remote_port}")
        local_port = remote_port

        self.client.exec_command(f"fuser -k -n tcp {remote_port}")
        time.sleep(0.5)

        log_file = f"jupyter_{remote_port}.log"
        pid_file = f"jupyter_{remote_port}.pid"

        cmd = (
            f"cd {work_dir} \n"
            f"nohup jupyter lab --no-browser --port={remote_port} --ip=127.0.0.1 {extra_options} > {log_file} 2>&1 &\n"
            f"echo $! > {pid_file} \n"
            f"echo '--> Jupyter launched in background. PID saved to {pid_file}'\n"
        )

        logger.info(f"[JUPYTER START] Sending command to shell")
        self.shell.send(cmd + "\n")

        pid = None
        logger.info(f"[JUPYTER START] Waiting for PID file...")
        for _ in range(20):
            time.sleep(1)
            _, stdout, _ = self.client.exec_command(f"cat {work_dir}/{pid_file}")
            content = stdout.read().decode().strip()
            if content.isdigit():
                pid = content
                self.client.exec_command(f"rm {work_dir}/{pid_file}")
                break

        if not pid:
            _, stdout, _ = self.client.exec_command(f"cat {work_dir}/{log_file}")
            raise Exception(f"Failed to obtain PID. Check terminal for errors. Log tail: {stdout.read().decode().strip()}")

        self.jupyter_pids[local_port] = pid
        logger.info(f"[JUPYTER START] Started with PID: {pid}")

        if local_port in self.active_tunnels:
             self.active_tunnels[local_port].stop()

        tunnel = PortForwarder(local_port, remote_port, self.transport)
        tunnel.start()
        self.active_tunnels[local_port] = tunnel
        logger.info(f"[JUPYTER START] Port forwarding tunnel started: local:{local_port} -> remote:{remote_port}")

        token = None
        logger.info(f"[JUPYTER START] Waiting for token in log file...")

        for _ in range(20):
            time.sleep(1)
            check_cmd = f"grep -m 1 'token=' {work_dir}/{log_file}"
            _, stdout, _ = self.client.exec_command(check_cmd)
            output = stdout.read().decode().strip()

            match = re.search(r'token=([a-zA-Z0-9]+)', output)
            if match:
                token = match.group(1)
                self.client.exec_command(f"rm {work_dir}/{log_file}")
                break

        if not token:
            _, stdout, _ = self.client.exec_command(f"cat {work_dir}/{log_file}")
            raise Exception(f"Timeout waiting for token. Log content: {stdout.read().decode()}")

        logger.info(f"[JUPYTER START COMPLETE] local_port: {local_port}, pid: {pid}, token: {token[:8]}...")
        return {
            "local_port": local_port,
            "remote_port": remote_port,
            "pid": pid,
            "token": token,
            "url": f"http://localhost:{local_port}/lab?token={token}"
        }

    def stop_jupyter(self, local_port):
        logger.info(f"[JUPYTER STOP] Stopping Jupyter on port {local_port}")
        if local_port in self.active_tunnels:
            logger.info(f"[JUPYTER STOP] Stopping tunnel on port {local_port}")
            self.active_tunnels[local_port].stop()
            del self.active_tunnels[local_port]

        if local_port in self.jupyter_pids:
            pid = self.jupyter_pids[local_port]
            logger.info(f"[JUPYTER STOP] Killing process {pid}")
            self.client.exec_command(f"kill -9 {pid}")
            del self.jupyter_pids[local_port]
        logger.info(f"[JUPYTER STOP] Jupyter stopped on port {local_port}")

    def close_all(self):
        logger.info("[SSH CLOSE] Closing all connections...")
        for port in list(self.jupyter_pids.keys()):
            self.stop_jupyter(port)
        # Close SFTP client
        if self.sftp_client:
            self.sftp_client.close()
            self.sftp_client = None
            logger.info("[SFTP CLOSE] SFTP client closed")
        if self.client:
            self.client.close()
        self.current_host = None
        self.current_user = None
        logger.info("[SSH CLOSE] All connections closed")


    # ==================== SFTP Operations ====================

    def _expand_remote_path(self, path: str) -> str:
        """Expand path with environment variables to absolute path"""
        logger.info(f"[SFTP INTERNAL] _expand_remote_path - input: '{path}'")
        if not path:
            path = '/'

        # Use shell to expand path (handles ~ and $VAR)
        if path.startswith('~') or '$' in path:
            try:
                cmd = f'echo {path}'
                logger.info(f"[SSH EXEC] exec_command: {cmd}")
                stdin, stdout, stderr = self.client.exec_command(cmd)
                expanded = stdout.read().decode('utf-8').strip()
                err = stderr.read().decode('utf-8').strip()
                if expanded:
                    result = expanded.replace('\\', '/')
                    logger.info(f"[SFTP INTERNAL] _expand_remote_path - expanded result: '{result}'")
                    return result
            except Exception as e:
                logger.warning(f"[SFTP INTERNAL] _expand_remote_path - expansion error: {e}")
                pass

        # Fallback: ensure path starts with /
        result = path.replace('\\', '/')
        if not result.startswith('/'):
            result = '/' + result
        logger.info(f"[SFTP INTERNAL] _expand_remote_path - result: '{result}'")
        return result

    def sftp_list_dir(self, path: str) -> List[Dict[str, Any]]:
        """List directory contents with file info"""
        logger.info(f"[SFTP OPERATION START] list_dir - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] list_dir - SFTP client not initialized")
            raise Exception("SFTP client not initialized")

        items = []
        start_time = time.time()
        try:
            original_path = path
            path = path.replace('\\', '/')
            path = self._expand_remote_path(path)
            if not path:
                path = self.sftp_client.getcwd() or '/'

            # Get parent directory info for ".."
            if path != '/':
                parent_path = os.path.dirname(path) or '/'
                items.append({
                    'name': '..',
                    'path': parent_path,
                    'type': 'directory',
                    'size': 0,
                    'modified': 0,
                    'permissions': 'drwxr-xr-x'
                })

            logger.info(f"[SFTP INTERNAL] list_dir - listing: '{path}'")
            entries = self.sftp_client.listdir_attr(path)
            for entry in entries:
                entry_path = f"{path.rstrip('/')}/{entry.filename}"
                if stat.S_ISLNK(entry.st_mode):
                    try:
                        real = self.sftp_client.stat(entry_path)
                        target_type = 'directory' if stat.S_ISDIR(real.st_mode) else 'file'
                    except Exception:
                        target_type = 'broken'
                    items.append({
                        'name': entry.filename,
                        'path': entry_path,
                        'type': 'symlink',
                        'target_type': target_type,
                        'size': entry.st_size,
                        'modified': entry.st_mtime,
                        'permissions': stat.filemode(entry.st_mode) if hasattr(stat, 'filemode') else oct(entry.st_mode)[-3:]
                    })
                else:
                    entry_type = 'directory' if stat.S_ISDIR(entry.st_mode) else 'file'
                    items.append({
                        'name': entry.filename,
                        'path': entry_path,
                        'type': entry_type,
                        'size': entry.st_size,
                        'modified': entry.st_mtime,
                        'permissions': stat.filemode(entry.st_mode) if hasattr(stat, 'filemode') else oct(entry.st_mode)[-3:]
                    })

            # Sort: directories and dir-symlinks first, then by name
            def sort_key(x):
                is_dir = x['type'] == 'directory' or (x['type'] == 'symlink' and x.get('target_type') == 'directory')
                return (0 if is_dir else 1, x['name'].lower())
            items.sort(key=sort_key)
            elapsed = time.time() - start_time
            logger.info(f"[SFTP OPERATION COMPLETE] list_dir - {elapsed:.3f}s, {len(items)} items, path: '{path}'")
            return items, path
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[SFTP OPERATION ERROR] list_dir - {elapsed:.3f}s - {type(e).__name__}: {e}")
            raise Exception(f"Failed to list directory: {str(e)}")

    def sftp_expand_path(self, path: str) -> str:
        """Expand path to absolute path on remote server"""
        logger.info(f"[SFTP OPERATION START] expand_path - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] expand_path - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            result = self._expand_remote_path(path)
            logger.info(f"[SFTP OPERATION COMPLETE] expand_path - result: '{result}'")
            return result
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] expand_path - {e}")
            raise Exception(f"Failed to expand path: {str(e)}")

    def sftp_exists(self, path: str) -> bool:
        """Check if path exists"""
        logger.info(f"[SFTP OPERATION START] exists - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] exists - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            self.sftp_client.stat(path)
            logger.info(f"[SFTP OPERATION COMPLETE] exists - path: '{path}', result: True")
            return True
        except FileNotFoundError:
            logger.info(f"[SFTP OPERATION COMPLETE] exists - path: '{path}', result: False")
            return False

    def sftp_is_dir(self, path: str) -> bool:
        """Check if path is a directory"""
        logger.info(f"[SFTP OPERATION START] is_dir - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] is_dir - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            result = stat.S_ISDIR(self.sftp_client.stat(path).st_mode)
            logger.info(f"[SFTP OPERATION COMPLETE] is_dir - path: '{path}', result: {result}")
            return result
        except Exception as e:
            logger.info(f"[SFTP OPERATION COMPLETE] is_dir - path: '{path}', result: False (error: {e})")
            return False

    def sftp_read_file(self, path: str, offset: int = 0, length: int = -1) -> bytes:
        """Read file content"""
        logger.info(f"[SFTP OPERATION START] read_file - path: '{path}', offset: {offset}, length: {length}")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] read_file - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            with self.sftp_client.file(path, 'rb') as f:
                if offset > 0:
                    f.seek(offset)
                if length > 0:
                    data = f.read(length)
                else:
                    data = f.read()
            logger.info(f"[SFTP OPERATION COMPLETE] read_file - path: '{path}', bytes: {len(data)}")
            return data
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] read_file - path: '{path}' - {e}")
            raise Exception(f"Failed to read file: {str(e)}")

    def sftp_write_file(self, path: str, content: bytes, append: bool = False) -> None:
        """Write file content"""
        logger.info(f"[SFTP OPERATION START] write_file - path: '{path}', append: {append}, bytes: {len(content)}")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] write_file - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            mode = 'ab' if append else 'wb'
            with self.sftp_client.file(path, mode) as f:
                f.write(content)
            logger.info(f"[SFTP OPERATION COMPLETE] write_file - path: '{path}', bytes written: {len(content)}")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] write_file - path: '{path}' - {e}")
            raise Exception(f"Failed to write file: {str(e)}")

    def sftp_mkdir(self, path: str) -> None:
        """Create directory"""
        logger.info(f"[SFTP OPERATION START] mkdir - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] mkdir - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            self.sftp_client.mkdir(path)
            logger.info(f"[SFTP OPERATION COMPLETE] mkdir - path: '{path}'")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] mkdir - path: '{path}' - {e}")
            raise Exception(f"Failed to create directory: {str(e)}")

    def sftp_remove(self, path: str) -> None:
        """Remove file or directory"""
        logger.info(f"[SFTP OPERATION START] remove - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] remove - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            if self.sftp_is_dir(path):
                logger.info(f"[SFTP INTERNAL] remove - recursively removing directory: '{path}'")
                self._rmdir_recursive(path)
            else:
                self.sftp_client.remove(path)
            logger.info(f"[SFTP OPERATION COMPLETE] remove - path: '{path}'")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] remove - path: '{path}' - {e}")
            raise Exception(f"Failed to remove: {str(e)}")

    def _rmdir_recursive(self, path: str) -> None:
        """Recursively remove directory"""
        logger.info(f"[SFTP INTERNAL] _rmdir_recursive - removing: '{path}'")
        for entry in self.sftp_client.listdir_attr(path):
            entry_path = f"{path.rstrip('/')}/{entry.filename}"
            if stat.S_ISDIR(entry.st_mode):
                self._rmdir_recursive(entry_path)
            else:
                self.sftp_client.remove(entry_path)
        self.sftp_client.rmdir(path)
        logger.info(f"[SFTP INTERNAL] _rmdir_recursive - removed: '{path}'")

    def sftp_rename(self, old_path: str, new_path: str) -> None:
        """Rename/move file or directory"""
        logger.info(f"[SFTP OPERATION START] rename - from: '{old_path}', to: '{new_path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] rename - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            old_path = self._expand_remote_path(old_path)
            new_path = self._expand_remote_path(new_path)
            self.sftp_client.rename(old_path, new_path)
            logger.info(f"[SFTP OPERATION COMPLETE] rename - from: '{old_path}', to: '{new_path}'")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] rename - from: '{old_path}', to: '{new_path}' - {e}")
            raise Exception(f"Failed to rename: {str(e)}")

    def sftp_copy(self, src_path: str, dst_path: str) -> None:
        """Copy file or directory"""
        logger.info(f"[SFTP OPERATION START] copy - from: '{src_path}', to: '{dst_path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] copy - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            src_path = self._expand_remote_path(src_path)
            dst_path = self._expand_remote_path(dst_path)
            if self.sftp_is_dir(src_path):
                self._copy_dir_recursive(src_path, dst_path)
            else:
                self._copy_file(src_path, dst_path)
            logger.info(f"[SFTP OPERATION COMPLETE] copy - from: '{src_path}', to: '{dst_path}'")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] copy - from: '{src_path}', to: '{dst_path}' - {e}")
            raise Exception(f"Failed to copy: {str(e)}")

    def _copy_file(self, src_path: str, dst_path: str) -> None:
        """Copy a single file"""
        logger.info(f"[SFTP INTERNAL] _copy_file - from: '{src_path}', to: '{dst_path}'")
        total_bytes = 0
        with self.sftp_client.file(src_path, 'rb') as src:
            with self.sftp_client.file(dst_path, 'wb') as dst:
                while True:
                    chunk = src.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    dst.write(chunk)
                    total_bytes += len(chunk)
        logger.info(f"[SFTP INTERNAL] _copy_file - copied {total_bytes} bytes")

    def _copy_dir_recursive(self, src_path: str, dst_path: str) -> None:
        """Recursively copy directory"""
        logger.info(f"[SFTP INTERNAL] _copy_dir_recursive - from: '{src_path}', to: '{dst_path}'")
        self.sftp_client.mkdir(dst_path)
        for entry in self.sftp_client.listdir_attr(src_path):
            src_entry_path = f"{src_path.rstrip('/')}/{entry.filename}"
            dst_entry_path = f"{dst_path.rstrip('/')}/{entry.filename}"
            if stat.S_ISDIR(entry.st_mode):
                self._copy_dir_recursive(src_entry_path, dst_entry_path)
            else:
                self._copy_file(src_entry_path, dst_entry_path)
        logger.info(f"[SFTP INTERNAL] _copy_dir_recursive - completed: '{dst_path}'")

    def sftp_upload(self, local_path: str, remote_path: str) -> None:
        """Upload file from local to remote"""
        logger.info(f"[SFTP OPERATION START] upload - local: '{local_path}', remote: '{remote_path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] upload - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            remote_path = self._expand_remote_path(remote_path)
            self.sftp_client.put(local_path, remote_path)
            logger.info(f"[SFTP OPERATION COMPLETE] upload - remote: '{remote_path}'")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] upload - local: '{local_path}', remote: '{remote_path}' - {e}")
            raise Exception(f"Failed to upload: {str(e)}")

    def sftp_download(self, remote_path: str, local_path: str) -> None:
        """Download file from remote to local"""
        logger.info(f"[SFTP OPERATION START] download - remote: '{remote_path}', local: '{local_path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] download - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            remote_path = self._expand_remote_path(remote_path)
            self.sftp_client.get(remote_path, local_path)
            logger.info(f"[SFTP OPERATION COMPLETE] download - local: '{local_path}'")
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] download - remote: '{remote_path}' - {e}")
            raise Exception(f"Failed to download: {str(e)}")

    def sftp_get_file_size(self, path: str) -> int:
        """Get file size"""
        logger.info(f"[SFTP OPERATION START] get_file_size - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] get_file_size - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            size = self.sftp_client.stat(path).st_size
            logger.info(f"[SFTP OPERATION COMPLETE] get_file_size - path: '{path}', size: {size}")
            return size
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] get_file_size - path: '{path}' - {e}")
            raise Exception(f"Failed to get file size: {str(e)}")

    def sftp_get_file_info(self, path: str, text_extensions: list = None) -> dict:
        """Get file information including size, modified time, and text detection"""
        logger.info(f"[SFTP OPERATION START] get_file_info - path: '{path}'")
        if not self.sftp_client:
            logger.error("[SFTP OPERATION ERROR] get_file_info - SFTP client not initialized")
            raise Exception("SFTP client not initialized")
        try:
            path = self._expand_remote_path(path)
            stat_info = self.sftp_client.stat(path)

            ext = os.path.splitext(path)[1].lower().lstrip('.')

            if text_extensions is None:
                text_extensions = [
                    'txt', 'md', 'json', 'js', 'ts', 'vue',
                    'py', 'java', 'c', 'cpp', 'h', 'hpp',
                    'go', 'rs', 'rb', 'php', 'sh', 'bash', 'zsh',
                    'yaml', 'yml', 'xml', 'html', 'css', 'scss',
                    'less', 'sql', 'log', 'conf', 'cfg', 'ini',
                    'properties', 'out', 'err', 'csv',
                    'gitignore', 'dockerfile', 'makefile', 'gradle', 'pom', 'lock',
                    'toml', 'cu', 'asm', 's', 'v', 'sv', 'svh', 'vh', 'vhd', 'vhdl',
                    'jl', 'lua', 'r', 'dart', 'swift', 'kt', 'kts', 'scala', 'groovy',
                    'matlab', 'm', 'sas', 'spss', 'stata', 'rmd', 'ipynb',
                    'changelog', 'license', 'readme', 'todo', 'note', 'copying',
                    'job', 'slurm', 'sbatch'
                ]

            if ext in text_extensions:
                is_text = True
            else:
                # Unknown extension: check first 8KB for null bytes
                try:
                    with self.sftp_client.open(path, 'rb') as f:
                        chunk = f.read(8192)
                    is_text = b'\x00' not in chunk
                except Exception:
                    is_text = False

            mime_types = {
                'txt': 'text/plain',
                'md': 'text/markdown',
                'json': 'application/json',
                'js': 'application/javascript',
                'ts': 'application/typescript',
                'vue': 'text/html',
                'py': 'text/x-python',
                'java': 'text/x-java',
                'c': 'text/x-c',
                'cpp': 'text/x-c++',
                'h': 'text/x-c',
                'hpp': 'text/x-c++',
                'go': 'text/x-go',
                'rs': 'text/x-rust',
                'rb': 'text/x-ruby',
                'php': 'text/x-php',
                'sh': 'text/x-shellscript',
                'bash': 'text/x-shellscript',
                'zsh': 'text/x-shellscript',
                'yaml': 'text/yaml',
                'yml': 'text/yaml',
                'xml': 'text/xml',
                'html': 'text/html',
                'css': 'text/css',
                'scss': 'text/x-scss',
                'less': 'text/x-less',
                'sql': 'text/x-sql',
                'csv': 'text/csv',
                'log': 'text/plain',
                'ini': 'text/plain',
                'conf': 'text/plain',
                'cfg': 'text/plain',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'bmp': 'image/bmp',
                'svg': 'image/svg+xml',
                'pdf': 'application/pdf',
                'zip': 'application/zip',
                'tar': 'application/x-tar',
                'gz': 'application/gzip',
                'bz2': 'application/x-bzip2',
                '7z': 'application/x-7z-compressed',
                'rar': 'application/x-rar-compressed',
                'doc': 'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xls': 'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'ppt': 'application/vnd.ms-powerpoint',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            }
            mime_type = mime_types.get(ext, 'application/octet-stream')

            result = {
                'name': os.path.basename(path),
                'path': path,
                'size': stat_info.st_size,
                'modified': stat_info.st_mtime,
                'permissions': stat.filemode(stat_info.st_mode) if hasattr(stat, 'filemode') else oct(stat_info.st_mode)[-3:],
                'is_directory': stat.S_ISDIR(stat_info.st_mode),
                'is_text': is_text,
                'mime_type': mime_type,
                'extension': ext
            }
            logger.info(f"[SFTP OPERATION COMPLETE] get_file_info - path: '{path}', size: {stat_info.st_size}, is_dir: {stat.S_ISDIR(stat_info.st_mode)}")
            return result
        except Exception as e:
            logger.error(f"[SFTP OPERATION ERROR] get_file_info - path: '{path}' - {e}")
            raise Exception(f"Failed to get file info: {str(e)}")


ssh_session = SSHManager()
