import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db

router = APIRouter(prefix="/api/characters", tags=["Characters"])

class CreateCharacterPayload(BaseModel):
    name: str
    avatar: Optional[str] = "🤖"
    description: Optional[str] = ""
    system_prompt: str
    default_model: Optional[str] = ""
    temperature: Optional[float] = 0.7

class UpdateCharacterPayload(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    default_model: Optional[str] = None
    temperature: Optional[float] = None

@router.get("/list")
async def list_characters():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM characters ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/create")
async def create_character(payload: CreateCharacterPayload):
    char_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO characters (id, name, avatar, description, system_prompt, default_model, temperature, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        char_id,
        payload.name,
        payload.avatar or "🤖",
        payload.description or "",
        payload.system_prompt,
        payload.default_model or "",
        payload.temperature if payload.temperature is not None else 0.7,
        now
    ))
    conn.commit()
    conn.close()
    return {"id": char_id, "name": payload.name, "avatar": payload.avatar, "created_at": now}

@router.get("/{char_id}")
async def get_character(char_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM characters WHERE id = ?", (char_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Character not found")
    return dict(row)

@router.put("/{char_id}")
async def update_character(char_id: str, payload: UpdateCharacterPayload):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM characters WHERE id = ?", (char_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Character not found")

    name = payload.name if payload.name is not None else existing["name"]
    avatar = payload.avatar if payload.avatar is not None else existing["avatar"]
    description = payload.description if payload.description is not None else existing["description"]
    system_prompt = payload.system_prompt if payload.system_prompt is not None else existing["system_prompt"]
    default_model = payload.default_model if payload.default_model is not None else existing["default_model"]
    temperature = payload.temperature if payload.temperature is not None else existing["temperature"]

    conn.execute("""
        UPDATE characters
        SET name = ?, avatar = ?, description = ?, system_prompt = ?, default_model = ?, temperature = ?
        WHERE id = ?
    """, (name, avatar, description, system_prompt, default_model, temperature, char_id))
    conn.commit()
    conn.close()
    return {"success": True, "id": char_id, "name": name}

@router.delete("/{char_id}")
async def delete_character(char_id: str):
    conn = get_db()
    conn.execute("DELETE FROM characters WHERE id = ?", (char_id,))
    conn.commit()
    conn.close()
    return {"success": True}
