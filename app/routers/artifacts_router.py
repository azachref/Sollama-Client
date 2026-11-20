import os
import subprocess
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.config import ARTIFACTS_DIR
from app.database import get_db

router = APIRouter(prefix="/api/artifacts", tags=["Artifacts"])

# Common language extension mappings
LANG_EXT_MAP = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "html": ".html", "htm": ".html",
    "css": ".css",
    "json": ".json",
    "markdown": ".md", "md": ".md",
    "bash": ".sh", "sh": ".sh",
    "shell": ".sh",
    "powershell": ".ps1", "ps1": ".ps1",
    "sql": ".sql",
    "cpp": ".cpp", "c": ".c",
    "rust": ".rs", "rs": ".rs",
    "go": ".go",
    "xml": ".xml",
    "yaml": ".yaml", "yml": ".yml",
    "text": ".txt", "txt": ".txt"
}

LANG_MIME_MAP = {
    "python": "text/x-python",
    "javascript": "application/javascript",
    "typescript": "application/x-typescript",
    "html": "text/html",
    "css": "text/css",
    "json": "application/json",
    "markdown": "text/markdown",
    "sql": "text/x-sql"
}

class SaveArtifactPayload(BaseModel):
    title: str
    language: str
    code: str
    description: Optional[str] = ""
    chat_id: Optional[str] = None

class UpdateArtifactPayload(BaseModel):
    title: Optional[str] = None
    language: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None

def get_safe_name(name: str) -> str:
    # Filter out characters that are invalid in Windows filenames
    invalid_chars = '<>:"/\\|?*'
    clean = "".join(c for c in name if c not in invalid_chars)
    return clean.strip().replace(" ", "_") or "artifact"

@router.get("/list")
async def list_artifacts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, chat_id, title, language, description, file_path, version, created_at, updated_at FROM artifacts ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/save")
async def save_artifact(payload: SaveArtifactPayload):
    art_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    clean_title = payload.title.strip() or "Untitled Artifact"
    clean_lang = payload.language.strip().lower() or "text"

    ext = LANG_EXT_MAP.get(clean_lang, ".txt")
    safe_base = get_safe_name(clean_title)
    safe_filename = safe_base if safe_base.endswith(ext) else f"{safe_base}{ext}"

    # Create physical folder on PC inside artifacts directory
    folder_name = safe_base.lower()
    save_dir = ARTIFACTS_DIR / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / safe_filename

    # Write code file to disk
    with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(payload.code)

    # Persist in SQLite
    conn = get_db()
    conn.execute("""
        INSERT INTO artifacts (id, chat_id, title, language, code, description, file_path, version, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (art_id, payload.chat_id, clean_title, clean_lang, payload.code, payload.description or "", str(file_path), now, now))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "id": art_id,
        "title": clean_title,
        "language": clean_lang,
        "filename": safe_filename,
        "file_path": str(file_path),
        "created_at": now
    }

@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")

    res = dict(row)
    lang = res["language"].lower()
    ext = LANG_EXT_MAP.get(lang, ".txt")
    safe_name = get_safe_name(res["title"])
    if not safe_name.endswith(ext):
        safe_name += ext
    res["filename"] = safe_name
    return res

@router.put("/{artifact_id}")
async def update_artifact(artifact_id: str, payload: UpdateArtifactPayload):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Artifact not found")

    title = payload.title if payload.title is not None else existing["title"]
    language = payload.language if payload.language is not None else existing["language"]
    code = payload.code if payload.code is not None else existing["code"]
    description = payload.description if payload.description is not None else existing["description"]
    new_version = existing["version"] + 1
    now = datetime.now().isoformat()

    # Re-save file to disk
    ext = LANG_EXT_MAP.get(language.lower(), ".txt")
    safe_base = get_safe_name(title)
    safe_filename = safe_base if safe_base.endswith(ext) else f"{safe_base}{ext}"
    save_dir = ARTIFACTS_DIR / safe_base.lower()
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / safe_filename
    with open(file_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(code)

    conn.execute("""
        UPDATE artifacts
        SET title = ?, language = ?, code = ?, description = ?, file_path = ?, version = ?, updated_at = ?
        WHERE id = ?
    """, (title, language, code, description, str(file_path), new_version, now, artifact_id))
    conn.commit()
    conn.close()
    return {"success": True, "id": artifact_id, "version": new_version, "file_path": str(file_path)}

@router.post("/{artifact_id}/reveal")
async def reveal_artifact_in_explorer(artifact_id: str):
    """Open the artifact file's containing folder in Windows Explorer."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM artifacts WHERE id = ?", (artifact_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row["file_path"]:
        raise HTTPException(status_code=404, detail="Artifact file path not recorded")

    fp = Path(row["file_path"])
    if not fp.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk at {fp}")

    try:
        # In Windows, explorer.exe /select,path highlights the file
        subprocess.run(["explorer.exe", f"/select,{fp}"], check=False)
        return {"success": True, "path": str(fp)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{artifact_id}/download")
async def download_artifact(artifact_id: str):
    """Download artifact with its intended filename and extension."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")

    lang = row["language"].lower()
    ext = LANG_EXT_MAP.get(lang, ".txt")
    safe_name = get_safe_name(row["title"])
    if not safe_name.endswith(ext):
        safe_name += ext

    mime_type = LANG_MIME_MAP.get(lang, "text/plain")
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"'
    }
    return Response(content=row["code"], media_type=mime_type, headers=headers)

@router.delete("/{artifact_id}")
async def delete_artifact(artifact_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM artifacts WHERE id = ?", (artifact_id,))
    row = cursor.fetchone()
    if row and row["file_path"]:
        try:
            fp = Path(row["file_path"])
            if fp.exists():
                fp.unlink()
        except Exception:
            pass

    conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    conn.commit()
    conn.close()
    return {"success": True}
