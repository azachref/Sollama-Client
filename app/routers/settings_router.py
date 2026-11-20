import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.database import get_db, get_all_settings, set_multiple_settings, set_setting
from app.ollama_client import OllamaClient

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class SettingsUpdatePayload(BaseModel):
    settings: Dict[str, Any]

class TestOllamaPayload(BaseModel):
    url: Optional[str] = None

@router.get("/")
async def get_settings():
    return get_all_settings()

@router.post("/")
async def update_settings(payload: SettingsUpdatePayload):
    set_multiple_settings(payload.settings)
    return {"success": True, "settings": get_all_settings()}

@router.post("/test-ollama")
async def test_ollama(payload: Optional[TestOllamaPayload] = None):
    if payload and payload.url:
        set_setting("ollama_base_url", payload.url)
    return await OllamaClient.check_health()

@router.get("/ollama-models")
async def get_ollama_models():
    return await OllamaClient.list_models()

@router.post("/clear-history")
async def clear_all_history():
    """Wipe all chats and message history."""
    conn = get_db()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM chats")
    conn.commit()
    conn.close()
    return {"success": True, "message": "All chat history cleared"}

@router.get("/export-chats")
async def export_chats():
    """Export all chats, messages, and artifacts as JSON."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM chats")
    chats = [dict(c) for c in cursor.fetchall()]

    cursor.execute("SELECT * FROM messages")
    messages = [dict(m) for m in cursor.fetchall()]

    cursor.execute("SELECT * FROM artifacts")
    artifacts = [dict(a) for a in cursor.fetchall()]

    cursor.execute("SELECT * FROM projects")
    projects = [dict(p) for p in cursor.fetchall()]

    cursor.execute("SELECT * FROM characters")
    characters = [dict(ch) for ch in cursor.fetchall()]

    conn.close()

    return {
        "exported_at": datetime.now().isoformat(),
        "version": "1.0",
        "chats": chats,
        "messages": messages,
        "artifacts": artifacts,
        "projects": projects,
        "characters": characters
    }

@router.post("/import-chats")
async def import_chats(file: UploadFile = File(...)):
    """Import previously exported chats JSON."""
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        conn = get_db()

        for c in data.get("chats", []):
            conn.execute("""
                INSERT OR REPLACE INTO chats (id, project_id, character_id, title, is_incognito, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (c["id"], c.get("project_id"), c.get("character_id"), c["title"], c.get("is_incognito", 0), c["created_at"], c["updated_at"]))

        for m in data.get("messages", []):
            conn.execute("""
                INSERT OR REPLACE INTO messages (id, chat_id, role, content, thinking, images_json, tools_used_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (m["id"], m["chat_id"], m["role"], m["content"], m.get("thinking", ""), m.get("images_json", "[]"), m.get("tools_used_json", "[]"), m["created_at"]))

        for a in data.get("artifacts", []):
            conn.execute("""
                INSERT OR REPLACE INTO artifacts (id, chat_id, title, language, code, description, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (a["id"], a.get("chat_id"), a["title"], a["language"], a["code"], a.get("description", ""), a.get("version", 1), a["created_at"], a["updated_at"]))

        conn.commit()
        conn.close()
        return {"success": True, "message": "Data imported successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import error: {str(e)}")
