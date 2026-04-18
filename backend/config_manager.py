"""
Unified configuration manager for three split config files:
  - ssh_config.json    : SSH connection credentials
  - presets_config.json: init_script and instance_presets
  - app_config.json    : server and viewer settings

On first load, automatically migrates legacy config.json if it exists.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# ── Resolve project root (two levels up from this file: backend/ -> project root)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)

SSH_CONFIG_FILE = os.path.join(_PROJECT_ROOT, "ssh_config.json")
PRESETS_CONFIG_FILE = os.path.join(_PROJECT_ROOT, "presets_config.json")
APP_CONFIG_FILE = os.path.join(_PROJECT_ROOT, "app_config.json")
LEGACY_CONFIG_FILE = os.path.join(_PROJECT_ROOT, "config.json")

# ── Default values ────────────────────────────────────────────────────────────

DEFAULT_SSH_CONFIG = {
    "host": "",
    "username": "",
    "password": ""
}

DEFAULT_PRESETS_CONFIG = {
    "init_script": "",
    "instance_presets": {}
}

_DEFAULT_TEXT_EXTENSIONS = [
    "txt", "md", "json", "js", "ts", "vue",
    "py", "java", "c", "cpp", "h", "hpp",
    "go", "rs", "rb", "php", "sh", "bash", "zsh",
    "yaml", "yml", "xml", "html", "css", "scss",
    "less", "sql", "log", "conf", "cfg", "ini",
    "properties", "out", "err", "csv",
    "gitignore", "dockerfile", "makefile", "gradle", "pom", "lock",
    "toml", "cu", "asm", "s", "v", "sv", "svh", "vh", "vhd", "vhdl",
    "jl", "lua", "r", "dart", "swift", "kt", "kts", "scala", "groovy",
    "matlab", "m", "sas", "spss", "stata", "rmd", "ipynb",
    "changelog", "license", "readme", "todo", "note", "copying",
    "job", "slurm", "sbatch"
]

DEFAULT_APP_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8000
    },
    "viewer": {
        "max_file_size": 2097152,  # 2 MB
        "text_extensions": _DEFAULT_TEXT_EXTENSIONS
    },
    "editor": {
        "theme": "vs",
        "fontSize": 14,
        "fontFamily": "monospace",
        "language": ""
    }
}


# ── Helper I/O ────────────────────────────────────────────────────────────────

def _read_json(path: str, default: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(default)


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _deep_merge(base: dict, override: dict) -> dict:
    """Shallow-merge override into a copy of base (one level deep for dicts)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = {**result[k], **v}
        else:
            result[k] = v
    return result


# ── Migration ─────────────────────────────────────────────────────────────────

def _migrate_legacy_config() -> None:
    """Split legacy config.json into three new files (runs once)."""
    if not os.path.exists(LEGACY_CONFIG_FILE):
        return
    # If all three new files already exist, skip migration
    if (os.path.exists(SSH_CONFIG_FILE) and
            os.path.exists(PRESETS_CONFIG_FILE) and
            os.path.exists(APP_CONFIG_FILE)):
        return

    logger.info("[CONFIG MIGRATE] Found legacy config.json — migrating to split files")
    try:
        with open(LEGACY_CONFIG_FILE, "r", encoding="utf-8") as f:
            legacy = json.load(f)
    except Exception as e:
        logger.warning(f"[CONFIG MIGRATE] Failed to read legacy config.json: {e}")
        return

    # ssh_config.json
    ssh_data = {
        "host": legacy.get("ssh", {}).get("host", ""),
        "username": legacy.get("ssh", {}).get("username", ""),
        "password": legacy.get("ssh", {}).get("password", "")
    }
    _write_json(SSH_CONFIG_FILE, ssh_data)

    # presets_config.json
    presets_data = {
        "init_script": legacy.get("init_script", ""),
        "instance_presets": legacy.get("instance_presets", {})
    }
    _write_json(PRESETS_CONFIG_FILE, presets_data)

    # app_config.json
    app_data = {
        "server": legacy.get("server", DEFAULT_APP_CONFIG["server"]),
        "viewer": legacy.get("viewer", DEFAULT_APP_CONFIG["viewer"])
    }
    _write_json(APP_CONFIG_FILE, app_data)

    logger.info("[CONFIG MIGRATE] Migration complete. Removing legacy config.json")
    try:
        os.remove(LEGACY_CONFIG_FILE)
    except Exception as e:
        logger.warning(f"[CONFIG MIGRATE] Could not remove legacy config.json: {e}")


# ── Public API ────────────────────────────────────────────────────────────────

def get_ssh_config() -> dict:
    """
    Return SSH config dict.
    Environment variables DASHBOARD_HOST, DASHBOARD_USERNAME, DASHBOARD_PASSWORD
    take precedence over stored values.
    """
    data = _read_json(SSH_CONFIG_FILE, DEFAULT_SSH_CONFIG)
    # Apply env var overrides
    if os.environ.get("DASHBOARD_HOST"):
        data["host"] = os.environ["DASHBOARD_HOST"]
    if os.environ.get("DASHBOARD_USERNAME"):
        data["username"] = os.environ["DASHBOARD_USERNAME"]
    if os.environ.get("DASHBOARD_PASSWORD"):
        data["password"] = os.environ["DASHBOARD_PASSWORD"]
    return data


def save_ssh_config(host: str, username: str, password: str) -> None:
    data = {"host": host, "username": username, "password": password}
    _write_json(SSH_CONFIG_FILE, data)


def get_presets_config() -> dict:
    return _deep_merge(DEFAULT_PRESETS_CONFIG, _read_json(PRESETS_CONFIG_FILE, DEFAULT_PRESETS_CONFIG))


def save_presets_config(update: dict) -> None:
    """
    update may contain any subset of keys:
      init_script, instance_presets (merged, not replaced)
    """
    current = get_presets_config()
    if "init_script" in update:
        current["init_script"] = update["init_script"]
    if "instance_presets" in update:
        current["instance_presets"].update(update["instance_presets"])
    _write_json(PRESETS_CONFIG_FILE, current)


def get_app_config() -> dict:
    """
    Return app config dict.
    SERVER_HOST / SERVER_PORT are read from environment variables
    SSH_JUPYTER_HOST / SSH_JUPYTER_PORT (legacy names kept for backward compat).
    """
    data = _deep_merge(DEFAULT_APP_CONFIG, _read_json(APP_CONFIG_FILE, DEFAULT_APP_CONFIG))
    # Apply env var overrides (keep legacy env var names for backward compat)
    if os.environ.get("SSH_JUPYTER_HOST"):
        data["server"]["host"] = os.environ["SSH_JUPYTER_HOST"]
    if os.environ.get("SSH_JUPYTER_PORT"):
        try:
            data["server"]["port"] = int(os.environ["SSH_JUPYTER_PORT"])
        except ValueError:
            pass
    return data


def save_app_config(update: dict) -> None:
    """
    update may contain any subset of keys: server, viewer
    """
    current = get_app_config()
    if "server" in update:
        current["server"].update(update["server"])
    if "viewer" in update:
        current["viewer"].update(update["viewer"])
    _write_json(APP_CONFIG_FILE, current)


def get_viewer_config() -> dict:
    return get_app_config().get("viewer", DEFAULT_APP_CONFIG["viewer"])


def get_presets(host: str, user: str) -> list:
    key = f"{user}@{host}"
    return get_presets_config()["instance_presets"].get(key, [])


def load_config_for_api() -> dict:
    """
    Return a combined dict in the shape expected by GET /api/config
    (backward-compatible with the legacy single-config format).
    """
    ssh = get_ssh_config()
    presets = get_presets_config()
    app = get_app_config()
    return {
        "ssh": {
            "host": ssh["host"],
            "username": ssh["username"],
            "password": ssh["password"]
        },
        "init_script": presets["init_script"],
        "instance_presets": presets["instance_presets"],
        "server": app["server"],
        "viewer": app["viewer"],
        "editor": app.get("editor", DEFAULT_APP_CONFIG["editor"])
    }


# ── Ensure files exist & run migration on import ──────────────────────────────

def _ensure_defaults() -> None:
    if not os.path.exists(SSH_CONFIG_FILE):
        _write_json(SSH_CONFIG_FILE, DEFAULT_SSH_CONFIG)
    if not os.path.exists(PRESETS_CONFIG_FILE):
        _write_json(PRESETS_CONFIG_FILE, DEFAULT_PRESETS_CONFIG)
    if not os.path.exists(APP_CONFIG_FILE):
        _write_json(APP_CONFIG_FILE, DEFAULT_APP_CONFIG)


# Run migration first, then ensure defaults for any missing files
_migrate_legacy_config()
_ensure_defaults()
