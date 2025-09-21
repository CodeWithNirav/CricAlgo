from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
import os

router = APIRouter()

# serve index for admin SPA build
@router.get("/admin", response_class=HTMLResponse)
async def admin_index():
    index_path = os.path.join(os.path.dirname(__file__), "..", "static", "admin", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Admin UI not built</h1>", status_code=404)

# serve static assets for admin UI
@router.get("/assets/{filename}")
async def admin_assets(filename: str):
    assets_path = os.path.join(os.path.dirname(__file__), "..", "static", "admin", "assets", filename)
    if os.path.exists(assets_path):
        return FileResponse(assets_path)
    return HTMLResponse("<h1>Asset not found</h1>", status_code=404)
