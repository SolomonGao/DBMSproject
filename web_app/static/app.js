const STORAGE_KEY = "gdelt-chat-sessions";
const ACTIVE_SESSION_KEY = "gdelt-active-session";
const DEFAULT_CHAT_TITLE = "New Chat";
const LEGACY_DEFAULT_TITLES = new Set(["\u65b0\u5bf9\u8bdd", DEFAULT_CHAT_TITLE]);

const state = {
    sessions: [],
    activeSessionId: null,
    serverInfo: null,
    requestInFlight: false,
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
    promptCards: document.querySelectorAll(".prompt-card"),
};

function bootstrap() {
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

    elements.sendButton.addEventListener("click", () => sendCurrentPrompt());

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
        elements.messageList.appendChild(buildMessageNode(message));
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
    content.textContent = message.content;

    return article;
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
    elements.sendButton.disabled = true;
    elements.messageList.appendChild(buildTypingNode());
    scrollMessagesToBottom();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: prompt,
                history,
            }),
        });

        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Chat request failed.");
        }

        session.messages.push(createMessage("assistant", payload.reply));
        session.updatedAt = new Date().toISOString();
        state.sessions.sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
        persistSessions();
    } catch (error) {
        console.error(error);
        showError(error.message || "Failed to send the message.");
    } finally {
        state.requestInFlight = false;
        elements.sendButton.disabled = false;
        render();
        focusComposer();
    }
}

function createMessage(role, content) {
    return {
        id: crypto.randomUUID(),
        role,
        content,
        createdAt: new Date().toISOString(),
    };
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
