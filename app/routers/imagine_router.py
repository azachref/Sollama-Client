import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.config import GENERATED_IMAGES_DIR
from app.database import get_db, get_all_settings
from app.imagine.forge_client import SDForgeClient

router = APIRouter(prefix="/api/imagine", tags=["Imagine"])

class GenerateImageRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    checkpoint: Optional[str] = None
    vae: Optional[str] = "Automatic"
    clip_skip: Optional[int] = 1
    text_encoder: Optional[str] = "None"
    text_encoders: Optional[List[str]] = []
    loras: Optional[List[Dict[str, Any]]] = []
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    steps: Optional[int] = 25
    cfg_scale: Optional[float] = 7.0
    shift: Optional[float] = 1.0
    sampler_name: Optional[str] = "Euler a"
    scheduler: Optional[str] = "Simple"
    seed: Optional[int] = -1

class SDPresetPayload(BaseModel):
    name: str
    checkpoint: Optional[str] = ""
    vae: Optional[str] = "Automatic"
    clip_skip: Optional[int] = 1
    text_encoder: Optional[str] = "None"
    text_encoders: Optional[List[str]] = []
    loras: Optional[List[Dict[str, Any]]] = []
    steps: Optional[int] = 25
    cfg_scale: Optional[float] = 7.0
    shift: Optional[float] = 1.0
    sampler_name: Optional[str] = "Euler a"
    scheduler: Optional[str] = "Simple"
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    negative_prompt: Optional[str] = ""

@router.get("/status")
async def get_forge_status():
    """Check connectivity and fetch Forge environment options."""
    status = await SDForgeClient.check_status()
    models = await SDForgeClient.get_models()
    vaes = await SDForgeClient.get_vaes()
    text_encoders = await SDForgeClient.get_text_encoders()
    loras = await SDForgeClient.get_loras()
    samplers = await SDForgeClient.get_samplers()
    schedulers = await SDForgeClient.get_schedulers()

    return {
        "status": status,
        "models": models,
        "vaes": vaes,
        "text_encoders": text_encoders,
        "loras": loras,
        "samplers": samplers,
        "schedulers": schedulers
    }

# --- Presets CRUD ---
@router.get("/presets")
async def list_presets():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sd_presets ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        try:
            item["loras"] = json.loads(item.get("loras_json", "[]"))
        except Exception:
            item["loras"] = []
        try:
            item["text_encoders"] = json.loads(item.get("text_encoders_json", "[]"))
        except Exception:
            item["text_encoders"] = []
        results.append(item)
    return results

@router.post("/presets")
async def save_preset(payload: SDPresetPayload):
    preset_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = get_db()
    # Determine text encoders list
    te_list = payload.text_encoders or []
    if not te_list and payload.text_encoder and payload.text_encoder != "None":
        te_list = [payload.text_encoder]

    conn.execute("""
        INSERT INTO sd_presets (id, name, checkpoint, vae, clip_skip, text_encoder, text_encoders_json, loras_json, steps, cfg_scale, shift, sampler_name, scheduler, width, height, negative_prompt, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        preset_id,
        payload.name,
        payload.checkpoint or "",
        payload.vae or "Automatic",
        payload.clip_skip or 1,
        payload.text_encoder or "None",
        json.dumps(te_list),
        json.dumps(payload.loras or []),
        payload.steps or 25,
        payload.cfg_scale or 7.0,
        payload.shift or 1.0,
        payload.sampler_name or "Euler a",
        payload.scheduler or "Simple",
        payload.width or 1024,
        payload.height or 1024,
        payload.negative_prompt or "",
        now
    ))
    conn.commit()
    conn.close()
    return {"success": True, "id": preset_id, "name": payload.name}

@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str):
    conn = get_db()
    conn.execute("DELETE FROM sd_presets WHERE id = ?", (preset_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@router.post("/generate")
async def generate_image(payload: GenerateImageRequest):
    """Trigger image generation via SD Forge Neo."""
    res = await SDForgeClient.generate_image(payload.model_dump())
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Image generation failed"))
    return res

@router.get("/gallery")
async def get_image_gallery():
    """Retrieve history of generated images."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM image_history ORDER BY created_at DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        item = dict(r)
        item["image_url"] = f"/api/imagine/image/{item['image_filename']}"
        results.append(item)
    return results

@router.get("/image/{filename}")
async def serve_image(filename: str):
    """Serve a generated image file."""
    path = GENERATED_IMAGES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")

@router.delete("/image/{image_id}")
async def delete_image(image_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT image_filename FROM image_history WHERE id = ?", (image_id,))
    row = cursor.fetchone()
    if row:
        img_path = GENERATED_IMAGES_DIR / row["image_filename"]
        if img_path.exists():
            try:
                img_path.unlink()
            except Exception:
                pass
        conn.execute("DELETE FROM image_history WHERE id = ?", (image_id,))
        conn.commit()
    conn.close()
    return {"success": True}
