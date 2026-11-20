import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.config import DB_PATH, DEFAULT_SETTINGS

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high performance concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)

    # Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            system_prompt TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # Characters table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            avatar TEXT DEFAULT '🤖',
            description TEXT DEFAULT '',
            system_prompt TEXT NOT NULL,
            default_model TEXT DEFAULT '',
            temperature REAL DEFAULT 0.7,
            created_at TEXT NOT NULL
        );
    """)

    # Chats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            character_id TEXT,
            title TEXT NOT NULL,
            is_incognito INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY(character_id) REFERENCES characters(id) ON DELETE SET NULL
        );
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            thinking TEXT DEFAULT '',
            images_json TEXT DEFAULT '[]',
            tools_used_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
        );
    """)

    # Artifacts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            chat_id TEXT,
            title TEXT NOT NULL,
            language TEXT NOT NULL,
            code TEXT NOT NULL,
            description TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            version INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)

    # Ensure schema migrations for artifacts table
    cursor.execute("PRAGMA table_info(artifacts)")
    art_cols = [c["name"] for c in cursor.fetchall()]
    if "file_path" not in art_cols:
        cursor.execute("ALTER TABLE artifacts ADD COLUMN file_path TEXT DEFAULT ''")

    # Ensure schema migrations for sd_presets table
    cursor.execute("PRAGMA table_info(sd_presets)")
    sd_cols = [c["name"] for c in cursor.fetchall()]
    if "text_encoders_json" not in sd_cols:
        cursor.execute("ALTER TABLE sd_presets ADD COLUMN text_encoders_json TEXT DEFAULT '[]'")

    # Stable Diffusion Presets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sd_presets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            checkpoint TEXT DEFAULT '',
            vae TEXT DEFAULT 'Automatic',
            clip_skip INTEGER DEFAULT 1,
            text_encoder TEXT DEFAULT 'None',
            loras_json TEXT DEFAULT '[]',
            steps INTEGER DEFAULT 25,
            cfg_scale REAL DEFAULT 7.0,
            shift REAL DEFAULT 1.0,
            sampler_name TEXT DEFAULT 'Euler a',
            scheduler TEXT DEFAULT 'Simple',
            width INTEGER DEFAULT 1024,
            height INTEGER DEFAULT 1024,
            negative_prompt TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)

    # RAG Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            chat_id TEXT,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            embedding_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );
    """)

    # Generated Images history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_history (
            id TEXT PRIMARY KEY,
            prompt TEXT NOT NULL,
            negative_prompt TEXT DEFAULT '',
            model TEXT DEFAULT '',
            sampler TEXT DEFAULT '',
            steps INTEGER DEFAULT 25,
            cfg REAL DEFAULT 7.0,
            shift REAL DEFAULT 1.0,
            seed INTEGER DEFAULT -1,
            width INTEGER DEFAULT 1024,
            height INTEGER DEFAULT 1024,
            image_filename TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)

    # Seed default settings if missing
    for k, v in DEFAULT_SETTINGS.items():
        cursor.execute("SELECT key FROM settings WHERE key = ?", (k,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))

    # Seed preset characters if none exist
    cursor.execute("SELECT COUNT(*) as count FROM characters")
    if cursor.fetchone()["count"] == 0:
        presets = [
            {
                "id": "char-python-architect",
                "name": "Senior Python Architect",
                "avatar": "🐍",
                "description": "Expert in modern Python, asynchronous architectures, FastAPI, optimization, and clean design patterns.",
                "system_prompt": "You are a Senior Python Architect. You write robust, clean, fully typed Python code with comprehensive docstrings and comments. Prioritize high performance, clean architecture, and modern best practices.",
                "default_model": "",
                "temperature": 0.4
            },
            {
                "id": "char-fullstack-dev",
                "name": "Fullstack Ninja",
                "avatar": "⚡",
                "description": "Master of modern web technologies, responsive UI/UX, JavaScript, HTML5, CSS3, and backend APIs.",
                "system_prompt": "You are a Fullstack Web Developer. You craft modern, responsive, accessible web interfaces and elegant backend APIs. Provide full, working code that can be run directly.",
                "default_model": "",
                "temperature": 0.5
            },
            {
                "id": "char-researcher",
                "name": "Academic Researcher",
                "avatar": "🔬",
                "description": "Rigorous scientist and researcher providing deep analyses, citations, and critical evaluations.",
                "system_prompt": "You are an Academic Research Assistant. You provide deep, scientifically grounded explanations with structured arguments, clear methodologies, and objective analysis.",
                "default_model": "",
                "temperature": 0.3
            },
            {
                "id": "char-creative-writer",
                "name": "Creative Storyteller",
                "avatar": "✨",
                "description": "Vivid imaginative storyteller, world builder, scriptwriter, and creative writing mentor.",
                "system_prompt": "You are a master storyteller and creative novelist. You craft vivid worlds, compelling dialogue, nuanced characters, and poetic prose.",
                "default_model": "",
                "temperature": 0.9
            },
            {
                "id": "char-tech-guru",
                "name": "Sarcastic Tech Reviewer",
                "avatar": "😎",
                "description": "Sharp, humorous, witty tech veteran who cuts through the hype with brutal honesty.",
                "system_prompt": "You are a witty, mildly sarcastic tech veteran. You provide brutally honest, hilarious yet deeply technically accurate analyses of software, hardware, and tech trends.",
                "default_model": "",
                "temperature": 0.8
            }
        ]
        now = datetime.now().isoformat()
        for p in presets:
            cursor.execute("""
                INSERT INTO characters (id, name, avatar, description, system_prompt, default_model, temperature, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["id"], p["name"], p["avatar"], p["description"], p["system_prompt"], p["default_model"], p["temperature"], now))

    # Seed default SD presets if empty
    cursor.execute("SELECT COUNT(*) as count FROM sd_presets")
    if cursor.fetchone()["count"] == 0:
        default_presets = [
            {
                "id": "preset-flux-quality",
                "name": "Flux / Flow-Match Quality",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 25,
                "cfg_scale": 3.5,
                "shift": 3.0,
                "sampler_name": "Euler",
                "scheduler": "Simple",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "low quality, blurry, text, watermark"
            },
            {
                "id": "preset-sdxl-cinematic",
                "name": "SDXL Cinematic High-Res",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 30,
                "cfg_scale": 7.0,
                "shift": 1.0,
                "sampler_name": "DPM++ 2M Karras",
                "scheduler": "Karras",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "ugly, deformed, bad anatomy, low quality, blurry"
            },
            {
                "id": "preset-anime-style",
                "name": "Anime & Manga Style",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 2,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 28,
                "cfg_scale": 7.5,
                "shift": 1.0,
                "sampler_name": "Euler a",
                "scheduler": "Simple",
                "width": 832,
                "height": 1216,
                "negative_prompt": "photorealistic, 3d, realistic, bad anatomy, low quality"
            },
            {
                "id": "preset-fast-turbo",
                "name": "Fast Turbo / Lightning",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 8,
                "cfg_scale": 2.0,
                "shift": 1.0,
                "sampler_name": "Euler",
                "scheduler": "Simple",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "low quality, bad quality"
            }
        ]
        now = datetime.now().isoformat()
        for p in default_presets:
            cursor.execute("""
                INSERT INTO sd_presets (id, name, checkpoint, vae, clip_skip, text_encoder, loras_json, steps, cfg_scale, shift, sampler_name, scheduler, width, height, negative_prompt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["id"], p["name"], p["checkpoint"], p["vae"], p["clip_skip"], p["text_encoder"], p["loras_json"], p["steps"], p["cfg_scale"], p["shift"], p["sampler_name"], p["scheduler"], p["width"], p["height"], p["negative_prompt"], now))

    conn.commit()

# Helper methods for settings
def get_all_settings() -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for r in rows:
        try:
            result[r["key"]] = json.loads(r["value"])
        except Exception:
            result[r["key"]] = r["value"]
    # Fill in any missing default settings
    for k, v in DEFAULT_SETTINGS.items():
        if k not in result:
            result[k] = v
    return result

def get_setting(key: str, default: Any = None) -> Any:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return default if default is not None else DEFAULT_SETTINGS.get(key)
    try:
        return json.loads(row["value"])
    except Exception:
        return row["value"]

def set_setting(key: str, value: Any):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))
    # Seed default SD presets if empty
    cursor.execute("SELECT COUNT(*) as count FROM sd_presets")
    if cursor.fetchone()["count"] == 0:
        default_presets = [
            {
                "id": "preset-flux-quality",
                "name": "Flux / Flow-Match Quality",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 25,
                "cfg_scale": 3.5,
                "shift": 3.0,
                "sampler_name": "Euler",
                "scheduler": "Simple",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "low quality, blurry, text, watermark"
            },
            {
                "id": "preset-sdxl-cinematic",
                "name": "SDXL Cinematic High-Res",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 30,
                "cfg_scale": 7.0,
                "shift": 1.0,
                "sampler_name": "DPM++ 2M Karras",
                "scheduler": "Karras",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "ugly, deformed, bad anatomy, low quality, blurry"
            },
            {
                "id": "preset-anime-style",
                "name": "Anime & Manga Style",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 2,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 28,
                "cfg_scale": 7.5,
                "shift": 1.0,
                "sampler_name": "Euler a",
                "scheduler": "Simple",
                "width": 832,
                "height": 1216,
                "negative_prompt": "photorealistic, 3d, realistic, bad anatomy, low quality"
            },
            {
                "id": "preset-fast-turbo",
                "name": "Fast Turbo / Lightning",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 8,
                "cfg_scale": 2.0,
                "shift": 1.0,
                "sampler_name": "Euler",
                "scheduler": "Simple",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "low quality, bad quality"
            }
        ]
        now = datetime.now().isoformat()
        for p in default_presets:
            cursor.execute("""
                INSERT INTO sd_presets (id, name, checkpoint, vae, clip_skip, text_encoder, loras_json, steps, cfg_scale, shift, sampler_name, scheduler, width, height, negative_prompt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["id"], p["name"], p["checkpoint"], p["vae"], p["clip_skip"], p["text_encoder"], p["loras_json"], p["steps"], p["cfg_scale"], p["shift"], p["sampler_name"], p["scheduler"], p["width"], p["height"], p["negative_prompt"], now))

    conn.commit()

def set_multiple_settings(settings_dict: Dict[str, Any]):
    conn = get_db()
    cursor = conn.cursor()
    for k, v in settings_dict.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))
    # Seed default SD presets if empty
    cursor.execute("SELECT COUNT(*) as count FROM sd_presets")
    if cursor.fetchone()["count"] == 0:
        default_presets = [
            {
                "id": "preset-flux-quality",
                "name": "Flux / Flow-Match Quality",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 25,
                "cfg_scale": 3.5,
                "shift": 3.0,
                "sampler_name": "Euler",
                "scheduler": "Simple",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "low quality, blurry, text, watermark"
            },
            {
                "id": "preset-sdxl-cinematic",
                "name": "SDXL Cinematic High-Res",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 30,
                "cfg_scale": 7.0,
                "shift": 1.0,
                "sampler_name": "DPM++ 2M Karras",
                "scheduler": "Karras",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "ugly, deformed, bad anatomy, low quality, blurry"
            },
            {
                "id": "preset-anime-style",
                "name": "Anime & Manga Style",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 2,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 28,
                "cfg_scale": 7.5,
                "shift": 1.0,
                "sampler_name": "Euler a",
                "scheduler": "Simple",
                "width": 832,
                "height": 1216,
                "negative_prompt": "photorealistic, 3d, realistic, bad anatomy, low quality"
            },
            {
                "id": "preset-fast-turbo",
                "name": "Fast Turbo / Lightning",
                "checkpoint": "",
                "vae": "Automatic",
                "clip_skip": 1,
                "text_encoder": "None",
                "loras_json": "[]",
                "steps": 8,
                "cfg_scale": 2.0,
                "shift": 1.0,
                "sampler_name": "Euler",
                "scheduler": "Simple",
                "width": 1024,
                "height": 1024,
                "negative_prompt": "low quality, bad quality"
            }
        ]
        now = datetime.now().isoformat()
        for p in default_presets:
            cursor.execute("""
                INSERT INTO sd_presets (id, name, checkpoint, vae, clip_skip, text_encoder, loras_json, steps, cfg_scale, shift, sampler_name, scheduler, width, height, negative_prompt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["id"], p["name"], p["checkpoint"], p["vae"], p["clip_skip"], p["text_encoder"], p["loras_json"], p["steps"], p["cfg_scale"], p["shift"], p["sampler_name"], p["scheduler"], p["width"], p["height"], p["negative_prompt"], now))

    conn.commit()
