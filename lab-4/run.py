"""Запуск локального FastAPI-сервера: python run.py."""

import os
import uvicorn
from common.config import ROOT

if __name__ == "__main__":
    uvicorn.run(
        "web_app.app:app",
        host=os.getenv("WEB_HOST", "127.0.0.1"),
        port=int(os.getenv("WEB_PORT", "8000")),
        app_dir=str(ROOT),
    )
