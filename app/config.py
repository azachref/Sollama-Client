import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
ZIM_DIR = DATA_DIR / "zim"
GENERATED_IMAGES_DIR = DATA_DIR / "generated_images"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DB_PATH = DATA_DIR / "superollama.db"

# Ensure runtime directories exist
for path in [DATA_DIR, UPLOADS_DIR, ZIM_DIR, GENERATED_IMAGES_DIR, ARTIFACTS_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Application metadata
APP_NAME = "SuperOllama"
APP_VERSION = "1.0.0"

# Default application settings
DEFAULT_SETTINGS = {
    # Ollama settings
    "ollama_base_url": "http://127.0.0.1:11434",
    "default_model": "llama3.2:latest",
    "default_embedding_model": "nomic-embed-text:latest",
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_ctx": 4096,
    "system_prompt": "You are a helpful, brilliant, and precise AI assistant. When writing code, provide clean, idiomatic, and working code blocks with proper syntax highlighting. Answer clearly and concisely.",

    # User personalization
    "user_name": "User",
    "user_occupation": "Developer",
    "user_custom_instructions": "",

    # Stable Diffusion Forge Neo API settings
    "sd_forge_url": "http://127.0.0.1:7860",
    "sd_checkpoint": "",
    "sd_vae": "Automatic",
    "sd_clip_skip": 1,
    "sd_text_encoders": ["CLIP-L"],
    "sd_loras": [],  # list of { name, weight }
    "sd_steps": 25,
    "sd_cfg_scale": 7.0,
    "sd_shift": 1.0,  # For Flux / SD3 flow models
    "sd_sampler_name": "Euler a",
    "sd_scheduler": "Simple",
    "sd_width": 1024,
    "sd_height": 1024,
    "sd_negative_prompt": "low quality, bad quality, blurry, deformed, distorted, text, watermark",

    # Extensions / Tools
    "ext_auto_route": True,
    "ext_wikipedia_enabled": True,
    "ext_open_meteo_enabled": True,
    "ext_searxng_enabled": True,
    "ext_searxng_url": "http://192.168.1.101:8080",
    "ext_ddgs_enabled": True,
    "ext_open_library_enabled": True,
    "ext_zim_enabled": True,
    "ext_zim_api_url": "http://127.0.0.1:8080",
    "ext_zim_path": str(ZIM_DIR),
    "active_zim_filename": "",

    # App preferences
    "theme": "dark",
    "incognito": False
}
