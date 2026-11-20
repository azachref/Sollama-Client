# SuperOllama 🚀

A modern, full-featured **Ollama Client & AI Studio** built with Python and FastAPI, designed specifically for Windows PCs and accessible seamlessly across desktop and mobile devices. Styled with the sleek aesthetics of big-tech AI platforms like **Google Gemini, ChatGPT, and Claude**.

---

## ✨ Features

### 💬 Big-Tech Chat Experience
- **Responsive Big-Tech Design**: Modern dark & light modes, smooth transitions, mobile off-canvas drawer sidebar, and touch-optimized controls.
- **Dynamic Model Selection**: Auto-detects all installed models from local or network Ollama instances (`/api/tags`).
- **Thinking / Reasoning Visualizer**: For reasoning models (such as DeepSeek-R1 or Qwen reasoning), outputs inside `<think>...</think>` tags are rendered in a sleek collapsible thought accordion with a live elapsed-time counter and glowing pulse indicator.
- **Multimodal Vision Support**: Drag-and-drop or upload images directly to analyze with vision models (e.g. `llama3.2-vision`, `llava`, `minicpm-v`).
- **Incognito Mode 🕵️**: One-click incognito toggle with purple glow badge. Chats conducted in incognito mode are completely ephemeral and never written to database or disk.

### 💻 First-Class Coding Support & Artifacts
- **Interactive Code Boxes**: Fenced code blocks with language badge, deduced filename, syntax highlighting, and 1-click **Copy**, **Download**, **Save to Artifacts**, and **Run**.
- **Live In-Browser Sandbox**:
  - **HTML / CSS / JavaScript / SVG**: Interactive live preview rendered inside an isolated iframe.
  - **Python**: Real-time server-side execution with standard output, error capture, and execution timing.
- **Artifacts Section**: Dedicated repository of all saved code snippets, scripts, apps, and documents. Supports versioning, live preview/execution, and direct file download with intended filename and extension.

### 📁 Projects Section (Workspaces)
- Create custom project workspaces separate from standard chats.
- Upload project-specific knowledge documents (PDF, DOCX, TXT, MD, CSV, JSON) into an isolated project RAG index.
- Configure dedicated project instructions and maintain isolated conversation threads.

### 🎭 Characters & Personas
- Create and manage custom personas with custom Name, Avatar (emoji or image), System Prompt, Preferred Model, and Temperature.
- Ships with built-in presets: **Senior Python Architect**, **Fullstack Ninja**, **Academic Researcher**, **Creative Storyteller**, and **Sarcastic Tech Reviewer**.

### 🎨 Imagine (Stable Diffusion Forge Neo)
- Deep integration with **Stable Diffusion WebUI / Forge / Forge Neo / Automatic1111 / SD.Next API**.
- Full parameter control:
  - Active Checkpoint selector & VAE dropdown
  - CLIP Skip / Text Encoders
  - LoRA(s) support
  - Image size presets (Width & Height sliders)
  - Sampling steps, CFG Scale, Shift (for Flux / Flow match models)
  - Sampling methods (Euler a, DPM++ 2M Karras, etc.) and Schedulers (Simple, Karras, Exponential, etc.)
  - Prompt & Negative Prompt with preset styles
  - Gallery history with download and 1-click "Send to Chat" (for vision queries).

### 🌐 Smart Extensions & Integrated Tools
All extensions can be toggled on/off in Settings. When **Smart Intent Auto-Routing** is enabled, the client detects the context and queries the right extension automatically:
1. **Open-Meteo Weather API**: 100% free, no API key needed. Geocodes locations and fetches live conditions + 3-day forecasts.
2. **Wikipedia REST API**: 100% free, fast encyclopedic extracts and canonical citations.
3. **SearXNG API**: Configurable local or remote meta-search engine (default: `http://192.168.1.101:8080/search?q=<query>&format=json`).
4. **DuckDuckGo (DDGS)**: Instant answers and web search snippets without API keys.
5. **Open Library & Gutendex**: Search millions of books, authors, and free Project Gutenberg classics.
6. **ZIM Pro / libzim Offline Reader & Catalog**:
   - Integrated with official `libzim` Python bindings for querying `.zim` archives completely offline without internet.
   - **Download Manager with Exact File Sizes**: View dump sizes before downloading (e.g., Simple Wikipedia 485MB, Wikipedia English Text-Only 4.2GB, with red warnings for >10GB dumps like Wikipedia Full 54GB).

### ⚙️ Settings & User Personalization
- Configure Ollama Base URL, Default Model, and Embedding Model.
- **User Profile Memory**: Set your Name, Occupation, and Custom Instructions which are automatically injected into the system prompt to personalize responses.
- Clear chat history, export all conversations to JSON, and import backups.

---

## 🚀 Quick Start on Windows

1. Double click `start.bat` in the root folder `c:\Softwares\SuperOllama`.
2. The script will verify dependencies, launch the server, and automatically open your default web browser to:
   - **Desktop**: [http://localhost:8000](http://localhost:8000)
   - **Mobile / Local Network**: Open `http://<YOUR_PC_IP>:8000` from your phone or tablet connected to the same Wi-Fi.

Or run manually via Python:
```powershell
cd c:\Softwares\SuperOllama
pip install -r requirements.txt
python main.py
```
