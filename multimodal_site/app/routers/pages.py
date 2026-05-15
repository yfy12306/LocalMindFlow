from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

from app.core.config import settings


router = APIRouter(prefix="/pages", tags=["pages"])

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"

@router.get("/")
def home(request: Request):
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>{settings.APP_TITLE}</title>
            <style>
              body {{
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                background: #0f1116;
                color: #f5f0e8;
                font-family: "Segoe UI", "PingFang SC", sans-serif;
              }}
              .card {{
                width: min(680px, calc(100vw - 48px));
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 24px;
                padding: 32px;
                background: rgba(255,255,255,0.04);
              }}
              code {{
                display: inline-block;
                margin-top: 12px;
                padding: 8px 12px;
                border-radius: 999px;
                background: rgba(255,255,255,0.08);
              }}
            </style>
          </head>
          <body>
            <div class="card">
              <h1>Frontend build not found</h1>
              <p>{settings.APP_SUBTITLE}</p>
              <code>cd frontend && npm install && npm run build</code>
            </div>
          </body>
        </html>
        """
    )
