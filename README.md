# SSH Jupyter Console

A browser-based dashboard for managing remote Jupyter Lab instances over SSH. Connect to HPC clusters or remote servers, launch Jupyter with port forwarding, browse files, and edit code — all from one tab.

## Features

- **SSH connection** with Duo 2FA support (keyboard-interactive)
- **Jupyter Lab management** — start/stop instances, automatic port forwarding, per-host presets
- **Browser terminal** — full xterm.js terminal over WebSocket
- **Remote file browser** — list, upload, download, rename, copy, move, drag-and-drop
- **Code editor** — Monaco Editor with syntax highlighting, theme/font/language selection, persisted settings

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) or pip

> Node.js is only required if you want to modify and rebuild the frontend. The pre-built frontend is included in the repository.

## Setup

### 1. Install backend dependencies

**Using uv (recommended):**
```bash
uv sync
```

**Using pip:**
```bash
pip install -r requirements.txt
```

### 2. Configure SSH credentials

Copy the example and fill in your details:

```bash
cp ssh_config.example.json ssh_config.json
```

`ssh_config.json`:
```json
{
    "host": "your-server.example.com",
    "username": "your_username",
    "password": "your_password"
}
```

Alternatively, use environment variables (no config file needed):

```bash
export DASHBOARD_HOST=your-server.example.com
export DASHBOARD_USERNAME=your_username
export DASHBOARD_PASSWORD=your_password
```

### 3. Start

**Quick start (recommended):**
```bash
# Use default port 8000
uv run launch.py

# Or specify a custom port
uv run launch.py 8001
```

The launch script automatically synchronizes the port configuration and starts the backend. Open `http://localhost:8000` (or your custom port) in your browser.

**Manual start (alternative):**
```bash
# Using uv
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# Using pip
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuration Files

All configs are auto-created with defaults on first run.

| File | Contents |
|------|----------|
| `ssh_config.json` | SSH host, username, password |
| `presets_config.json` | Init script, per-host Jupyter instance presets |
| `app_config.json` | Server bind address, file viewer settings, editor preferences |

> **Note**: `ssh_config.json` contains plaintext credentials. Do not commit it to version control.

## Developing the Frontend

Node.js 18+ is required to modify and rebuild the frontend.

```bash
cd frontend
npm install
npm run build
```

Commit the updated `frontend/dist/` so others can use it without Node.
