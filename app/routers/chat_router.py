import json
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import UPLOADS_DIR
from app.database import get_db, get_setting
from app.ollama_client import OllamaClient
from app.extensions.manager import ExtensionManager
from app.rag.rag_engine import RAGEngine

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class NewChatRequest(BaseModel):
    title: Optional[str] = "New Chat"
    project_id: Optional[str] = None
    character_id: Optional[str] = None
    is_incognito: Optional[bool] = False

class RenameChatRequest(BaseModel):
    title: str

class SendMessagePayload(BaseModel):
    chat_id: str
    message: str
    model: Optional[str] = None
    images: Optional[List[str]] = []  # base64 encoded strings
    is_incognito: Optional[bool] = False
    system_prompt: Optional[str] = None

@router.get("/list")
async def list_chats(project_id: Optional[str] = None):
    """List chats with character and project metadata, optionally filtered by project."""
    conn = get_db()
    cursor = conn.cursor()
    if project_id:
        cursor.execute("""
            SELECT c.id, c.project_id, c.character_id, c.title, c.is_incognito, c.created_at, c.updated_at,
                   p.name as project_name,
                   ch.name as character_name, ch.avatar as character_avatar
            FROM chats c
            LEFT JOIN projects p ON c.project_id = p.id
            LEFT JOIN characters ch ON c.character_id = ch.id
            WHERE c.project_id = ? AND c.is_incognito = 0
            ORDER BY c.updated_at DESC
        """, (project_id,))
    else:
        cursor.execute("""
            SELECT c.id, c.project_id, c.character_id, c.title, c.is_incognito, c.created_at, c.updated_at,
                   p.name as project_name,
                   ch.name as character_name, ch.avatar as character_avatar
            FROM chats c
            LEFT JOIN projects p ON c.project_id = p.id
            LEFT JOIN characters ch ON c.character_id = ch.id
            WHERE (c.project_id IS NULL OR c.project_id = '') AND c.is_incognito = 0
            ORDER BY c.updated_at DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.post("/new")
async def create_chat(payload: NewChatRequest):
    """Create a new chat conversation."""
    chat_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    is_incognito = 1 if payload.is_incognito else 0

    if not is_incognito:
        conn = get_db()
        conn.execute("""
            INSERT INTO chats (id, project_id, character_id, title, is_incognito, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (chat_id, payload.project_id, payload.character_id, payload.title or "New Chat", is_incognito, now, now))
        conn.commit()
        conn.close()

    return {
        "id": chat_id,
        "project_id": payload.project_id,
        "character_id": payload.character_id,
        "title": payload.title or "New Chat",
        "is_incognito": bool(is_incognito),
        "created_at": now
    }

@router.get("/{chat_id}")
async def get_chat_details(chat_id: str):
    """Retrieve chat info, associated project/character, and its messages."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*,
               p.name as project_name,
               ch.name as character_name,
               ch.avatar as character_avatar,
               ch.default_model as character_model
        FROM chats c
        LEFT JOIN projects p ON c.project_id = p.id
        LEFT JOIN characters ch ON c.character_id = ch.id
        WHERE c.id = ?
    """, (chat_id,))
    chat_row = cursor.fetchone()
    if not chat_row:
        conn.close()
        # Might be an incognito session id
        return {"chat": {"id": chat_id, "title": "Incognito Session", "is_incognito": True}, "messages": []}

    cursor.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,))
    msg_rows = cursor.fetchall()
    conn.close()

    messages = []
    for m in msg_rows:
        item = dict(m)
        try:
            item["images"] = json.loads(item.get("images_json", "[]"))
        except Exception:
            item["images"] = []
        try:
            item["tools_used"] = json.loads(item.get("tools_used_json", "[]"))
        except Exception:
            item["tools_used"] = []
        messages.append(item)

    return {"chat": dict(chat_row), "messages": messages}

@router.put("/{chat_id}/rename")
async def rename_chat(chat_id: str, payload: RenameChatRequest):
    conn = get_db()
    conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?", (payload.title, datetime.now().isoformat(), chat_id))
    conn.commit()
    conn.close()
    return {"success": True, "title": payload.title}

@router.delete("/{chat_id}")
async def delete_chat(chat_id: str):
    conn = get_db()
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@router.post("/upload")
async def upload_attachment(file: UploadFile = File(...), chat_id: Optional[str] = Form(None), project_id: Optional[str] = Form(None)):
    """Upload an image or document for vision or RAG indexing."""
    filename = file.filename or "uploaded_file"
    ext = Path(filename).suffix.lower()
    save_name = f"{uuid.uuid4().hex[:10]}_{filename}"
    save_path = UPLOADS_DIR / save_name

    with open(save_path, "wb") as f_out:
        content = await file.read()
        f_out.write(content)

    is_image = ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]
    image_base64 = ""
    if is_image:
        image_base64 = base64.b64encode(content).decode("utf-8")

    # If document (PDF, TXT, DOCX, MD), index into RAG
    rag_chunks = 0
    if ext in [".pdf", ".docx", ".doc", ".txt", ".md", ".json", ".csv"]:
        rag_chunks = await RAGEngine.process_and_index_file(save_path, filename, project_id=project_id, chat_id=chat_id)

    return {
        "success": True,
        "filename": filename,
        "saved_path": str(save_path),
        "is_image": is_image,
        "base64": image_base64,
        "rag_chunks": rag_chunks
    }

@router.post("/send")
async def send_message_stream(payload: SendMessagePayload):
    """
    Process incoming user message:
    1. Check tools & extensions intent (Open-Meteo, Wikipedia, SearXNG, DDGS, Open Library, ZIM).
    2. Check RAG knowledge base for matching documents.
    3. Inject user personalization and character system prompt.
    4. Stream response via Server-Sent Events (SSE) with thinking tags extraction.
    5. Save to database if not incognito.
    """
    chat_id = payload.chat_id
    user_text = payload.message.strip()
    is_incognito = payload.is_incognito
    now_iso = datetime.now().isoformat()

    # Load chat info if exists
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    chat_row = cursor.fetchone()

    project_id = chat_row["project_id"] if chat_row else None
    character_id = chat_row["character_id"] if chat_row else None
    if chat_row and chat_row["is_incognito"]:
        is_incognito = True

    # 1. Determine Model
    chosen_model = payload.model
    if not chosen_model:
        # Check character default model
        if character_id:
            cursor.execute("SELECT default_model, temperature, system_prompt FROM characters WHERE id = ?", (character_id,))
            char_row = cursor.fetchone()
            if char_row and char_row["default_model"]:
                chosen_model = char_row["default_model"]

    if not chosen_model:
        chosen_model = get_setting("default_model", "llama3.2:latest")

    # 2. Build System Prompt & Personalization
    base_sys_prompt = payload.system_prompt or get_setting("system_prompt", "")
    char_sys_prompt = ""
    if character_id:
        cursor.execute("SELECT system_prompt FROM characters WHERE id = ?", (character_id,))
        cr = cursor.fetchone()
        if cr and cr["system_prompt"]:
            char_sys_prompt = cr["system_prompt"]

    # Personalization info
    user_name = get_setting("user_name", "")
    user_occ = get_setting("user_occupation", "")
    user_custom = get_setting("user_custom_instructions", "")
    personal_parts = []
    if user_name:
        personal_parts.append(f"The user's name is {user_name}.")
    if user_occ:
        personal_parts.append(f"The user's occupation/role: {user_occ}.")
    if user_custom:
        personal_parts.append(f"User preferences & context: {user_custom}")

    personal_block = f"\n[USER PERSONALIZATION]\n" + "\n".join(personal_parts) + "\n[END PERSONALIZATION]\n" if personal_parts else ""

    # Project context
    proj_block = ""
    if project_id:
        cursor.execute("SELECT name, description, system_prompt FROM projects WHERE id = ?", (project_id,))
        pr = cursor.fetchone()
        if pr:
            proj_block = f"\n[PROJECT WORKSPACE: {pr['name']}]\nDescription: {pr['description']}\nGuidelines: {pr['system_prompt']}\n[END PROJECT]\n"

    # 3. Check Tools & Extensions
    detected_tool = ExtensionManager.detect_intent(user_text)
    tools_used = []
    tool_context = ""
    if detected_tool:
        tool_name, tool_query = detected_tool
        print(f"[SuperOllama] Tool detected: {tool_name} | Query: {tool_query!r}")
        tool_res = ExtensionManager.execute_tool(tool_name, tool_query)
        if tool_res:
            tools_used.append(tool_res)
            tool_context = ExtensionManager.format_tool_context(tool_res)
            print(f"[SuperOllama] Tool executed successfully: {tool_res['tool']} — {tool_res['summary']}")
        else:
            print(f"[SuperOllama] Tool {tool_name} returned no results for: {tool_query!r}")
    else:
        print(f"[SuperOllama] No tool intent detected for: {user_text[:80]!r}")

    # 4. Check RAG Knowledge Base
    rag_context = ""
    try:
        rag_hits = await RAGEngine.search(user_text, project_id=project_id, chat_id=chat_id, top_k=3)
        if rag_hits:
            rag_context = RAGEngine.format_rag_context(rag_hits)
    except Exception:
        pass

    # 5. Assemble final system prompt
    # Include tool-awareness blurb so the model knows what it can do
    tools_awareness = ExtensionManager.get_enabled_tools_summary() if get_setting("ext_auto_route", True) else ""
    full_system_prompt = "\n\n".join(filter(None, [base_sys_prompt, char_sys_prompt, proj_block, personal_block, tools_awareness, tool_context, rag_context]))

    # 6. Fetch conversation history
    history_messages = []
    if not is_incognito and chat_row:
        cursor.execute("SELECT role, content, images_json FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,))
        for r in cursor.fetchall():
            m_item = {"role": r["role"], "content": r["content"]}
            try:
                imgs = json.loads(r["images_json"])
                if imgs:
                    m_item["images"] = imgs
            except Exception:
                pass
            history_messages.append(m_item)

    conn.close()

    # Append current user message
    user_msg_obj = {"role": "user", "content": user_text}
    if payload.images:
        user_msg_obj["images"] = payload.images
    history_messages.append(user_msg_obj)

    # Save user message to database if not incognito
    user_msg_id = str(uuid.uuid4())
    if not is_incognito:
        conn = get_db()
        conn.execute("""
            INSERT INTO messages (id, chat_id, role, content, images_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_msg_id, chat_id, "user", user_text, json.dumps(payload.images or []), now_iso))
        
        # Update chat title if it's the first message
        if chat_row and chat_row["title"] in ["New Chat", ""]:
            new_title = user_text[:35] + ("..." if len(user_text) > 35 else "")
            conn.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?", (new_title, now_iso, chat_id))
        else:
            conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now_iso, chat_id))
        conn.commit()
        conn.close()

    # 7. SSE Generator
    async def event_generator():
        # First send tool usage notification if any tool was executed
        if tools_used:
            for tu in tools_used:
                yield f"data: {json.dumps({'type': 'tool', 'tool': tu['tool'], 'icon': tu['icon'], 'summary': tu['summary']})}\n\n"

        assistant_content = ""
        assistant_thinking = ""
        assistant_msg_id = str(uuid.uuid4())

        async for chunk in OllamaClient.stream_chat(history_messages, model=chosen_model, system_prompt=full_system_prompt):
            c_type = chunk.get("type")
            if c_type == "content":
                assistant_content += chunk.get("content", "")
                yield f"data: {json.dumps({'type': 'content', 'delta': chunk.get('content', '')})}\n\n"
            elif c_type == "thinking":
                assistant_thinking += chunk.get("content", "")
                yield f"data: {json.dumps({'type': 'thinking', 'delta': chunk.get('content', '')})}\n\n"
            elif c_type == "done":
                # Save assistant response to DB if not incognito
                if not is_incognito:
                    c = get_db()
                    c.execute("""
                        INSERT INTO messages (id, chat_id, role, content, thinking, tools_used_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        assistant_msg_id,
                        chat_id,
                        "assistant",
                        assistant_content,
                        assistant_thinking,
                        json.dumps(tools_used),
                        datetime.now().isoformat()
                    ))
                    c.commit()
                    c.close()

                yield f"data: {json.dumps({'type': 'done', 'msg_id': assistant_msg_id, 'is_incognito': is_incognito})}\n\n"
            elif c_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'error': chunk.get('error', 'Unknown error')})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
