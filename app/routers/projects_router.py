import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from pathlib import Path

from app.config import UPLOADS_DIR
from app.database import get_db
from app.rag.rag_engine import RAGEngine

router = APIRouter(prefix="/api/projects", tags=["Projects"])

class CreateProjectPayload(BaseModel):
    name: str
    description: Optional[str] = ""
    system_prompt: Optional[str] = ""

class UpdateProjectPayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None

@router.get("/list")
async def list_projects():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*,
            (SELECT COUNT(*) FROM chats WHERE project_id = p.id) as chat_count,
            (SELECT COUNT(DISTINCT filename) FROM rag_documents WHERE project_id = p.id) as doc_count
        FROM projects p
        ORDER BY updated_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/create")
async def create_project(payload: CreateProjectPayload):
    proj_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO projects (id, name, description, system_prompt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (proj_id, payload.name, payload.description or "", payload.system_prompt or "", now, now))
    conn.commit()
    conn.close()
    return {"id": proj_id, "name": payload.name, "description": payload.description, "system_prompt": payload.system_prompt, "created_at": now}

@router.get("/{project_id}")
async def get_project(project_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute("SELECT id, title, created_at, updated_at FROM chats WHERE project_id = ? ORDER BY updated_at DESC", (project_id,))
    chats = [dict(c) for c in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT filename, file_type, created_at FROM rag_documents WHERE project_id = ?", (project_id,))
    docs = [dict(d) for d in cursor.fetchall()]

    conn.close()
    return {"project": dict(row), "chats": chats, "documents": docs}

@router.put("/{project_id}")
async def update_project(project_id: str, payload: UpdateProjectPayload):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    name = payload.name if payload.name is not None else existing["name"]
    description = payload.description if payload.description is not None else existing["description"]
    system_prompt = payload.system_prompt if payload.system_prompt is not None else existing["system_prompt"]
    now = datetime.now().isoformat()

    conn.execute("""
        UPDATE projects SET name = ?, description = ?, system_prompt = ?, updated_at = ?
        WHERE id = ?
    """, (name, description, system_prompt, now, project_id))
    conn.commit()
    conn.close()
    return {"success": True, "id": project_id, "name": name}

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    conn = get_db()
    # Delete associated documents and chats
    conn.execute("DELETE FROM rag_documents WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM chats WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@router.post("/{project_id}/upload_doc")
async def upload_project_document(project_id: str, file: UploadFile = File(...)):
    filename = file.filename or "project_doc"
    save_path = UPLOADS_DIR / f"proj_{project_id[:8]}_{filename}"
    
    with open(save_path, "wb") as f_out:
        content = await file.read()
        f_out.write(content)

    chunks_count = await RAGEngine.process_and_index_file(save_path, filename, project_id=project_id)
    return {"success": True, "filename": filename, "chunks_indexed": chunks_count}
