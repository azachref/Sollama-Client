import os
import socket
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import BASE_DIR, DATA_DIR, APP_NAME, APP_VERSION
from app.database import init_db
from app.routers import (
    chat_router,
    projects_router,
    characters_router,
    imagine_router,
    artifacts_router,
    extensions_router,
    settings_router,
    sandbox_router
)

# Initialize application
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Modern, feature-rich Ollama Client with Big-Tech Chatbot UI, Tools, SD Forge Neo, ZIM offline, and Code Sandboxing"
)

# CORS middleware for local network access (e.g. mobile phone access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
static_path = BASE_DIR / "static"
templates_path = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory=str(templates_path))

# Include routers
app.include_router(chat_router.router)
app.include_router(projects_router.router)
app.include_router(characters_router.router)
app.include_router(imagine_router.router)
app.include_router(artifacts_router.router)
app.include_router(extensions_router.router)
app.include_router(settings_router.router)
app.include_router(sandbox_router.router)

# Ensure database is initialized immediately
init_db()

@app.on_event("startup")
async def on_startup():
    init_db()

@app.get("/")
async def root_view(request: Request):
    """Serve the single-page application."""
    return templates.TemplateResponse(request=request, name="index.html", context={"app_name": APP_NAME, "version": APP_VERSION})

def get_local_ip():
    """Get the local network IP address for convenient mobile browsing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    print("=" * 65)
    print(f"  🚀  {APP_NAME} v{APP_VERSION} is starting!")
    print(f"  💻  Desktop URL:  http://localhost:{port}")
    print(f"  📱  Mobile URL:   http://{local_ip}:{port}")
    print("=" * 65)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
