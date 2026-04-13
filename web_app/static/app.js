const STORAGE_KEY = "gdelt-chat-sessions";
const ACTIVE_SESSION_KEY = "gdelt-active-session";
const DEFAULT_CHAT_TITLE = "New Chat";
const LEGACY_DEFAULT_TITLES = new Set(["\u65b0\u5bf9\u8bdd", DEFAULT_CHAT_TITLE]);

const state = {
    sessions: [],
    activeSessionId: null,
    serverInfo: null,
    requestInFlight: false,
    abortController: null,
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
    thinkingBanner: document.getElementById("thinkingBanner"),
    thinkingBannerText: document.getElementById("thinkingBannerText"),
    thinkingBannerTime: document.getElementById("thinkingBannerTime"),
    messageTemplate: document.getElementById("messageTemplate"),
    typingTemplate: document.getElementById("typingTemplate"),
    thinkingTemplate: document.getElementById("thinkingTemplate"),
    promptCards: document.querySelectorAll(".prompt-card"),
};

function bootstrap() {
    console.log("[GDELT Chat UI] Version 2.0 loaded");
    loadSessions();
    bindEvents();
    selectOrCreateSession();
    render();
    fetchHealth();
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
        if (!session) {
            return;
        }

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
        id: crypto.randomUUID(),
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
    if (existing) {
        return existing;
    }

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
    if (!session) {
        return;
    }

    const title = session.title || DEFAULT_CHAT_TITLE;
    if (!window.confirm(`Delete "${title}"?`)) {
        return;
    }

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
    if (!session) {
        return;
    }

    elements.conversationTitle.textContent = session.title || DEFAULT_CHAT_TITLE;
    elements.messageList.innerHTML = "";

    const hasMessages = session.messages.length > 0;
    elements.emptyState.hidden = hasMessages;
    elements.messageList.hidden = !hasMessages;

    if (!hasMessages) {
        return;
    }

    session.messages.forEach((message) => {
        try {
            elements.messageList.appendChild(buildMessageNode(message));
        } catch (err) {
            console.error("Failed to render message:", message, err);
            const errorNode = document.createElement("div");
            errorNode.className = "message message--assistant";
            errorNode.textContent = "[Error rendering message]";
            elements.messageList.appendChild(errorNode);
        }
    });

    scrollMessagesToBottom();
}

function buildMessageNode(message) {
    const fragment = elements.messageTemplate.content.cloneNode(true);
    const article = fragment.querySelector(".message");
    const avatar = fragment.querySelector(".message__avatar");
    const role = fragment.querySelector(".message__role");
    const time = fragment.querySelector(".message__time");
    const content = fragment.querySelector(".message__content");

    article.classList.add(message.role === "user" ? "message--user" : "message--assistant");
    avatar.textContent = message.role === "user" ? "You" : "AI";
    role.textContent = message.role === "user" ? "You" : "Assistant";
    time.textContent = formatTime(message.createdAt);
    content.textContent = message.content || "(No response content)";

    if (message.thinking_process && message.thinking_process.length > 0) {
        const isEmptyContent = !message.content || !message.content.trim();
        const thinkingNode = buildThinkingNode(message.thinking_process, isEmptyContent);
        article.querySelector(".message__body").appendChild(thinkingNode);
    }

    return article;
}

function buildThinkingNode(steps, openByDefault = false) {
    try {
        const fragment = elements.thinkingTemplate.content.cloneNode(true);
        const details = fragment.querySelector(".thinking-process");
        const container = fragment.querySelector(".thinking-process__content");
        if (openByDefault) {
            details.setAttribute("open", "");
        }

        steps.forEach((step) => {
            try {
                const row = document.createElement("div");
                row.className = "thinking-step";

                const badge = document.createElement("span");
                badge.className = "thinking-step__badge";
                badge.textContent = step.type || "unknown";

                const text = document.createElement("span");
                text.className = "thinking-step__text";

                switch (step.type) {
                    case "router_decision":
                        text.textContent = `Router: ${step.intent || "?"} (confidence: ${((step.confidence != null ? step.confidence : 0)).toFixed(2)})` +
                            (step.suggested_tools?.length ? ` → suggested: ${step.suggested_tools.join(", ")}` : "");
                        break;
                    case "system_hint":
                        text.textContent = `System hint: suggested tools = ${(step.suggested_tools || []).join(", ")}`;
                        break;
                    case "history_truncated":
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

        return details;
    } catch (err) {
        console.error("Failed to build thinking node:", err);
        const fallback = document.createElement("details");
        fallback.className = "thinking-process";
        fallback.innerHTML = '<summary class="thinking-process__summary">Thinking Process (error)</summary>';
        return fallback;
    }
}

function buildTypingNode() {
    return elements.typingTemplate.content.cloneNode(true);
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

function updateThinkingStatus(startTime) {
    const elapsedMs = Date.now() - startTime;
    const elapsedSec = Math.floor(elapsedMs / 1000);

    let status = "Thinking...";
    if (elapsedSec < 5) {
        status = "Analyzing your question...";
    } else if (elapsedSec < 15) {
        status = "Router identified intent, preparing tools...";
    } else if (elapsedSec < 30) {
        status = "Querying the database...";
    } else if (elapsedSec < 60) {
        status = "Processing large dataset (this may take a minute)...";
    } else {
        status = "Almost there, finalizing response...";
    }

    elements.thinkingBannerText.textContent = status;
    elements.thinkingBannerTime.textContent = `${elapsedSec}s`;
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
    if (state.requestInFlight) {
        return;
    }

    const prompt = elements.composerInput.value.trim();
    if (!prompt) {
        return;
    }

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
    elements.thinkingBanner.hidden = false;
    elements.messageList.appendChild(buildTypingNode());
    scrollMessagesToBottom();

    const requestStartTime = Date.now();
    const thinkingInterval = setInterval(() => {
        updateThinkingStatus(requestStartTime);
    }, 1000);
    updateThinkingStatus(requestStartTime);

    try {
        console.log("[UI] Sending chat request...");
        const response = await fetchWithTimeout("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: prompt,
                history,
            }),
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
    } finally {
        clearInterval(thinkingInterval);
        state.requestInFlight = false;
        state.abortController = null;
        elements.sendButton.textContent = "Send";
        elements.sendButton.classList.remove("is-stopping");
        elements.thinkingBanner.hidden = true;
        render();
        focusComposer();
    }
}

function createMessage(role, content, thinking_process = null) {
    return {
        id: crypto.randomUUID(),
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
            id: crypto.randomUUID(),
            title: DEFAULT_CHAT_TITLE,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            messages: [],
        };
    }

    return {
        ...session,
        title: session.title === "\u65b0\u5bf9\u8bdd" ? DEFAULT_CHAT_TITLE : (session.title || DEFAULT_CHAT_TITLE),
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

bootstrap();
