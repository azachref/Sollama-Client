from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.config import ZIM_DIR
from app.database import get_all_settings, set_setting, set_multiple_settings
from app.extensions.wikipedia_tool import WikipediaTool
from app.extensions.open_meteo_tool import OpenMeteoTool
from app.extensions.searxng_tool import SearXNGTool
from app.extensions.duckduckgo_tool import DuckDuckGoTool
from app.extensions.open_library_tool import OpenLibraryTool
from app.extensions.zim_tool import ZimTool, ZimDownloadManager, CURATED_ZIM_CATALOG

router = APIRouter(prefix="/api/extensions", tags=["Extensions"])

class ExtensionConfigPayload(BaseModel):
    ext_auto_route: Optional[bool] = None
    ext_wikipedia_enabled: Optional[bool] = None
    ext_open_meteo_enabled: Optional[bool] = None
    ext_searxng_enabled: Optional[bool] = None
    ext_searxng_url: Optional[str] = None
    ext_ddgs_enabled: Optional[bool] = None
    ext_open_library_enabled: Optional[bool] = None
    ext_zim_enabled: Optional[bool] = None
    ext_zim_api_url: Optional[str] = None
    active_zim_filename: Optional[str] = None

class TestExtensionRequest(BaseModel):
    tool_name: str
    query: str

@router.get("/config")
async def get_extensions_config():
    settings = get_all_settings()
    installed_zims = ZimTool.get_installed_zims()

    return {
        "ext_auto_route": settings.get("ext_auto_route", True),
        "ext_wikipedia_enabled": settings.get("ext_wikipedia_enabled", True),
        "ext_open_meteo_enabled": settings.get("ext_open_meteo_enabled", True),
        "ext_searxng_enabled": settings.get("ext_searxng_enabled", True),
        "ext_searxng_url": settings.get("ext_searxng_url", "http://192.168.1.101:8080"),
        "ext_ddgs_enabled": settings.get("ext_ddgs_enabled", True),
        "ext_open_library_enabled": settings.get("ext_open_library_enabled", True),
        "ext_zim_enabled": settings.get("ext_zim_enabled", True),
        "ext_zim_api_url": settings.get("ext_zim_api_url", "http://127.0.0.1:8080"),
        "active_zim_filename": settings.get("active_zim_filename", ""),
        "installed_zims": installed_zims,
        "installed_zims_count": len(installed_zims)
    }

@router.post("/config")
async def update_extensions_config(payload: ExtensionConfigPayload):
    updates = {}
    for k, v in payload.model_dump().items():
        if v is not None:
            updates[k] = v
    if updates:
        set_multiple_settings(updates)
    return {"success": True, "updated": updates}

@router.post("/test")
async def test_extension(payload: TestExtensionRequest):
    """Test individual extension with custom query."""
    tool = payload.tool_name.lower()
    q = payload.query.strip()
    settings = get_all_settings()

    if tool == "open_meteo":
        return OpenMeteoTool.get_weather(q or "London")
    elif tool == "wikipedia":
        return WikipediaTool.search_and_summary(q or "Python (programming language)")
    elif tool == "searxng":
        url = settings.get("ext_searxng_url", "http://192.168.1.101:8080")
        return SearXNGTool.search(url, q or "open source AI")
    elif tool == "ddgs":
        return DuckDuckGoTool.search(q or "Python programming")
    elif tool == "open_library":
        return OpenLibraryTool.search_books(q or "Sherlock Holmes")
    elif tool == "zim":
        api_url = settings.get("ext_zim_api_url", "")
        return ZimTool.search_offline(q or "Solar System", api_url=api_url)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown extension '{tool}'")

# --- ZIM Catalog & Downloads ---

@router.get("/zim/catalog")
async def get_zim_catalog():
    """Retrieve catalog of ZIM dumps, their exact sizes, and current installation status."""
    installed = {item["filename"]: item for item in ZimTool.get_installed_zims()}
    active_downloads = ZimDownloadManager.get_all_statuses()

    result = []
    for item in CURATED_ZIM_CATALOG:
        entry = dict(item)
        is_installed = item["filename"] in installed
        entry["is_installed"] = is_installed
        if is_installed:
            entry["local_path"] = installed[item["filename"]]["path"]
        
        # Check download status
        dl_status = active_downloads.get(item["id"], {"status": "idle", "percent": 0})
        entry["download_status"] = dl_status
        result.append(entry)

    return result

@router.get("/zim/installed")
async def get_installed_zims():
    return ZimTool.get_installed_zims()

@router.post("/zim/download/{item_id}")
async def start_zim_download(item_id: str):
    res = ZimDownloadManager.start_download(item_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@router.post("/zim/cancel/{item_id}")
async def cancel_zim_download(item_id: str):
    ZimDownloadManager.cancel_download(item_id)
    return {"success": True, "message": "Cancel requested"}

@router.get("/zim/status")
async def get_all_zim_statuses():
    return ZimDownloadManager.get_all_statuses()

@router.delete("/zim/file/{filename}")
async def delete_zim_file(filename: str):
    target = ZIM_DIR / filename
    if target.exists():
        try:
            target.unlink()
            return {"success": True, "message": f"Deleted {filename}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="ZIM file not found")
