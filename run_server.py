from pathlib import Path

import uvicorn


if __name__ == "__main__":
    log_path = Path("backend/data/server.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Starting Noesis server on http://127.0.0.1:8000\n", encoding="utf-8")
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True,
    )
