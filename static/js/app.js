/**
 * SuperOllama - Modern Big-Tech AI Studio & Client
 * Complete Single-Page Application Logic
 */

// Global code snippets store for 100% reliable execution and action handling
window._codeStore = window._codeStore || {};

// Application State
const state = {
  activeTab: "chat",
  chats: [],
  activeChatId: null,
  activeProjectId: null,
  activeCharacterId: null,
  activeProjectName: "",
  activeCharacterName: "",
  activeCharacterAvatar: "",
  isIncognito: false,
  models: [],
  currentModel: "",
  isStreaming: false,
  abortController: null,
  attachedImages: [], // base64 strings
  attachedDocs: [],   // list of filenames
  settings: {},
  forgeData: {
    status: {},
    models: [],
    vaes: [],
    text_encoders: [],
    loras: [],
    samplers: [],
    schedulers: []
  },
  sdPresets: [],
  activeSdPreset: null,
  selectedLoras: [], // array of { name: str, weight: float }
  selectedTextEncoders: ["CLIP-L"], // array of selected text encoders
  artifacts: [],
  projects: [],
  characters: [],
  zimCatalog: [],
  installedZims: [],
  theme: localStorage.getItem("superollama_theme") || "slate"
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", async () => {
  applyTheme(state.theme);
  await loadSettings();
  await loadModels();
  await loadSdPresets();
  await loadChats();
  await loadCharacters();
  await loadProjects();
  lucide.createIcons();
  setupEventListeners();

  if (state.chats.length > 0) {
    selectChat(state.chats[0].id);
  } else {
    createNewChat();
  }
});

// --- Theme Management ---
function applyTheme(themeName) {
  state.theme = themeName;
  localStorage.setItem("superollama_theme", themeName);
  document.body.setAttribute("data-theme", themeName);

  const isLight = themeName.includes("light");
  if (isLight) {
    document.documentElement.classList.remove("dark");
  } else {
    document.documentElement.classList.add("dark");
  }

  // Update theme select inputs in settings
  const sel = document.getElementById("setting-theme-select");
  if (sel) sel.value = themeName;

  lucide.createIcons();
}

// --- Tab Navigation ---
function switchTab(tabName) {
  state.activeTab = tabName;
  const tabSections = ["chat", "projects", "characters", "imagine", "artifacts", "settings"];
  tabSections.forEach(t => {
    const el = document.getElementById(`section-${t}`);
    const navBtn = document.getElementById(`nav-btn-${t}`);
    if (el) el.classList.toggle("hidden", t !== tabName);
    if (navBtn) {
      if (t === tabName) {
        navBtn.classList.add("nav-active");
        navBtn.classList.remove("text-slate-400", "hover:bg-[var(--hover-bg)]");
      } else {
        navBtn.classList.remove("nav-active");
        navBtn.classList.add("text-slate-400", "hover:bg-[var(--hover-bg)]");
      }
    }
  });

  closeMobileSidebar();

  if (tabName === "imagine") {
    loadForgeData();
    loadSdPresets();
  }
  if (tabName === "artifacts") loadArtifacts();
  if (tabName === "projects") loadProjects();
  if (tabName === "characters") loadCharacters();
  if (tabName === "settings") {
    loadSettings();
    loadForgeData();
    loadZimCatalog();
  }
  lucide.createIcons();
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById("sidebar-container");
  if (sidebar) sidebar.classList.toggle("open");
}
function closeMobileSidebar() {
  const sidebar = document.getElementById("sidebar-container");
  if (sidebar) sidebar.classList.remove("open");
}

// --- Incognito Mode Toggle ---
function toggleIncognito() {
  state.isIncognito = !state.isIncognito;
  const btn = document.getElementById("incognito-toggle-btn");
  const banner = document.getElementById("incognito-banner");
  
  if (state.isIncognito) {
    if (btn) {
      btn.classList.add("bg-purple-600", "text-white", "incognito-mode-active");
      btn.classList.remove("app-text-muted");
    }
    if (banner) banner.classList.remove("hidden");
    createNewChat(true);
  } else {
    if (btn) {
      btn.classList.remove("bg-purple-600", "text-white", "incognito-mode-active");
      btn.classList.add("app-text-muted");
    }
    if (banner) banner.classList.add("hidden");
    if (state.chats.length > 0) {
      selectChat(state.chats[0].id);
    } else {
      createNewChat(false);
    }
  }
  lucide.createIcons();
}

// --- Ollama Models & Health ---
async function loadModels() {
  try {
    const res = await fetch("/api/settings/ollama-models");
    const data = await res.json();
    state.models = data || [];
    
    const statusPill = document.getElementById("ollama-status-pill");
    const settingsDefaultModelSelect = document.getElementById("setting-default-model-select");

    if (state.models.length > 0) {
      state.currentModel = state.settings.default_model || state.models[0].name;
      if (statusPill) {
        statusPill.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span><span class="text-xs text-emerald-400">Connected</span>`;
      }
    } else {
      state.currentModel = state.settings.default_model || "llama3.2";
      if (statusPill) {
        statusPill.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-500"></span><span class="text-xs text-amber-400">Offline</span>`;
      }
    }

    if (settingsDefaultModelSelect) {
      settingsDefaultModelSelect.innerHTML = `<option value="">Select Default Model...</option>`;
      state.models.forEach(m => {
        settingsDefaultModelSelect.innerHTML += `<option value="${m.name}">${m.name}</option>`;
      });
      if (state.settings.default_model) {
        settingsDefaultModelSelect.value = state.settings.default_model;
      }
    }
  } catch (err) {
    console.warn("Could not reach Ollama:", err);
  }
}

// --- Chats Manager ---
async function loadChats() {
  try {
    const url = state.activeProjectId 
      ? `/api/chat/list?project_id=${state.activeProjectId}` 
      : `/api/chat/list`;
    const res = await fetch(url);
    state.chats = await res.json();
    renderChatHistory();
  } catch (e) {
    console.error("Error loading chats:", e);
  }
}

function renderChatHistory() {
  const container = document.getElementById("chat-history-list");
  if (!container) return;
  container.innerHTML = "";

  if (state.chats.length === 0) {
    container.innerHTML = `<div class="p-4 text-center text-xs app-text-muted">No chats yet. Start one!</div>`;
    return;
  }

  state.chats.forEach(chat => {
    const isActive = chat.id === state.activeChatId;
    const div = document.createElement("div");
    div.className = `group flex items-center justify-between px-3 py-2.5 rounded-xl text-sm cursor-pointer transition-all ${
      isActive 
        ? "bg-[var(--accent)]/15 text-[var(--accent)] font-medium border border-[var(--accent)]/30 shadow-sm" 
        : "text-slate-400 hover:bg-[var(--hover-bg)] hover:text-[var(--text-primary)]"
    }`;

    let badgeHtml = "";
    if (chat.character_avatar || chat.character_name) {
      badgeHtml = `<span class="px-1.5 py-0.5 rounded text-[10px] bg-purple-950/60 text-purple-300 border border-purple-500/30 flex items-center gap-1 shrink-0">${chat.character_avatar || "🤖"} ${escapeHtml(chat.character_name || "")}</span>`;
    } else if (chat.project_name) {
      badgeHtml = `<span class="px-1.5 py-0.5 rounded text-[10px] bg-blue-950/60 text-blue-300 border border-blue-500/30 flex items-center gap-1 shrink-0"><i data-lucide="folder" class="w-2.5 h-2.5"></i> ${escapeHtml(chat.project_name)}</span>`;
    }

    div.innerHTML = `
      <div class="flex items-center gap-2 truncate flex-1" onclick="selectChat('${chat.id}')">
        <i data-lucide="message-square" class="w-4 h-4 shrink-0 text-slate-500"></i>
        <span class="truncate">${escapeHtml(chat.title)}</span>
        ${badgeHtml}
      </div>
      <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button onclick="promptRenameChat('${chat.id}', '${escapeHtml(chat.title)}', event)" class="p-1 hover:text-white rounded" title="Rename">
          <i data-lucide="edit-2" class="w-3.5 h-3.5"></i>
        </button>
        <button onclick="deleteChat('${chat.id}', event)" class="p-1 hover:text-red-400 rounded" title="Delete">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    `;
    container.appendChild(div);
  });
  lucide.createIcons();
}

async function createNewChat(isIncognito = false) {
  if (state.isStreaming) stopGeneration();
  try {
    const res = await fetch("/api/chat/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: isIncognito ? "Incognito Chat" : "New Chat",
        project_id: state.activeProjectId,
        character_id: state.activeCharacterId,
        is_incognito: isIncognito
      })
    });
    const newChat = await res.json();
    state.activeChatId = newChat.id;
    if (!isIncognito) {
      state.chats.unshift(newChat);
      renderChatHistory();
    }
    clearMessagesView();
    updateContextIndicator();
    closeMobileSidebar();
  } catch (e) {
    console.error("Create chat error:", e);
  }
}

async function selectChat(chatId) {
  if (state.isStreaming) stopGeneration();
  state.activeChatId = chatId;
  clearMessagesView();
  closeMobileSidebar();

  try {
    const res = await fetch(`/api/chat/${chatId}`);
    const data = await res.json();
    const chat = data.chat || {};
    const messages = data.messages || [];

    state.activeProjectId = chat.project_id || null;
    state.activeProjectName = chat.project_name || "";
    state.activeCharacterId = chat.character_id || null;
    state.activeCharacterName = chat.character_name || "";
    state.activeCharacterAvatar = chat.character_avatar || "";

    if (chat.character_model) {
      state.currentModel = chat.character_model;
    } else {
      state.currentModel = state.settings.default_model || "";
    }

    updateContextIndicator();
    renderChatHistory();

    if (messages.length === 0) {
      showWelcomeHero();
    } else {
      hideWelcomeHero();
      messages.forEach(msg => {
        appendMessage(msg.role, msg.content, {
          thinking: msg.thinking,
          tools_used: msg.tools_used,
          images: msg.images
        });
      });
    }
    scrollToBottom();
  } catch (e) {
    console.error("Load chat details error:", e);
  }
}

function updateContextIndicator() {
  const bar = document.getElementById("chat-context-indicator-bar");
  const charPill = document.getElementById("context-character-pill");
  const projPill = document.getElementById("context-project-pill");
  const input = document.getElementById("chat-input-textarea");

  if (!bar) return;
  let hasContext = false;

  if (state.activeCharacterId && state.activeCharacterName) {
    hasContext = true;
    charPill.classList.remove("hidden");
    charPill.innerHTML = `
      <div class="flex items-center gap-1.5">
        <span class="text-base">${state.activeCharacterAvatar || "🤖"}</span>
        <span class="font-semibold text-purple-300">${escapeHtml(state.activeCharacterName)}</span>
        <span class="text-[10px] app-text-muted">(${state.currentModel || "Default"})</span>
      </div>
      <button onclick="exitCharacterContext()" class="p-0.5 hover:text-white rounded" title="Exit Character">
        <i data-lucide="x" class="w-3.5 h-3.5"></i>
      </button>
    `;
    if (input) input.placeholder = `Talking to ${state.activeCharacterName}...`;
  } else {
    charPill.classList.add("hidden");
  }

  if (state.activeProjectId && state.activeProjectName) {
    hasContext = true;
    projPill.classList.remove("hidden");
    projPill.innerHTML = `
      <div class="flex items-center gap-1.5">
        <i data-lucide="folder-kanban" class="w-3.5 h-3.5 text-blue-400"></i>
        <span class="font-semibold text-blue-300">Project: ${escapeHtml(state.activeProjectName)}</span>
      </div>
      <button onclick="exitProjectContext()" class="p-0.5 hover:text-white rounded" title="Exit Project">
        <i data-lucide="x" class="w-3.5 h-3.5"></i>
      </button>
    `;
    if (input && !state.activeCharacterId) input.placeholder = `Chatting in ${state.activeProjectName}...`;
  } else {
    projPill.classList.add("hidden");
  }

  if (hasContext) {
    bar.classList.remove("hidden");
  } else {
    bar.classList.add("hidden");
    if (input) input.placeholder = "Ask anything, run code, or attach documents...";
  }

  lucide.createIcons();
}

function exitCharacterContext() {
  state.activeCharacterId = null;
  state.activeCharacterName = "";
  state.activeCharacterAvatar = "";
  updateContextIndicator();
}

function exitProjectContext() {
  state.activeProjectId = null;
  state.activeProjectName = "";
  updateContextIndicator();
  loadChats();
}

async function deleteChat(chatId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Are you sure you want to delete this conversation?")) return;
  try {
    await fetch(`/api/chat/${chatId}`, { method: "DELETE" });
    state.chats = state.chats.filter(c => c.id !== chatId);
    if (state.activeChatId === chatId) {
      if (state.chats.length > 0) {
        selectChat(state.chats[0].id);
      } else {
        createNewChat();
      }
    } else {
      renderChatHistory();
    }
  } catch (err) {
    console.error("Delete chat error:", err);
  }
}

async function promptRenameChat(chatId, oldTitle, e) {
  if (e) e.stopPropagation();
  const newTitle = prompt("Enter conversation title:", oldTitle);
  if (!newTitle || newTitle.trim() === "") return;
  try {
    await fetch(`/api/chat/${chatId}/rename`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle.trim() })
    });
    const c = state.chats.find(item => item.id === chatId);
    if (c) c.title = newTitle.trim();
    renderChatHistory();
  } catch (err) {
    console.error("Rename chat error:", err);
  }
}

// --- Messaging & SSE Streaming ---
function clearMessagesView() {
  const container = document.getElementById("chat-messages-container");
  if (container) container.innerHTML = "";
  showWelcomeHero();
}

function showWelcomeHero() {
  const hero = document.getElementById("chat-welcome-hero");
  if (hero) hero.classList.remove("hidden");
}
function hideWelcomeHero() {
  const hero = document.getElementById("chat-welcome-hero");
  if (hero) hero.classList.add("hidden");
}

function scrollToBottom() {
  const scrollArea = document.getElementById("chat-scroll-area");
  if (scrollArea) {
    scrollArea.scrollTop = scrollArea.scrollHeight;
  }
}

async function sendMessage() {
  const input = document.getElementById("chat-input-textarea");
  const text = input.value.trim();
  if (!text && state.attachedImages.length === 0) return;
  if (state.isStreaming) return;

  hideWelcomeHero();
  const currentImages = [...state.attachedImages];
  state.attachedImages = [];
  renderAttachedThumbnails();

  appendMessage("user", text, { images: currentImages });
  input.value = "";
  input.style.height = "auto";
  scrollToBottom();

  const assistantBubble = createAssistantMessagePlaceholder();
  state.isStreaming = true;
  updateSendStopButton(true);

  const selectedModel = state.currentModel || state.settings.default_model;

  try {
    state.abortController = new AbortController();
    const response = await fetch("/api/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: state.abortController.signal,
      body: JSON.stringify({
        chat_id: state.activeChatId,
        message: text,
        model: selectedModel,
        images: currentImages,
        is_incognito: state.isIncognito
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedContent = "";
    let accumulatedThinking = "";
    let thinkingStartTime = Date.now();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n\n");

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.replace("data: ", "").trim();
        if (!jsonStr) continue;

        try {
          const data = JSON.parse(jsonStr);

          if (data.type === "tool") {
            renderToolBadge(assistantBubble, data.tool, data.icon, data.summary);
          } else if (data.type === "thinking") {
            accumulatedThinking += data.delta;
            const elapsed = Math.round((Date.now() - thinkingStartTime) / 1000);
            updateThinkingBox(assistantBubble, accumulatedThinking, elapsed);
          } else if (data.type === "content") {
            accumulatedContent += data.delta;
            updateAssistantContent(assistantBubble, accumulatedContent);
          } else if (data.type === "done") {
            finalizeAssistantContent(assistantBubble, accumulatedContent);
            if (!state.isIncognito) {
              loadChats();
            }
          } else if (data.type === "error") {
            renderAssistantError(assistantBubble, data.error);
          }
        } catch (err) {
          console.error("SSE parse error:", err);
        }
      }
      scrollToBottom();
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      renderAssistantError(assistantBubble, `Request error: ${err.message}`);
    }
  } finally {
    state.isStreaming = false;
    updateSendStopButton(false);
    scrollToBottom();
  }
}

function stopGeneration() {
  if (state.abortController) {
    state.abortController.abort();
    state.abortController = null;
  }
  state.isStreaming = false;
  updateSendStopButton(false);
}

function updateSendStopButton(isStreaming) {
  const sendBtn = document.getElementById("chat-send-btn");
  if (!sendBtn) return;
  if (isStreaming) {
    sendBtn.innerHTML = `<i data-lucide="square" class="w-4 h-4 text-white"></i>`;
    sendBtn.className = "w-8 h-8 rounded-xl bg-red-600 hover:bg-red-700 flex items-center justify-center text-white transition-all shadow-md";
    sendBtn.onclick = stopGeneration;
  } else {
    sendBtn.innerHTML = `<i data-lucide="arrow-up" class="w-4 h-4 text-white"></i>`;
    sendBtn.className = "w-8 h-8 rounded-xl btn-accent flex items-center justify-center text-white transition-all shadow-md";
    sendBtn.onclick = sendMessage;
  }
  lucide.createIcons();
}

// --- DOM Message Rendering & Copy Buttons ---
function appendMessage(role, content, extra = {}) {
  const container = document.getElementById("chat-messages-container");
  if (!container) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = `flex gap-4 p-5 md:p-6 max-w-4xl mx-auto w-full transition-all ${
    role === "user" ? "bg-[var(--bubble-user)] rounded-2xl border app-border shadow-sm" : ""
  }`;

  const avatarHtml = role === "user"
    ? `<div class="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shrink-0">U</div>`
    : `<div class="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-pink-500 flex items-center justify-center text-white shrink-0"><i data-lucide="sparkles" class="w-4 h-4"></i></div>`;

  let imagesHtml = "";
  if (extra.images && extra.images.length > 0) {
    imagesHtml = `<div class="flex flex-wrap gap-2 mb-3">` +
      extra.images.map(img => `<img src="data:image/png;base64,${img}" class="w-24 h-24 object-cover rounded-xl border app-border shadow" />`).join("") +
      `</div>`;
  }

  let toolsHtml = "";
  if (extra.tools_used && extra.tools_used.length > 0) {
    toolsHtml = extra.tools_used.map(t => `
      <div class="tool-badge">
        <span>${t.icon || "⚙️"}</span>
        <span>${escapeHtml(t.tool || "Tool")}</span>
        <span class="app-text-muted font-normal">| ${escapeHtml(t.summary || "")}</span>
      </div>
    `).join("");
  }

  let thinkingHtml = "";
  if (extra.thinking && extra.thinking.trim()) {
    thinkingHtml = `
      <div class="thinking-box">
        <div class="thinking-header" onclick="toggleThinking(this)">
          <div class="flex items-center gap-2">
            <i data-lucide="brain" class="w-4 h-4 text-purple-400"></i>
            <span>Thought Process</span>
          </div>
          <i data-lucide="chevron-down" class="w-4 h-4 transition-transform"></i>
        </div>
        <div class="thinking-content hidden">${escapeHtml(extra.thinking)}</div>
      </div>
    `;
  }

  const parsedContent = formatMarkdown(content);

  // Message Bottom Action Bar with Copy Button
  const actionBarHtml = `
    <div class="msg-action-bar">
      <button class="msg-action-btn" onclick="copyMessageBody(this)" title="Copy message text">
        <i data-lucide="copy" class="w-3.5 h-3.5"></i>
        <span>Copy</span>
      </button>
      <span class="app-text-muted text-[10px] ml-auto">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
  `;

  msgDiv.innerHTML = `
    ${avatarHtml}
    <div class="flex-1 overflow-hidden leading-relaxed text-sm md:text-base">
      ${imagesHtml}
      ${toolsHtml}
      ${thinkingHtml}
      <div class="prose-custom max-w-none break-words text-[var(--text-primary)]">${parsedContent}</div>
      ${actionBarHtml}
    </div>
  `;

  container.appendChild(msgDiv);
  lucide.createIcons();
}

function copyMessageBody(btn) {
  const msgWrapper = btn.closest(".msg-action-bar").previousElementSibling;
  if (!msgWrapper) return;
  const text = msgWrapper.innerText || msgWrapper.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.innerHTML;
    btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i> <span class="text-emerald-400">Copied!</span>`;
    lucide.createIcons();
    setTimeout(() => {
      btn.innerHTML = original;
      lucide.createIcons();
    }, 2000);
  });
}

function createAssistantMessagePlaceholder() {
  const container = document.getElementById("chat-messages-container");
  const msgDiv = document.createElement("div");
  msgDiv.className = "flex gap-4 p-5 md:p-6 max-w-4xl mx-auto w-full";

  msgDiv.innerHTML = `
    <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-pink-500 flex items-center justify-center text-white shrink-0">
      <i data-lucide="sparkles" class="w-4 h-4"></i>
    </div>
    <div class="flex-1 overflow-hidden leading-relaxed text-sm md:text-base">
      <div class="tools-container"></div>
      <div class="thinking-container"></div>
      <div class="content-body prose-custom max-w-none break-words text-[var(--text-primary)]">
        <div class="flex items-center gap-2 app-text-muted text-sm">
          <span class="w-2 h-2 rounded-full bg-purple-500 animate-ping"></span>
          <span>Thinking...</span>
        </div>
      </div>
      <div class="msg-action-bar hidden">
        <button class="msg-action-btn" onclick="copyMessageBody(this)" title="Copy message text">
          <i data-lucide="copy" class="w-3.5 h-3.5"></i>
          <span>Copy</span>
        </button>
      </div>
    </div>
  `;

  container.appendChild(msgDiv);
  lucide.createIcons();
  return msgDiv;
}

function renderToolBadge(msgDiv, toolName, icon, summary) {
  const container = msgDiv.querySelector(".tools-container");
  if (!container) return;
  const badge = document.createElement("div");
  badge.className = "tool-badge";
  badge.innerHTML = `
    <span>${icon || "⚙️"}</span>
    <span>${escapeHtml(toolName)}</span>
    <span class="app-text-muted font-normal">| ${escapeHtml(summary || "")}</span>
  `;
  container.appendChild(badge);
}

function updateThinkingBox(msgDiv, thinkingText, elapsedSec) {
  const container = msgDiv.querySelector(".thinking-container");
  if (!container) return;

  let box = container.querySelector(".thinking-box");
  if (!box) {
    box = document.createElement("div");
    box.className = "thinking-box";
    box.innerHTML = `
      <div class="thinking-header" onclick="toggleThinking(this)">
        <div class="flex items-center gap-2">
          <i data-lucide="brain" class="w-4 h-4 text-purple-400 brain-pulsing"></i>
          <span class="thinking-label">Thinking (${elapsedSec}s)</span>
        </div>
        <i data-lucide="chevron-down" class="w-4 h-4 transition-transform"></i>
      </div>
      <div class="thinking-content">${escapeHtml(thinkingText)}</div>
    `;
    container.appendChild(box);
    lucide.createIcons();
  } else {
    const label = box.querySelector(".thinking-label");
    const content = box.querySelector(".thinking-content");
    if (label) label.textContent = `Thinking (${elapsedSec}s)`;
    if (content) content.textContent = thinkingText;
  }
}

function toggleThinking(headerEl) {
  const content = headerEl.nextElementSibling;
  const chevron = headerEl.querySelector("[data-lucide='chevron-down']");
  if (content) {
    content.classList.toggle("hidden");
    if (chevron) chevron.classList.toggle("rotate-180");
  }
}

function updateAssistantContent(msgDiv, rawMarkdown) {
  const body = msgDiv.querySelector(".content-body");
  if (body) {
    body.innerHTML = formatMarkdown(rawMarkdown);
    lucide.createIcons();
  }
}

function finalizeAssistantContent(msgDiv, rawMarkdown) {
  const body = msgDiv.querySelector(".content-body");
  if (body) {
    body.innerHTML = formatMarkdown(rawMarkdown);
  }
  const pulsingBrain = msgDiv.querySelector(".brain-pulsing");
  if (pulsingBrain) pulsingBrain.classList.remove("brain-pulsing");
  
  const bar = msgDiv.querySelector(".msg-action-bar");
  if (bar) bar.classList.remove("hidden");
  
  lucide.createIcons();
}

function renderAssistantError(msgDiv, errorText) {
  const body = msgDiv.querySelector(".content-body");
  if (body) {
    body.innerHTML = `<div class="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-red-400 text-sm flex items-center gap-2"><i data-lucide="alert-triangle" class="w-4 h-4 shrink-0"></i><span>${escapeHtml(errorText)}</span></div>`;
    lucide.createIcons();
  }
}

// --- 100% Robust Markdown & Code Block Formatter ---
function formatMarkdown(text) {
  if (!text) return "";

  try {
    const renderer = new marked.Renderer();

    renderer.code = function(arg1, arg2) {
      let code = "";
      let lang = "text";

      if (typeof arg1 === "object" && arg1 !== null) {
        code = arg1.text || "";
        lang = (arg1.lang || "text").toLowerCase();
      } else {
        code = String(arg1 || "");
        lang = String(arg2 || "text").toLowerCase();
      }

      // Syntax highlight
      let highlightedCode = escapeHtml(code);
      if (lang && hljs.getLanguage(lang)) {
        try {
          highlightedCode = hljs.highlight(code, { language: lang }).value;
        } catch (e) {}
      } else {
        try {
          highlightedCode = hljs.highlightAuto(code).value;
        } catch (e) {}
      }

      // Generate unique snippet ID and store in memory (ZERO quoting/escaping bugs!)
      const snippetId = "snip_" + Math.random().toString(36).substring(2, 10);
      const cleanTitle = deduceFileName(code, lang);
      window._codeStore[snippetId] = {
        code: code,
        lang: lang,
        title: cleanTitle
      };

      const canRun = ["html", "javascript", "js", "svg", "python", "py"].includes(lang);

      return `
        <div class="code-box-container" data-snippet-id="${snippetId}">
          <div class="code-box-header">
            <div class="flex items-center gap-2 font-mono text-xs">
              <span class="w-2.5 h-2.5 rounded-full bg-slate-500"></span>
              <span class="text-slate-200 font-semibold uppercase">${lang}</span>
              <span class="text-slate-400 text-[11px]">${cleanTitle}</span>
            </div>
            <div class="code-box-actions">
              ${canRun ? `
                <button class="code-btn" onclick="handleCodeAction('run', '${snippetId}', this)" title="Run code live">
                  <i data-lucide="play" class="w-3.5 h-3.5 text-emerald-400"></i> Run
                </button>
              ` : ""}
              <button class="code-btn" onclick="handleCodeAction('save', '${snippetId}', this)" title="Save to PC & Artifacts">
                <i data-lucide="save" class="w-3.5 h-3.5 text-purple-400"></i> Save
              </button>
              <button class="code-btn" onclick="handleCodeAction('download', '${snippetId}', this)" title="Download file to computer">
                <i data-lucide="download" class="w-3.5 h-3.5 text-blue-400"></i> Download
              </button>
              <button class="code-btn" onclick="handleCodeAction('copy', '${snippetId}', this)" title="Copy code">
                <i data-lucide="copy" class="w-3.5 h-3.5"></i> Copy
              </button>
            </div>
          </div>
          <pre class="code-box-pre"><code class="hljs language-${lang}">${highlightedCode}</code></pre>
        </div>
      `;
    };

    return marked.parse(text, { renderer: renderer, breaks: true, gfm: true });
  } catch (err) {
    console.error("formatMarkdown error:", err);
    return `<pre class="p-3 bg-slate-900 rounded-lg text-xs overflow-auto text-slate-200">${escapeHtml(text)}</pre>`;
  }
}

// Single handler for all code actions ensuring 100% reliable execution
function handleCodeAction(action, snippetId, btn) {
  let snippet = window._codeStore[snippetId];

  // Fallback: extract directly from DOM element
  if (!snippet && btn) {
    const container = btn.closest(".code-box-container");
    if (container) {
      const codeEl = container.querySelector("code");
      const codeText = codeEl ? codeEl.textContent : "";
      snippet = {
        code: codeText,
        lang: "text",
        title: "snippet.txt"
      };
    }
  }

  if (!snippet) {
    alert("Code snippet could not be retrieved.");
    return;
  }

  const { code, lang, title } = snippet;

  // 1. COPY
  if (action === "copy") {
    navigator.clipboard.writeText(code).then(() => {
      const original = btn.innerHTML;
      btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i> <span class="text-emerald-400">Copied!</span>`;
      lucide.createIcons();
      setTimeout(() => {
        btn.innerHTML = original;
        lucide.createIcons();
      }, 2000);
    });
  }

  // 2. DOWNLOAD
  else if (action === "download") {
    const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = title || `snippet.${lang}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // 3. SAVE TO ARTIFACTS & PC DISK
  else if (action === "save") {
    saveToArtifacts(title, lang, code);
  }

  // 4. RUN LIVE
  else if (action === "run") {
    runCodeSnippet(lang, code);
  }
}

function deduceFileName(code, lang) {
  if (!code) return `snippet.${lang}`;
  const firstLine = String(code).split("\n")[0].trim();
  const match = firstLine.match(/(?:filename:|file:|\/\/|#|<!--)\s*([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)/i);
  if (match && match[1]) {
    return match[1];
  }

  const extMap = {
    python: "script.py", py: "script.py",
    javascript: "app.js", js: "app.js",
    typescript: "main.ts", ts: "main.ts",
    html: "index.html",
    css: "styles.css",
    json: "data.json",
    markdown: "document.md", md: "document.md",
    sql: "query.sql",
    cpp: "main.cpp", c: "main.c",
    rust: "main.rs", go: "main.go"
  };
  return extMap[lang] || `snippet.${lang}`;
}

async function saveToArtifacts(title, lang, code) {
  try {
    const res = await fetch("/api/artifacts/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title,
        language: lang,
        code: code,
        chat_id: state.activeChatId
      })
    });
    const data = await res.json();
    if (data.success) {
      alert(`Artifact saved successfully!\nSaved on your PC at:\n${data.file_path}`);
      loadArtifacts();
    }
  } catch (err) {
    alert("Error saving artifact: " + err.message);
  }
}

// --- Live Sandbox Code Runner ---
async function runCodeSnippet(lang, code) {
  const modal = document.getElementById("code-sandbox-modal");
  const iframe = document.getElementById("sandbox-preview-iframe");
  const consoleOutput = document.getElementById("sandbox-console-output");
  const title = document.getElementById("sandbox-modal-title");

  if (!modal) return;
  modal.classList.remove("hidden");
  title.textContent = `Running ${lang.toUpperCase()} App`;

  if (["html", "javascript", "js", "svg"].includes(lang.toLowerCase())) {
    iframe.classList.remove("hidden");
    consoleOutput.classList.add("hidden");

    let fullHtml = code;
    if (lang === "javascript" || lang === "js") {
      fullHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:sans-serif;padding:24px;color:#f8fafc;background:#0b0f19;line-height:1.6;}</style></head><body><div id="app"></div><div id="output"></div><script>console.log = function(...args){ document.getElementById('output').innerHTML += '<div style=\"font-family:monospace;padding:4px 0;\">' + args.join(' ') + '</div>'; }; try { ${code} } catch(e) { console.log('Error: ' + e.message); }</script></body></html>`;
    }
    iframe.srcdoc = fullHtml;
  } else if (["python", "py"].includes(lang.toLowerCase())) {
    iframe.classList.add("hidden");
    consoleOutput.classList.remove("hidden");
    consoleOutput.textContent = "Executing Python script in isolated subprocess on Windows...";

    try {
      const res = await fetch("/api/sandbox/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code, language: "python", timeout_sec: 10 })
      });
      const data = await res.json();
      let outStr = `[Execution finished in ${data.elapsed_ms}ms with Exit Code ${data.exit_code}]\n\n`;
      if (data.stdout) outStr += `--- STDOUT ---\n${data.stdout}\n`;
      if (data.stderr) outStr += `--- STDERR ---\n${data.stderr}\n`;
      if (!data.stdout && !data.stderr) outStr += "(No output returned)";
      consoleOutput.textContent = outStr;
    } catch (err) {
      consoleOutput.textContent = `Execution failed: ${err.message}`;
    }
  }
}

function closeSandboxModal() {
  const modal = document.getElementById("code-sandbox-modal");
  const iframe = document.getElementById("sandbox-preview-iframe");
  if (modal) modal.classList.add("hidden");
  if (iframe) iframe.srcdoc = "";
}

// --- Attachments & Vision / RAG File Upload ---
async function handleFileUpload(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  if (state.activeChatId) formData.append("chat_id", state.activeChatId);
  if (state.activeProjectId) formData.append("project_id", state.activeProjectId);

  try {
    const res = await fetch("/api/chat/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (data.success) {
      if (data.is_image) {
        state.attachedImages.push(data.base64);
        renderAttachedThumbnails();
      } else {
        alert(`Indexed "${data.filename}" into RAG Knowledge Base (${data.rag_chunks} chunks)!`);
      }
    }
  } catch (err) {
    alert("File upload error: " + err.message);
  }
}

function renderAttachedThumbnails() {
  const container = document.getElementById("attached-thumbnails-bar");
  if (!container) return;
  container.innerHTML = "";
  if (state.attachedImages.length === 0) {
    container.classList.add("hidden");
    return;
  }
  container.classList.remove("hidden");

  state.attachedImages.forEach((b64, idx) => {
    const thumb = document.createElement("div");
    thumb.className = "relative inline-block";
    thumb.innerHTML = `
      <img src="data:image/png;base64,${b64}" class="w-14 h-14 object-cover rounded-lg border app-border shadow" />
      <button onclick="removeAttachedImage(${idx})" class="absolute -top-1.5 -right-1.5 bg-red-600 text-white rounded-full p-0.5 shadow">
        <i data-lucide="x" class="w-3 h-3"></i>
      </button>
    `;
    container.appendChild(thumb);
  });
  lucide.createIcons();
}

function removeAttachedImage(idx) {
  state.attachedImages.splice(idx, 1);
  renderAttachedThumbnails();
}

// --- Projects Section ---
async function loadProjects() {
  try {
    const res = await fetch("/api/projects/list");
    state.projects = await res.json();
    renderProjectsList();
  } catch (e) {
    console.error("Load projects error:", e);
  }
}

function renderProjectsList() {
  const container = document.getElementById("projects-grid");
  if (!container) return;
  container.innerHTML = "";

  state.projects.forEach(p => {
    const card = document.createElement("div");
    card.className = "p-5 rounded-2xl border app-card hover:border-[var(--accent)] transition-all flex flex-col justify-between";
    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between mb-3">
          <div class="w-10 h-10 rounded-xl bg-blue-600/15 text-blue-500 flex items-center justify-center font-bold">
            <i data-lucide="folder-kanban" class="w-5 h-5"></i>
          </div>
          <button onclick="deleteProject('${p.id}', event)" class="app-text-muted hover:text-red-400 p-1">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
        <h3 class="font-semibold text-lg mb-1">${escapeHtml(p.name)}</h3>
        <p class="text-xs app-text-secondary mb-4 line-clamp-2">${escapeHtml(p.description || "No description")}</p>
      </div>
      <div class="flex items-center justify-between pt-4 border-t app-border">
        <div class="text-xs app-text-muted">
          <span>${p.chat_count} chats</span> • <span>${p.doc_count} docs</span>
        </div>
        <button onclick="openProjectWorkspace('${p.id}', '${escapeHtml(p.name)}')" class="px-3.5 py-1.5 btn-accent text-white text-xs font-medium rounded-lg">
          Open Workspace
        </button>
      </div>
    `;
    container.appendChild(card);
  });
  lucide.createIcons();
}

async function createNewProjectModal() {
  const name = prompt("Enter Project Name:");
  if (!name) return;
  const desc = prompt("Enter Project Description / Goal:");
  const promptText = prompt("Enter Custom Project Instructions / System Prompt (optional):");

  try {
    const res = await fetch("/api/projects/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, description: desc || "", system_prompt: promptText || "" })
    });
    if (res.ok) {
      await loadProjects();
    }
  } catch (err) {
    alert("Create project error: " + err.message);
  }
}

async function openProjectWorkspace(projectId, projectName) {
  state.activeProjectId = projectId;
  state.activeProjectName = projectName;
  switchTab("chat");
  await loadChats();
  createNewChat();
}

async function deleteProject(projectId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Delete project and its knowledge base?")) return;
  try {
    await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
    await loadProjects();
    if (state.activeProjectId === projectId) {
      exitProjectContext();
    }
  } catch (err) {
    alert("Delete error: " + err.message);
  }
}

// --- Characters Section ---
async function loadCharacters() {
  try {
    const res = await fetch("/api/characters/list");
    state.characters = await res.json();
    renderCharactersList();
  } catch (e) {
    console.error("Load characters error:", e);
  }
}

function renderCharactersList() {
  const container = document.getElementById("characters-grid");
  if (!container) return;
  container.innerHTML = "";

  state.characters.forEach(c => {
    const card = document.createElement("div");
    card.className = "p-5 rounded-2xl border app-card hover:border-[var(--accent)] transition-all flex flex-col justify-between";
    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-2xl bg-purple-600/15 border border-purple-500/20 flex items-center justify-center text-2xl shadow">
              ${c.avatar || "🤖"}
            </div>
            <div>
              <h3 class="font-semibold text-base">${escapeHtml(c.name)}</h3>
              <span class="text-[11px] text-purple-400 font-mono">${c.default_model || "Use Default Model"}</span>
            </div>
          </div>
          <button onclick="deleteCharacter('${c.id}', event)" class="app-text-muted hover:text-red-400 p-1">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
        <p class="text-xs app-text-secondary mb-4 line-clamp-3">${escapeHtml(c.description || c.system_prompt)}</p>
      </div>
      <div class="flex items-center justify-between pt-4 border-t app-border">
        <span class="text-xs app-text-muted">Temp: ${c.temperature}</span>
        <button onclick="startChatWithCharacter('${c.id}')" class="px-3.5 py-1.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:opacity-90 text-white text-xs font-medium rounded-lg">
          Chat
        </button>
      </div>
    `;
    container.appendChild(card);
  });
  lucide.createIcons();
}

function openCreateCharacterModal() {
  const modal = document.getElementById("character-create-modal");
  const modelSelect = document.getElementById("char-model-select");
  if (modelSelect) {
    modelSelect.innerHTML = `<option value="">System Default Model</option>`;
    state.models.forEach(m => {
      modelSelect.innerHTML += `<option value="${m.name}">${m.name}</option>`;
    });
  }
  if (modal) modal.classList.remove("hidden");
}

function closeCreateCharacterModal() {
  const modal = document.getElementById("character-create-modal");
  if (modal) modal.classList.add("hidden");
}

async function submitCreateCharacter() {
  const name = document.getElementById("char-name-input").value.trim();
  const avatar = document.getElementById("char-avatar-input").value.trim() || "🤖";
  const desc = document.getElementById("char-desc-input").value.trim();
  const promptText = document.getElementById("char-prompt-input").value.trim();
  const model = document.getElementById("char-model-select").value;
  const temp = parseFloat(document.getElementById("char-temp-input").value) || 0.7;

  if (!name || !promptText) {
    alert("Please provide character name and system prompt instructions.");
    return;
  }

  try {
    const res = await fetch("/api/characters/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        avatar: avatar,
        description: desc,
        system_prompt: promptText,
        default_model: model,
        temperature: temp
      })
    });
    if (res.ok) {
      closeCreateCharacterModal();
      await loadCharacters();
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function deleteCharacter(charId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Delete this character persona?")) return;
  try {
    await fetch(`/api/characters/${charId}`, { method: "DELETE" });
    await loadCharacters();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function startChatWithCharacter(charId) {
  state.activeCharacterId = charId;
  const char = state.characters.find(c => c.id === charId);
  if (char) {
    state.activeCharacterName = char.name;
    state.activeCharacterAvatar = char.avatar;
    if (char.default_model) {
      state.currentModel = char.default_model;
    }
  }
  switchTab("chat");
  await createNewChat();
}

// --- Stable Diffusion Presets & Studio ---
async function loadSdPresets() {
  try {
    const res = await fetch("/api/imagine/presets");
    state.sdPresets = await res.json();
    
    const select = document.getElementById("sd-preset-select");
    if (select) {
      select.innerHTML = `<option value="">⚡ Load Preset...</option>`;
      state.sdPresets.forEach(p => {
        select.innerHTML += `<option value="${p.id}">${escapeHtml(p.name)}</option>`;
      });
    }

    renderSettingsPresetsList();
  } catch (err) {
    console.error("Load presets error:", err);
  }
}

function renderSettingsPresetsList() {
  const container = document.getElementById("settings-presets-list");
  if (!container) return;
  container.innerHTML = "";

  state.sdPresets.forEach(p => {
    const item = document.createElement("div");
    item.className = "p-3 rounded-xl border app-border app-input flex items-center justify-between";
    const encodersStr = p.text_encoders && p.text_encoders.length > 0 ? p.text_encoders.join(", ") : (p.text_encoder || "None");
    item.innerHTML = `
      <div>
        <div class="font-semibold text-xs">${escapeHtml(p.name)}</div>
        <div class="text-[11px] app-text-muted">Sampler: ${p.sampler_name} • Steps: ${p.steps} • CFG: ${p.cfg_scale} • Encoders: ${escapeHtml(encodersStr)}</div>
      </div>
      <button onclick="deleteSdPreset('${p.id}')" class="p-1 hover:text-red-400 text-slate-500" title="Delete preset">
        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
      </button>
    `;
    container.appendChild(item);
  });
  lucide.createIcons();
}

async function saveCurrentSettingsAsPreset() {
  const name = prompt("Enter a name for this Stable Diffusion Preset (e.g. 'Flux High Quality', 'SDXL Anime'):");
  if (!name) return;

  const payload = {
    name: name,
    checkpoint: getInputValue("sd-checkpoint-select"),
    vae: getInputValue("sd-vae-select"),
    clip_skip: parseInt(getInputValue("sd-clipskip-input")) || 1,
    text_encoders: state.selectedTextEncoders,
    loras: state.selectedLoras,
    steps: parseInt(getInputValue("sd-steps-input")) || 25,
    cfg_scale: parseFloat(getInputValue("sd-cfg-input")) || 7.0,
    shift: parseFloat(getInputValue("sd-shift-input")) || 1.0,
    sampler_name: getInputValue("sd-sampler-select"),
    scheduler: getInputValue("sd-scheduler-select"),
    width: parseInt(getInputValue("sd-width-input")) || 1024,
    height: parseInt(getInputValue("sd-height-input")) || 1024,
    negative_prompt: getInputValue("sd-neg-prompt-input")
  };

  try {
    const res = await fetch("/api/imagine/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert(`Preset "${name}" saved!`);
      await loadSdPresets();
    }
  } catch (err) {
    alert("Error saving preset: " + err.message);
  }
}

async function deleteSdPreset(id) {
  if (!confirm("Delete this preset?")) return;
  await fetch(`/api/imagine/presets/${id}`, { method: "DELETE" });
  await loadSdPresets();
}

function applySdPreset(presetId) {
  const preset = state.sdPresets.find(p => p.id === presetId);
  if (!preset) return;

  setInputValue("sd-checkpoint-select", preset.checkpoint);
  setInputValue("sd-vae-select", preset.vae || "Automatic");
  setInputValue("sd-clipskip-input", preset.clip_skip || 1);
  setInputValue("sd-sampler-select", preset.sampler_name || "Euler a");
  setInputValue("sd-scheduler-select", preset.scheduler || "Simple");
  setInputValue("sd-steps-input", preset.steps || 25);
  setInputValue("sd-cfg-input", preset.cfg_scale || 7.0);
  setInputValue("sd-shift-input", preset.shift || 1.0);
  setInputValue("sd-width-input", preset.width || 1024);
  setInputValue("sd-height-input", preset.height || 1024);
  if (preset.negative_prompt) setInputValue("sd-neg-prompt-input", preset.negative_prompt);

  state.selectedLoras = preset.loras || [];
  renderSelectedLoras();

  state.selectedTextEncoders = preset.text_encoders || (preset.text_encoder && preset.text_encoder !== "None" ? [preset.text_encoder] : []);
  renderTextEncodersSelector();
}

async function loadForgeData() {
  try {
    const res = await fetch("/api/imagine/status");
    const data = await res.json();
    state.forgeData = data;

    // Checkpoints
    const cpSelect = document.getElementById("sd-checkpoint-select");
    if (cpSelect && data.models) {
      const curr = cpSelect.value;
      cpSelect.innerHTML = `<option value="">Auto / Current Checkpoint</option>`;
      data.models.forEach(m => {
        const title = m.model_name || m.title;
        cpSelect.innerHTML += `<option value="${escapeHtml(title)}">${escapeHtml(title)}</option>`;
      });
      if (curr) cpSelect.value = curr;
    }

    // VAEs (None, Automatic, custom)
    const vaeSelect = document.getElementById("sd-vae-select");
    if (vaeSelect && data.vaes) {
      const curr = vaeSelect.value;
      vaeSelect.innerHTML = "";
      data.vaes.forEach(v => {
        vaeSelect.innerHTML += `<option value="${escapeHtml(v.model_name)}">${escapeHtml(v.model_name)}</option>`;
      });
      vaeSelect.value = curr || "Automatic";
    }

    // Text Encoders list
    renderTextEncodersSelector();

    // Samplers
    const samplerSelect = document.getElementById("sd-sampler-select");
    if (samplerSelect && data.samplers) {
      const curr = samplerSelect.value;
      samplerSelect.innerHTML = "";
      data.samplers.forEach(s => {
        samplerSelect.innerHTML += `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)}</option>`;
      });
      if (curr) samplerSelect.value = curr;
    }

    // Schedulers
    const schedSelect = document.getElementById("sd-scheduler-select");
    if (schedSelect && data.schedulers) {
      const curr = schedSelect.value;
      schedSelect.innerHTML = "";
      data.schedulers.forEach(s => {
        schedSelect.innerHTML += `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)}</option>`;
      });
      if (curr) schedSelect.value = curr;
    }

    // LoRA pickers (in Imagine studio & in Settings)
    ["sd-lora-picker-select", "setting-sd-lora-picker-select"].forEach(id => {
      const loraPicker = document.getElementById(id);
      if (loraPicker && data.loras) {
        loraPicker.innerHTML = `<option value="">+ Add LoRA...</option>`;
        data.loras.forEach(l => {
          loraPicker.innerHTML += `<option value="${escapeHtml(l.name)}">${escapeHtml(l.name)}</option>`;
        });
      }
    });

    loadImagineGallery();
  } catch (err) {
    console.error("Load Forge data error:", err);
  }
}

// Multi-Text Encoder selection
function renderTextEncodersSelector() {
  const container = document.getElementById("sd-textencoders-pills-container");
  if (!container) return;
  container.innerHTML = "";

  const availableEncoders = ["CLIP-L", "CLIP-G", "T5-XXL", "OpenCLIP", "Dual CLIP"];
  if (state.forgeData.text_encoders) {
    state.forgeData.text_encoders.forEach(te => {
      if (te && !["None", "Automatic"].includes(te) && !availableEncoders.includes(te)) {
        availableEncoders.push(te);
      }
    });
  }

  availableEncoders.forEach(name => {
    const isSelected = state.selectedTextEncoders.includes(name);
    const chip = document.createElement("button");
    chip.type = "button";
    chip.onclick = () => toggleTextEncoder(name);
    chip.className = `px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-all ${
      isSelected 
        ? "bg-purple-600 text-white shadow-sm" 
        : "app-input border app-border text-slate-400 hover:text-white"
    }`;
    chip.innerHTML = `${isSelected ? "✓ " : ""}${escapeHtml(name)}`;
    container.appendChild(chip);
  });
}

function toggleTextEncoder(name) {
  if (state.selectedTextEncoders.includes(name)) {
    state.selectedTextEncoders = state.selectedTextEncoders.filter(n => n !== name);
  } else {
    state.selectedTextEncoders.push(name);
  }
  renderTextEncodersSelector();
}

function addSelectedLora(name) {
  if (!name) return;
  if (!state.selectedLoras.some(l => l.name === name)) {
    state.selectedLoras.push({ name: name, weight: 1.0 });
    renderSelectedLoras();
  }
}

function removeSelectedLora(idx) {
  state.selectedLoras.splice(idx, 1);
  renderSelectedLoras();
}

function updateLoraWeight(idx, weight) {
  if (state.selectedLoras[idx]) {
    state.selectedLoras[idx].weight = parseFloat(weight);
    document.querySelectorAll(`.lora-weight-val-${idx}`).forEach(el => {
      el.textContent = weight;
    });
  }
}

function renderSelectedLoras() {
  ["sd-selected-loras-list", "setting-sd-selected-loras-list"].forEach(containerId => {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = "";

    state.selectedLoras.forEach((l, idx) => {
      const chip = document.createElement("div");
      chip.className = "flex items-center gap-2 p-1.5 rounded-lg border app-border app-input text-xs";
      chip.innerHTML = `
        <span class="font-mono text-purple-400 truncate flex-1">${escapeHtml(l.name)}</span>
        <div class="flex items-center gap-1.5 shrink-0">
          <input type="range" min="-2.0" max="2.0" step="0.1" value="${l.weight}" oninput="updateLoraWeight(${idx}, this.value)" class="w-16 accent-purple-500 h-1.5 cursor-pointer" />
          <span class="lora-weight-val-${idx} font-mono text-[10px] w-6">${l.weight}</span>
          <button onclick="removeSelectedLora(${idx})" class="hover:text-red-400 p-0.5"><i data-lucide="x" class="w-3 h-3"></i></button>
        </div>
      `;
      container.appendChild(chip);
    });
  });
  lucide.createIcons();
}

async function generateImagineImage() {
  const promptInput = document.getElementById("sd-prompt-input");
  const negPromptInput = document.getElementById("sd-neg-prompt-input");
  const btn = document.getElementById("sd-generate-btn");
  const statusEl = document.getElementById("sd-generate-status");

  const prompt = promptInput ? promptInput.value.trim() : "";
  if (!prompt) {
    alert("Please enter a prompt to generate an image.");
    return;
  }

  if (btn) btn.disabled = true;
  if (statusEl) statusEl.textContent = "Generating image via Stable Diffusion Forge...";

  try {
    const res = await fetch("/api/imagine/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: prompt,
        negative_prompt: negPromptInput ? negPromptInput.value : "",
        checkpoint: getInputValue("sd-checkpoint-select") || null,
        vae: getInputValue("sd-vae-select") || "Automatic",
        clip_skip: parseInt(getInputValue("sd-clipskip-input")) || 1,
        text_encoders: state.selectedTextEncoders,
        loras: state.selectedLoras,
        sampler_name: getInputValue("sd-sampler-select") || "Euler a",
        scheduler: getInputValue("sd-scheduler-select") || "Simple",
        steps: parseInt(getInputValue("sd-steps-input")) || 25,
        cfg_scale: parseFloat(getInputValue("sd-cfg-input")) || 7.0,
        shift: parseFloat(getInputValue("sd-shift-input")) || 1.0,
        width: parseInt(getInputValue("sd-width-input")) || 1024,
        height: parseInt(getInputValue("sd-height-input")) || 1024
      })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Image generation failed");
    }

    if (statusEl) statusEl.textContent = "Generation complete!";
    await loadImagineGallery();
  } catch (err) {
    alert("Forge Generation Error: " + err.message);
    if (statusEl) statusEl.textContent = `Error: ${err.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadImagineGallery() {
  try {
    const res = await fetch("/api/imagine/gallery");
    const items = await res.json();
    const container = document.getElementById("imagine-gallery-grid");
    if (!container) return;
    container.innerHTML = "";

    if (items.length === 0) {
      container.innerHTML = `<div class="col-span-full py-12 text-center app-text-muted text-sm">No generated images yet. Try creating one!</div>`;
      return;
    }

    items.forEach(img => {
      const card = document.createElement("div");
      card.className = "group relative rounded-xl overflow-hidden border app-border bg-slate-900";
      card.innerHTML = `
        <img src="${img.image_url}" class="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-300" />
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity p-3 flex flex-col justify-between">
          <button onclick="deleteGeneratedImage('${img.id}', event)" class="self-end p-1.5 bg-red-600/80 hover:bg-red-600 text-white rounded-lg">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
          <div>
            <p class="text-xs text-slate-200 line-clamp-2 mb-2 font-medium">${escapeHtml(img.prompt)}</p>
            <div class="flex gap-2">
              <a href="${img.image_url}" download="${img.image_filename}" class="flex-1 py-1 btn-accent text-white text-[11px] rounded flex items-center justify-center gap-1">
                <i data-lucide="download" class="w-3 h-3"></i> Download
              </a>
              <button onclick="sendImageToChat('${img.image_url}')" class="flex-1 py-1 bg-purple-600 hover:bg-purple-700 text-white text-[11px] rounded flex items-center justify-center gap-1">
                <i data-lucide="send" class="w-3 h-3"></i> To Chat
              </button>
            </div>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
    lucide.createIcons();
  } catch (err) {
    console.error("Load gallery error:", err);
  }
}

async function deleteGeneratedImage(imgId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Delete this generated image?")) return;
  await fetch(`/api/imagine/image/${imgId}`, { method: "DELETE" });
  loadImagineGallery();
}

function sendImageToChat(imageUrl) {
  fetch(imageUrl)
    .then(r => r.blob())
    .then(blob => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const b64 = reader.result.split(",")[1];
        state.attachedImages.push(b64);
        renderAttachedThumbnails();
        switchTab("chat");
      };
      reader.readAsDataURL(blob);
    });
}

// --- Artifacts Section ---
async function loadArtifacts() {
  try {
    const res = await fetch("/api/artifacts/list");
    state.artifacts = await res.json();
    renderArtifactsList();
  } catch (err) {
    console.error("Load artifacts error:", err);
  }
}

function renderArtifactsList() {
  const container = document.getElementById("artifacts-list-container");
  if (!container) return;
  container.innerHTML = "";

  if (state.artifacts.length === 0) {
    container.innerHTML = `
      <div class="p-8 text-center app-text-muted text-sm border app-border rounded-2xl">
        <i data-lucide="folder-code" class="w-10 h-10 mx-auto mb-2 text-purple-400/50"></i>
        No saved artifacts yet. Click 'Save' on any code block in your chat to persist it in your artifacts folder!
      </div>`;
    lucide.createIcons();
    return;
  }

  state.artifacts.forEach(art => {
    const item = document.createElement("div");
    item.className = "p-4 rounded-xl border app-card hover:border-[var(--accent)] transition-all flex flex-col md:flex-row md:items-center justify-between gap-3";
    item.innerHTML = `
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-purple-600/15 text-purple-400 flex items-center justify-center font-mono text-xs font-bold uppercase shrink-0">
          ${art.language.slice(0, 3)}
        </div>
        <div class="truncate">
          <h4 class="font-medium text-sm truncate">${escapeHtml(art.title)}</h4>
          <span class="text-xs app-text-muted">v${art.version} • ${new Date(art.updated_at).toLocaleDateString()}</span>
          ${art.file_path ? `<div class="text-[11px] font-mono text-purple-400/80 truncate max-w-md">${escapeHtml(art.file_path)}</div>` : ""}
        </div>
      </div>
      <div class="flex items-center gap-2 self-end md:self-auto">
        <button onclick="previewArtifactDetails('${art.id}')" class="px-3.5 py-1.5 app-input hover:bg-slate-700/50 text-xs rounded-lg flex items-center gap-1.5 font-medium">
          <i data-lucide="play" class="w-3.5 h-3.5 text-emerald-400"></i> Run App / View
        </button>
        ${art.file_path ? `
          <button onclick="revealArtifactInExplorer('${art.id}')" class="p-1.5 bg-purple-600/15 hover:bg-purple-600 text-purple-400 hover:text-white rounded-lg" title="Open Folder in PC Explorer">
            <i data-lucide="folder" class="w-4 h-4"></i>
          </button>
        ` : ""}
        <a href="/api/artifacts/${art.id}/download" class="p-1.5 bg-blue-600/15 hover:bg-blue-600 text-blue-400 hover:text-white rounded-lg" title="Download">
          <i data-lucide="download" class="w-4 h-4"></i>
        </a>
        <button onclick="deleteArtifact('${art.id}')" class="p-1.5 bg-red-600/15 hover:bg-red-600 text-red-400 hover:text-white rounded-lg" title="Delete">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      </div>
    `;
    container.appendChild(item);
  });
  lucide.createIcons();
}

async function revealArtifactInExplorer(artifactId) {
  try {
    const res = await fetch(`/api/artifacts/${artifactId}/reveal`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) alert("Could not open folder: " + data.detail);
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function previewArtifactDetails(artifactId) {
  try {
    const res = await fetch(`/api/artifacts/${artifactId}`);
    const art = await res.json();
    runCodeSnippet(art.language, art.code);
  } catch (err) {
    alert("Error loading artifact: " + err.message);
  }
}

async function deleteArtifact(artifactId) {
  if (!confirm("Delete this artifact from database and disk?")) return;
  await fetch(`/api/artifacts/${artifactId}`, { method: "DELETE" });
  loadArtifacts();
}

// --- Settings Section & Zim Catalog ---
async function loadSettings() {
  try {
    const res = await fetch("/api/settings/");
    state.settings = await res.json();

    setInputValue("setting-ollama-url", state.settings.ollama_base_url);
    setInputValue("setting-default-model-select", state.settings.default_model);
    setInputValue("setting-embed-model", state.settings.default_embedding_model);
    setInputValue("setting-system-prompt", state.settings.system_prompt);
    setInputValue("setting-user-name", state.settings.user_name);
    setInputValue("setting-user-occ", state.settings.user_occupation);
    setInputValue("setting-user-custom", state.settings.user_custom_instructions);

    setCheckboxValue("ext-toggle-autoroute", state.settings.ext_auto_route);
    setCheckboxValue("ext-toggle-meteo", state.settings.ext_open_meteo_enabled);
    setCheckboxValue("ext-toggle-wiki", state.settings.ext_wikipedia_enabled);
    setCheckboxValue("ext-toggle-searxng", state.settings.ext_searxng_enabled);
    setInputValue("setting-searxng-url", state.settings.ext_searxng_url);
    setCheckboxValue("ext-toggle-ddgs", state.settings.ext_ddgs_enabled);
    setCheckboxValue("ext-toggle-openlibrary", state.settings.ext_open_library_enabled);
    setCheckboxValue("ext-toggle-zim", state.settings.ext_zim_enabled);
    setInputValue("setting-zim-url", state.settings.ext_zim_api_url);

    setInputValue("setting-forge-url", state.settings.sd_forge_url);
  } catch (err) {
    console.error("Load settings error:", err);
  }
}

async function saveAllSettings() {
  const payload = {
    settings: {
      ollama_base_url: getInputValue("setting-ollama-url"),
      default_model: getInputValue("setting-default-model-select"),
      default_embedding_model: getInputValue("setting-embed-model"),
      system_prompt: getInputValue("setting-system-prompt"),
      user_name: getInputValue("setting-user-name"),
      user_occupation: getInputValue("setting-user-occ"),
      user_custom_instructions: getInputValue("setting-user-custom"),
      ext_auto_route: getCheckboxValue("ext-toggle-autoroute"),
      ext_open_meteo_enabled: getCheckboxValue("ext-toggle-meteo"),
      ext_wikipedia_enabled: getCheckboxValue("ext-toggle-wiki"),
      ext_searxng_enabled: getCheckboxValue("ext-toggle-searxng"),
      ext_searxng_url: getInputValue("setting-searxng-url"),
      ext_ddgs_enabled: getCheckboxValue("ext-toggle-ddgs"),
      ext_open_library_enabled: getCheckboxValue("ext-toggle-openlibrary"),
      ext_zim_enabled: getCheckboxValue("ext-toggle-zim"),
      ext_zim_api_url: getInputValue("setting-zim-url"),
      active_zim_filename: getInputValue("setting-active-zim-select"),
      sd_forge_url: getInputValue("setting-forge-url"),
      sd_text_encoders: state.selectedTextEncoders,
      sd_loras: state.selectedLoras
    }
  };

  try {
    const res = await fetch("/api/settings/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert("Settings saved successfully!");
      await loadModels();
    }
  } catch (err) {
    alert("Error saving settings: " + err.message);
  }
}

async function testOllamaConnection() {
  const url = getInputValue("setting-ollama-url");
  try {
    const res = await fetch("/api/settings/test-ollama", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    if (data.connected) {
      alert(`Success! Connected to Ollama at ${url}.\nFound ${data.models.length} model(s).`);
      loadModels();
    } else {
      alert(`Connection failed: ${data.error}`);
    }
  } catch (err) {
    alert("Test connection error: " + err.message);
  }
}

async function testExtension(toolName) {
  const query = prompt(`Enter test query for ${toolName}:`, toolName === "open_meteo" ? "Tokyo" : "Artificial Intelligence");
  if (!query) return;

  try {
    const res = await fetch("/api/extensions/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool_name: toolName, query: query })
    });
    const data = await res.json();
    alert(`[${toolName.toUpperCase()} Test Result]:\n\n` + JSON.stringify(data, null, 2));
  } catch (err) {
    alert(`Test error: ${err.message}`);
  }
}

// --- ZIM Catalog, Active Package & Download Manager ---
async function loadZimCatalog() {
  try {
    const res = await fetch("/api/extensions/zim/catalog");
    state.zimCatalog = await res.json();
    
    // Also fetch installed zims
    const instRes = await fetch("/api/extensions/zim/installed");
    state.installedZims = await instRes.json();

    // Populate Active ZIM package dropdown
    const activeZimSelect = document.getElementById("setting-active-zim-select");
    const activeZimNotice = document.getElementById("active-zim-status-notice");

    if (activeZimSelect) {
      activeZimSelect.innerHTML = `<option value="">Auto-Detect Installed Archive</option>`;
      state.installedZims.forEach(z => {
        activeZimSelect.innerHTML += `<option value="${z.filename}">${escapeHtml(z.title)} (${z.size_str})</option>`;
      });
      if (state.settings.active_zim_filename) {
        activeZimSelect.value = state.settings.active_zim_filename;
      }
    }

    if (activeZimNotice) {
      if (state.installedZims.length > 0) {
        activeZimNotice.className = "p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between";
        activeZimNotice.innerHTML = `
          <div class="flex items-center gap-2">
            <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
            <span>Active Offline Package: <strong>${escapeHtml(state.installedZims[0].title)}</strong> (${state.installedZims[0].size_str})</span>
          </div>
          <button onclick="testOfflineZimQuery()" class="px-2.5 py-1 bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-200 rounded text-[11px] font-medium">
            Test Query
          </button>
        `;
      } else {
        activeZimNotice.className = "p-3 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2";
        activeZimNotice.innerHTML = `
          <i data-lucide="alert-circle" class="w-4 h-4 text-amber-400 shrink-0"></i>
          <span>No offline ZIM packages downloaded yet. Click <strong>Download</strong> below on <strong>Wikipedia Simple English (505 MB)</strong> to enable offline Wikipedia!</span>
        `;
      }
    }

    renderZimCatalogTable();
  } catch (err) {
    console.error("Load Zim catalog error:", err);
  }
}

async function testOfflineZimQuery() {
  const query = prompt("Enter search query to test offline ZIM archive:", "Albert Einstein");
  if (!query) return;

  try {
    const res = await fetch("/api/extensions/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool_name: "zim", query: query })
    });
    const data = await res.json();
    alert(`[Offline ZIM Search Result]:\n\nTitle: ${data.title || "None"}\nSource: ${data.source || "N/A"}\nSnippet: ${data.snippet ? data.snippet.slice(0, 300) + '...' : data.error}`);
  } catch (err) {
    alert("Test error: " + err.message);
  }
}

function renderZimCatalogTable() {
  const tbody = document.getElementById("zim-catalog-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  state.zimCatalog.forEach(item => {
    const tr = document.createElement("tr");
    tr.className = "border-b app-border hover:bg-[var(--hover-bg)] text-xs";

    let sizeBadgeClass = "bg-emerald-950/60 text-emerald-400 border-emerald-500/30";
    if (item.is_huge) {
      sizeBadgeClass = "bg-red-950/60 text-red-400 border-red-500/30 font-bold";
    } else if (item.size_bytes > 2000000000) {
      sizeBadgeClass = "bg-amber-950/60 text-amber-400 border-amber-500/30";
    }

    let actionHtml = "";
    if (item.is_installed) {
      actionHtml = `
        <div class="flex items-center gap-2">
          <span class="text-emerald-400 font-medium flex items-center gap-1"><i data-lucide="check-circle" class="w-3.5 h-3.5"></i> Installed</span>
          <button onclick="deleteZimFile('${item.filename}')" class="p-1 hover:text-red-400 app-text-muted" title="Delete offline file">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      `;
    } else if (item.download_status && item.download_status.status === "downloading") {
      actionHtml = `
        <div class="flex items-center gap-2">
          <span class="text-blue-400 font-mono text-[11px]">${item.download_status.percent}% (${item.download_status.speed_mb}MB/s)</span>
          <button onclick="cancelZimDownload('${item.id}')" class="px-2 py-0.5 bg-red-600 hover:bg-red-700 text-white rounded text-[10px]">Cancel</button>
        </div>
      `;
    } else if (item.download_status && item.download_status.status === "error") {
      actionHtml = `
        <div class="flex items-center gap-2">
          <span class="text-red-400 text-[10px]" title="${escapeHtml(item.download_status.error)}">Failed</span>
          <button onclick="startZimDownload('${item.id}')" class="px-2 py-0.5 btn-accent text-white rounded text-[10px]">Retry</button>
        </div>
      `;
    } else {
      actionHtml = `
        <button onclick="startZimDownload('${item.id}')" class="px-3 py-1 btn-accent text-white rounded flex items-center gap-1.5 font-medium">
          <i data-lucide="download" class="w-3 h-3"></i> Download
        </button>
      `;
    }

    tr.innerHTML = `
      <td class="py-3 px-3">
        <div class="font-medium">${escapeHtml(item.name)}</div>
        <div class="text-[11px] app-text-muted">${escapeHtml(item.description)}</div>
      </td>
      <td class="py-3 px-3">
        <span class="px-2 py-0.5 rounded-full border text-[11px] font-mono ${sizeBadgeClass}">
          ${item.size_str} ${item.is_huge ? "⚠️ Very Large" : ""}
        </span>
      </td>
      <td class="py-3 px-3 app-text-muted">${item.category}</td>
      <td class="py-3 px-3 text-right">${actionHtml}</td>
    `;
    tbody.appendChild(tr);
  });
  lucide.createIcons();
}

async function startZimDownload(itemId) {
  const item = state.zimCatalog.find(c => c.id === itemId);
  if (item && item.is_huge) {
    const confirmHuge = confirm(`WARNING: This file is ${item.size_str}! It will consume massive bandwidth and drive space. Do you still wish to proceed?`);
    if (!confirmHuge) return;
  }

  try {
    const res = await fetch(`/api/extensions/zim/download/${itemId}`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      alert(data.message);
      startZimPolling();
    } else {
      alert("Download error: " + data.detail);
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function cancelZimDownload(itemId) {
  await fetch(`/api/extensions/zim/cancel/${itemId}`, { method: "POST" });
  loadZimCatalog();
}

async function deleteZimFile(filename) {
  if (!confirm(`Delete ${filename}?`)) return;
  await fetch(`/api/extensions/zim/file/${filename}`, { method: "DELETE" });
  loadZimCatalog();
}

let zimPollInterval = null;
function startZimPolling() {
  if (zimPollInterval) clearInterval(zimPollInterval);
  zimPollInterval = setInterval(async () => {
    await loadZimCatalog();
    const isAnyDownloading = state.zimCatalog.some(c => c.download_status && c.download_status.status === "downloading");
    if (!isAnyDownloading) {
      clearInterval(zimPollInterval);
      zimPollInterval = null;
    }
  }, 1500);
}

async function clearChatHistory() {
  if (!confirm("Are you sure you want to permanently clear ALL chat history?")) return;
  await fetch("/api/settings/clear-history", { method: "POST" });
  state.chats = [];
  createNewChat();
  renderChatHistory();
}

async function exportChats() {
  window.location.href = "/api/settings/export-chats";
}

// --- Event Listeners & Helpers ---
function setupEventListeners() {
  const textarea = document.getElementById("chat-input-textarea");
  if (textarea) {
    textarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    textarea.addEventListener("input", () => {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(textarea.scrollHeight, 180) + "px";
    });
  }

  const fileInput = document.getElementById("chat-file-upload-input");
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) handleFileUpload(file);
      fileInput.value = "";
    });
  }

  ["sd-lora-picker-select", "setting-sd-lora-picker-select"].forEach(id => {
    const loraPicker = document.getElementById(id);
    if (loraPicker) {
      loraPicker.addEventListener("change", (e) => {
        const val = e.target.value;
        if (val) {
          addSelectedLora(val);
          loraPicker.value = "";
        }
      });
    }
  });

  const presetSelect = document.getElementById("sd-preset-select");
  if (presetSelect) {
    presetSelect.addEventListener("change", (e) => {
      if (e.target.value) {
        applySdPreset(e.target.value);
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setInputValue(id, val) {
  const el = document.getElementById(id);
  if (el && val !== undefined && val !== null) el.value = val;
}
function getInputValue(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}
function setCheckboxValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = Boolean(val);
}
function getCheckboxValue(id) {
  const el = document.getElementById(id);
  return el ? el.checked : false;
}
