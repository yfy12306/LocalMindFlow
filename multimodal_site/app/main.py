import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.routers import api_chat, base, history, pages, platform, tools
from app.database import engine, Base
from app.models.chat_record import ChatRecord
from app.models.agent_event import AgentEvent
from app.models.memory_item import MemoryItem
from app.models.session_state import SessionState

if hasattr(sys.stdout, "reconfigure"):
	sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
	sys.stderr.reconfigure(encoding="utf-8")

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_TITLE)

app.include_router(base.router)
app.include_router(pages.router)
app.include_router(platform.router)
app.include_router(api_chat.router)
app.include_router(history.router)
app.include_router(tools.router)

frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
frontend_assets = frontend_dist / "assets"

if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_assets)), name="frontend-assets")
