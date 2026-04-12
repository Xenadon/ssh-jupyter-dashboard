#!/usr/bin/env python3
"""
Launch script for SSH Jupyter Console.

Usage:
    python launch.py           # Use default port 8000
    python launch.py 8001      # Use custom port
"""

import os
import sys
import json
import uvicorn


def get_configured_port():
    """Get port from app_config.json, default to 8000."""
    config_path = os.path.join(os.path.dirname(__file__), "app_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("server", {}).get("port", 8000)
    return 8000


def main():
    # Priority: command line > config file > default 8000
    port = int(sys.argv[1]) if len(sys.argv) > 1 else get_configured_port()

    print(f"Starting SSH Jupyter Console on http://127.0.0.1:{port}")
    print(f"Press Ctrl+C to stop\n")

    uvicorn.run("backend.main:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
