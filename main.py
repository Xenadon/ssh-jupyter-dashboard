from backend.main import app  # noqa: F401

# This shim allows `uvicorn main:app` (or `uv run uvicorn main:app`) to work
# from the project root without any path manipulation.
