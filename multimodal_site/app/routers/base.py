from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get("/")
def home():
    return RedirectResponse(url="/pages/", status_code=307)

@router.get("/api")
def api_home():
    return {"message": "后端服务已启动"}

@router.get("/ping")
def ping():
    return {"status": "ok"}