from pathlib import Path
import logging
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.middleware_auth import AuthMiddleware
from app.routers import router

log = logging.getLogger(__name__)

app = FastAPI(title="Holzlinge Inventar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.include_router(router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _imap_poll_loop() -> None:
    from app.config import settings
    from app.etsy_mail import fetch_new_mails_standalone, imap_configured

    hours = float(settings.imap_poll_hours or 6.0)
    if hours < 1:
        hours = 1.0
    interval = int(hours * 3600)
    # Erster Lauf erst nach Intervall (Knopf holt bei Bedarf sofort)
    while True:
        time.sleep(interval)
        if not imap_configured():
            continue
        try:
            result = fetch_new_mails_standalone()
            fetched = int(result.get("fetched") or 0)
            if fetched:
                log.info("IMAP Auto-Abruf: %s neue Mail(s)", fetched)
        except Exception:
            log.exception("IMAP Auto-Abruf fehlgeschlagen")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    from app.etsy_mail import imap_configured

    if imap_configured():
        threading.Thread(target=_imap_poll_loop, name="imap-poll", daemon=True).start()
        log.info("IMAP Auto-Abruf gestartet")


if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
