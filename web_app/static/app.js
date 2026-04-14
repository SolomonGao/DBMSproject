/**
 * app.js - GDELT Chat UI
 * 
 * 修复点：
 * 1. UUID 兼容性问题 - 添加 generateUUID() polyfill
 * 2. buildMessageNode null 问题 - 添加防御性检查
 * 3. mapIntegration 加载问题 - 改进初始化
 */

// ==================== UUID 生成函数（兼容所有浏览器）====================

function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    
    if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = crypto.getRandomValues(new Uint8Array(1))[0] % 16;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
    
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// ==================== 全局状态 ====================

const STORAGE_KEY = "gdelt-chat-sessions";
const ACTIVE_SESSION_KEY = "gdelt-active-session";
const DEFAULT_CHAT_TITLE = "New Chat";
const LEGACY_DEFAULT_TITLES = new Set(["新对话", DEFAULT_CHAT_TITLE]);

const state = {
    sessions: [],
    activeSessionId: null,
    serverInfo: null,
    requestInFlight: false,
    abortController: null,
    mapVisible: false,
    eventExtractor: null,
};

const elements = {
    sessionList: document.getElementById("sessionList"),
    newChatButton: document.getElementById("newChatButton"),
    clearAllButton: document.getElementById("clearAllButton"),
    resetConversationButton: document.getElementById("resetConversationButton"),
    conversationTitle: document.getElementById("conversationTitle"),
    modelBadge: document.getElementById("modelBadge"),
    statusLine: document.getElementById("statusLine"),
    emptyState: document.getElementById("emptyState"),
    messageList: document.getElementById("messageList"),
    composerInput: document.getElementById("composerInput"),
    sendButton: document.getElementById("sendButton"),
    errorBanner: document.getElementById("errorBanner"),
    messageTemplate: document.getElementById("messageTemplate"),
    typingTemplate: document.getElementById("typingTemplate"),
    thinkingTemplate: document.getElementById("thinkingTemplate"),
    promptCards: document.querySelectorAll(".prompt-card"),
    mapContainer: document.getElementById("mapContainer"),
    toggleMapButton: null,
};

// ==================== 初始化 ====================

function bootstrap() {
    console.log("[GDELT Chat UI] Version 2.0 loaded");
    
    // Check mapIntegration
    if (typeof EventExtractor !== 'undefined') {
        state.eventExtractor = new EventExtractor();
        console.log("[✓] EventExtractor initialized");
    } else {
        console.warn("[⚠] EventExtractor not available - map features will be disabled");
    }
    
    loadSessions();
    bindEvents();
    setupMapToggle();
    selectOrCreateSession();
    render();
    fetchHealth();
}

function setupMapToggle() {
    if (!elements.toggleMapButton) {
        const header = document.querySelector('.chat-header') || document.querySelector('.workspace__header');
        if (header) {
            elements.toggleMapButton = document.createElement('button');
            elements.toggleMapButton.id = 'toggleMapButton';
            elements.toggleMapButton.type = 'button';
            elements.toggleMapButton.className = 'toggle-map-button';
            elements.toggleMapButton.textContent = '📍 Show Map';
            elements.toggleMapButton.title = 'Toggle map visualization';
            elements.toggleMapButton.addEventListener('click', toggleMapVisibility);
            
            const statusLine = document.getElementById('statusLine');
            if (statusLine) {
                statusLine.parentNode.insertBefore(elements.toggleMapButton, statusLine.nextSibling);
            }
        }
    }
    
    if (!elements.mapContainer) {
        const mapDiv = document.createElement('div');
        mapDiv.id = 'mapContainer';
        mapDiv.className = 'map-container';
        mapDiv.style.display = 'none';
        mapDiv.style.height = '400px';
        mapDiv.style.width = '100%';
        mapDiv.style.borderRadius = '8px';
        mapDiv.style.marginTop = '16px';
        mapDiv.style.border = '1px solid #ddd';
        
        const messageList = document.getElementById('messageList');
        if (messageList && messageList.parentNode) {
            messageList.parentNode.insertBefore(mapDiv, messageList.nextSibling);
            elements.mapContainer = mapDiv;
        }
    }
}

function toggleMapVisibility() {
    if (!elements.mapContainer) return;
    
    state.mapVisible = !state.mapVisible;
    
    if (state.mapVisible) {
        elements.mapContainer.style.display = 'block';
        if (elements.toggleMapButton) elements.toggleMapButton.textContent = '📍 Hide Map';
        
        if (state.eventExtractor && !state.eventExtractor.initialized) {
            state.eventExtractor.init();
        }
        
        if (state.eventExtractor && state.eventExtractor.mapInstance) {
            state.eventExtractor.mapInstance.invalidateSize();
        }
    } else {
        elements.mapContainer.style.display = 'none';
        if (elements.toggleMapButton) elements.toggleMapButton.textContent = '📍 Show Map';
    }
}

function bindEvents() {
    elements.newChatButton.addEventListener("click", () => {
        createSession();
        render();
        focusComposer();
    });

    elements.clearAllButton.addEventListener("click", () => {
        state.sessions = [];
        state.activeSessionId = null;
        persistSessions();
        createSession();
        render();
    });

    elements.resetConversationButton.addEventListener("click", () => {
        const session = getActiveSession();
        if (!session) return;
        session.messages = [];
        session.updatedAt = new Date().toISOString();
        session.title = DEFAULT_CHAT_TITLE;
        persistSessions();
        render();
        focusComposer();
    });

    elements.sendButton.addEventListener("click", () => {
        if (state.requestInFlight && state.abortController) {
            state.abortController.abort();
            return;
        }
        sendCurrentPrompt();
    });

    elements.composerInput.addEventListener("input", autoResizeComposer);
    elements.composerInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendCurrentPrompt();
        }
    });

    elements.promptCards.forEach((button) => {
        button.addEventListener("click", () => {
            elements.composerInput.value = button.dataset.prompt || "";
            autoResizeComposer();
            focusComposer();
        });
    });
}

function loadSessions() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : [];
        state.sessions = Array.isArray(parsed) ? parsed.map(normalizeSession) : [];
        state.activeSessionId = localStorage.getItem(ACTIVE_SESSION_KEY);
        persistSessions();
    } catch (error) {
        console.error("Failed to load sessions", error);
        state.sessions = [];
        state.activeSessionId = null;
    }
}

function persistSessions() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.sessions));
    if (state.activeSessionId) {
        localStorage.setItem(ACTIVE_SESSION_KEY, state.activeSessionId);
    } else {
        localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
}

function createSession() {
    const session = {
        id: generateUUID(),
        title: DEFAULT_CHAT_TITLE,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messages: [],
    };
    state.sessions.unshift(session);
    state.activeSessionId = session.id;
    persistSessions();
    return session;
}

function selectOrCreateSession() {
    const existing = getActiveSession();
    if (existing) return existing;

    if (state.sessions.length === 0) {
        return createSession();
    }

    const [latestSession] = getSortedSessions();
    state.activeSessionId = latestSession ? latestSession.id : null;
    persistSessions();
    return latestSession || createSession();
}

function getActiveSession() {
    return state.sessions.find((session) => session.id === state.activeSessionId) || null;
}

function setActiveSession(sessionId) {
    state.activeSessionId = sessionId;
    persistSessions();
    render();
}

function deleteSession(sessionId) {
    const session = state.sessions.find((item) => item.id === sessionId);
    if (!session) return;

    const title = session.title || DEFAULT_CHAT_TITLE;
    if (!window.confirm(`Delete "${title}"?`)) return;

    state.sessions = state.sessions.filter((item) => item.id !== sessionId);

    if (state.activeSessionId === sessionId) {
        const [nextSession] = getSortedSessions();
        state.activeSessionId = nextSession ? nextSession.id : null;
    }

    if (state.sessions.length === 0) {
        createSession();
    } else {
        persistSessions();
    }

    render();
}

function render() {
    renderSessionList();
    renderConversation();
}

function renderSessionList() {
    elements.sessionList.innerHTML = "";

    if (state.sessions.length === 0) {
        const empty = document.createElement("p");
        empty.className = "session-item__meta";
        empty.textContent = "No conversations yet.";
        elements.sessionList.appendChild(empty);
        return;
    }

    getSortedSessions().forEach((session) => {
        const row = document.createElement("div");
        row.className = "session-row";

        const sessionButton = document.createElement("button");
        sessionButton.type = "button";
        sessionButton.className = "session-item";
        if (session.id === state.activeSessionId) {
            sessionButton.classList.add("is-active");
        }

        const title = document.createElement("span");
        title.className = "session-item__title";
        title.textContent = session.title || DEFAULT_CHAT_TITLE;

        const meta = document.createElement("span");
        meta.className = "session-item__meta";
        meta.textContent = formatSessionMeta(session);

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "session-delete";
        deleteButton.textContent = "Delete";
        deleteButton.setAttribute("aria-label", `Delete ${title.textContent}`);
        deleteButton.addEventListener("click", () => deleteSession(session.id));

        sessionButton.appendChild(title);
        sessionButton.appendChild(meta);
        sessionButton.addEventListener("click", () => setActiveSession(session.id));

        row.appendChild(sessionButton);
        row.appendChild(deleteButton);
        elements.sessionList.appendChild(row);
    });
}

function renderConversation() {
    const session = getActiveSession();
    if (!session) return;

    elements.conversationTitle.textContent = session.title || DEFAULT_CHAT_TITLE;
    elements.messageList.innerHTML = "";

    if (session.messages.length === 0) {
        elements.emptyState.hidden = false;
        return;
    }

    elements.emptyState.hidden = true;

    session.messages.forEach((message, index) => {
        try {
            const node = buildMessageNode(message);
            elements.messageList.appendChild(node);
        } catch (error) {
            console.error(`Error rendering message ${index}:`, error);
            const fallback = document.createElement("div");
            fallback.className = `message message--${message.role}`;
            fallback.innerHTML = `<div class="message__body"><div class="message__meta"><span class="message__role">${message.role === "user" ? "You" : "Assistant"}</span><time class="message__time">${formatTime(message.createdAt)}</time></div><div class="message__content">${message.content}</div></div>`;
            elements.messageList.appendChild(fallback);
        }
    });

    scrollMessagesToBottom();
}

// ==================== 关键修复：buildMessageNode ====================

function buildMessageNode(message) {
    const template = elements.messageTemplate.content.cloneNode(true);

    const container = template.querySelector("article") || template.querySelector("div");
    if (!container) {
        console.error("Message template structure invalid");
        return template;
    }
    
    container.className = `message message--${message.role}`;

    // 尝试多种方式找到文本容器
    let textDiv = template.querySelector("[data-message-text]");
    if (!textDiv) textDiv = template.querySelector(".message__content");
    if (!textDiv) {
        const body = template.querySelector(".message__body");
        if (body) {
            textDiv = document.createElement("div");
            textDiv.className = "message__content";
            body.appendChild(textDiv);
        }
    }
    
    if (textDiv) {
        textDiv.innerHTML = message.content;
    }

    // 处理时间戳
    let timeDiv = template.querySelector("[data-message-time]");
    if (!timeDiv) timeDiv = template.querySelector(".message__time");
    if (timeDiv) timeDiv.textContent = formatTime(message.createdAt);

    // 处理role
    let roleSpan = template.querySelector("[data-message-role]");
    if (!roleSpan) roleSpan = template.querySelector(".message__role");
    if (roleSpan) roleSpan.textContent = message.role === "user" ? "You" : "Assistant";

    if (message.thinking_process && message.thinking_process.length > 0) {
        const thinkingNode = buildThinkingNode(message.thinking_process);
        container.appendChild(thinkingNode);
    }

    return template;
}

// ==================== 其他函数 ====================

function buildThinkingNode(thinkingProcess) {
    try {
        const details = document.createElement("details");
        details.className = "thinking-process";

        const summary = document.createElement("summary");
        summary.className = "thinking-process__summary";
        summary.textContent = `Thinking Process (${thinkingProcess.length} steps)`;
        details.appendChild(summary);

        const container = document.createElement("div");
        container.className = "thinking-process__steps";

        thinkingProcess.forEach((step) => {
            try {
                const row = document.createElement("div");
                row.className = "thinking-step";

                const badge = document.createElement("span");
                badge.className = "thinking-step__badge";
                badge.textContent = (step.type || "?").toUpperCase();

                const text = document.createElement("span");
                text.className = "thinking-step__text";

                switch (step.type) {
                    case "input_analysis":
                        text.textContent = `Input: ${step.input || ""}`;
                        break;
                    case "history_handling":
                        text.textContent = `History truncated to ${step.max_messages != null ? step.max_messages : "?"} messages`;
                        break;
                    case "llm_reasoning":
                        text.textContent = `LLM reasoning: ${step.reasoning || ""}`.slice(0, 180) + "...";
                        break;
                    case "tool_calls":
                        text.textContent = `AI requests tools: ${(step.tools || []).map(t => t.name || "?").join(", ")}`;
                        break;
                    case "tool_call_start":
                        text.textContent = `Calling tool: ${step.name || "?"}`;
                        break;
                    case "tool_result":
                        text.textContent = `Tool ${step.name || "?"} returned (${step.elapsed != null ? step.elapsed : "?"}s): ${step.result_preview || ""}`;
                        break;
                    case "router_error":
                        text.textContent = `Router error: ${step.error || ""}`;
                        break;
                    default:
                        text.textContent = JSON.stringify(step);
                }

                row.appendChild(badge);
                row.appendChild(text);
                container.appendChild(row);
            } catch (innerErr) {
                console.error("Failed to render thinking step:", step, innerErr);
            }
        });

        details.appendChild(container);
        return details;
    } catch (err) {
        console.error("Failed to build thinking node:", err);
        const fallback = document.createElement("details");
        fallback.className = "thinking-process";
        fallback.innerHTML = '<summary class="thinking-process__summary">Thinking Process (error)</summary>';
        return fallback;
    }
}

function formatSessionMeta(session) {
    const messageCount = session.messages.length;
    const timeLabel = new Intl.DateTimeFormat("en-US", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(session.updatedAt));

    return `${messageCount} messages - ${timeLabel}`;
}

function formatTime(value) {
    return new Intl.DateTimeFormat("en-US", {
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(value));
}

function autoResizeComposer() {
    elements.composerInput.style.height = "auto";
    elements.composerInput.style.height = `${Math.min(elements.composerInput.scrollHeight, 220)}px`;
}

function focusComposer() {
    elements.composerInput.focus();
}

async function fetchHealth() {
    try {
        const response = await fetch("/api/health");
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Health check failed.");
        }

        state.serverInfo = payload;
        elements.modelBadge.textContent = `${payload.provider} - ${payload.model}`;
        elements.statusLine.textContent = `Server is healthy, MCP transport: ${payload.transport}`;
    } catch (error) {
        console.error(error);
        elements.modelBadge.textContent = "Offline";
        elements.statusLine.textContent = "Health check failed. Please confirm that run_web.py is running.";
        showError("The service is unavailable. Start the web server first.");
    }
}

async function sendCurrentPrompt() {
    if (state.requestInFlight) return;

    const prompt = elements.composerInput.value.trim();
    if (!prompt) return;

    hideError();
    const session = getActiveSession() || createSession();
    const history = session.messages.map(({ role, content }) => ({ role, content }));

    const userMessage = createMessage("user", prompt);
    session.messages.push(userMessage);
    session.updatedAt = userMessage.createdAt;
    if (LEGACY_DEFAULT_TITLES.has(session.title)) {
        session.title = prompt.slice(0, 28);
    }

    persistSessions();
    render();

    elements.composerInput.value = "";
    autoResizeComposer();

    state.requestInFlight = true;
    state.abortController = new AbortController();
    elements.sendButton.textContent = "Stop";
    elements.sendButton.classList.add("is-stopping");
    elements.messageList.appendChild(buildTypingNode());
    scrollMessagesToBottom();

    try {
        console.log("[UI] Sending chat request...");
        const response = await fetchWithTimeout("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: prompt, history }),
            signal: state.abortController.signal,
        }, 120000);

        console.log("[UI] Response received, parsing JSON...");
        const payload = await response.json();
        console.log("[UI] Payload:", payload);
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Chat request failed.");
        }

        console.log("[UI] Appending assistant message...");
        session.messages.push(createMessage("assistant", payload.reply, payload.thinking_process));
        session.updatedAt = new Date().toISOString();
        state.sessions.sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
        persistSessions();
        console.log("[UI] Message saved.");

        // ==================== 地图集成 ====================
        if (state.eventExtractor && payload.reply) {
            try {
                console.log("[Map] Processing visualization...");
                if (!state.eventExtractor.initialized) {
                    state.eventExtractor.init();
                }
                
                state.eventExtractor.showEventsFromText(payload.reply);
                const events = state.eventExtractor.getEvents();
                console.log(`[Map] Found ${events.length} events`);
                
                if (events.length > 0 && elements.mapContainer) {
                    elements.mapContainer.style.display = 'block';
                    if (state.eventExtractor.mapInstance) {
                        setTimeout(() => {
                            state.eventExtractor.mapInstance.invalidateSize();
                        }, 100);
                    }
                }
            } catch (mapError) {
                console.error("[Map] Error:", mapError);
            }
        }
        // ==================== 地图集成结束 ====================

    } catch (error) {
        if (error.name === "AbortError") {
            console.log("[UI] Request aborted by user.");
            session.messages.push(createMessage("assistant", "[Stopped thinking]"));
            session.updatedAt = new Date().toISOString();
            state.sessions.sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
            persistSessions();
        } else {
            console.error(error);
            showError(error.message || "Failed to send the message.");
        }
        
        if (elements.mapContainer) {
            elements.mapContainer.style.display = 'none';
        }
        
    } finally {
        state.requestInFlight = false;
        state.abortController = null;
        elements.sendButton.textContent = "Send";
        elements.sendButton.classList.remove("is-stopping");
        render();
        focusComposer();
    }
}

function createMessage(role, content, thinking_process = null) {
    return {
        id: generateUUID(),
        role,
        content,
        createdAt: new Date().toISOString(),
        thinking_process: thinking_process || null,
    };
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 120000) {
    const internalController = new AbortController();
    const externalSignal = options.signal;

    const onExternalAbort = () => internalController.abort();
    if (externalSignal) {
        externalSignal.addEventListener("abort", onExternalAbort);
    }

    const id = setTimeout(() => internalController.abort(), timeoutMs);
    try {
        const response = await fetch(url, { ...options, signal: internalController.signal });
        return response;
    } finally {
        clearTimeout(id);
        if (externalSignal) {
            externalSignal.removeEventListener("abort", onExternalAbort);
        }
    }
}

function normalizeSession(session) {
    if (!session || typeof session !== "object") {
        return {
            id: generateUUID(),
            title: DEFAULT_CHAT_TITLE,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            messages: [],
        };
    }

    return {
        ...session,
        title: session.title === "新对话" ? DEFAULT_CHAT_TITLE : (session.title || DEFAULT_CHAT_TITLE),
        messages: Array.isArray(session.messages) ? session.messages : [],
        thinking_process: session.thinking_process || null,
    };
}

function getSortedSessions() {
    return state.sessions
        .slice()
        .sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
}

function showError(message) {
    elements.errorBanner.hidden = false;
    elements.errorBanner.textContent = message;
}

function hideError() {
    elements.errorBanner.hidden = true;
    elements.errorBanner.textContent = "";
}

function scrollMessagesToBottom() {
    requestAnimationFrame(() => {
        elements.messageList.scrollTop = elements.messageList.scrollHeight;
    });
}

function buildTypingNode() {
    return elements.typingTemplate.content.cloneNode(true);
}

// ==================== 启动应用 ====================

bootstrap();