// main.js — структура WS-primary, HTTP fallback, построчная отправка логов на фронт.

let systemLogsModal = null;
let tentacleLogsModal = null;
let restartTentacleModal = null;
let currentTentacle = null;
let socket = null;
let wsConnected = false;
const FALLBACK_POLL_INTERVAL_MS = 60_000; // резервный пул — 60s

document.addEventListener("DOMContentLoaded", () => {
    systemLogsModal = new bootstrap.Modal(document.getElementById("systemLogsModal"));
    tentacleLogsModal = new bootstrap.Modal(document.getElementById("logsModal"));
    restartTentacleModal = new bootstrap.Modal(document.getElementById("restartModal"));

    registerButtonListeners();

    refreshData();
    initWebSocket();

    setInterval(() => {
        if (!wsConnected) {
            refreshData();
        }
    }, FALLBACK_POLL_INTERVAL_MS);
});

/* Init */
function registerButtonListeners() {
    const refreshTableBtn = document.getElementById("refreshButton");
    const refreshLogsBtn = document.getElementById("refreshLogsBtn");
    const restartTentacleBtnClean = document.getElementById("restartButtonModalClean");
    const restartTentacleBtn = document.getElementById("restartButtonModal");
    const systemLogsRefreshBtn = document.getElementById("systemLogsRefreshBtn");
    const systemLogsButton = document.getElementById("systemLogsButton");

    if (refreshTableBtn) refreshTableBtn.addEventListener("click", refreshTableButtonOnClick);
    if (refreshLogsBtn) refreshLogsBtn.addEventListener("click", refreshLogsButtonOnClick);
    if (restartTentacleBtnClean) restartTentacleBtnClean.addEventListener("click", () => restartTentacleButtonOnClick(currentTentacle, true));
    if (restartTentacleBtn) restartTentacleBtn.addEventListener("click", () => restartTentacleButtonOnClick(currentTentacle, false));
    if (systemLogsButton) systemLogsButton.addEventListener("click", systemLogsButtonOnClick);
    if (systemLogsRefreshBtn) systemLogsRefreshBtn.addEventListener("click", systemLogsRefreshButtonOnClick);
}

/* Buttons */
function refreshTableButtonOnClick() {
    refreshData();
    initWebSocket(true); // переподключение WS по кнопке
}

function refreshLogsButtonOnClick() {
    if (!currentTentacle) return;

    loadLogs(currentTentacle, 'build');
    loadLogs(currentTentacle, 'start');
}

function restartTentacleButtonOnClick(tentacleName, isClean = false) {
    if (!tentacleName) return

    apiRestartTentacle(tentacleName, isClean).then(r => console.log("Restart tentacle " + tentacleName + r.ok ? " OK" : " FAIL"));
    restartTentacleModal.hide();
}

function systemLogsButtonOnClick() {
    if (!systemLogsModal) return;

    reloadSystemLogs().then();
    systemLogsModal.show();
}

function systemLogsRefreshButtonOnClick() {
    reloadSystemLogs().then();
}

/* HTTP helpers */

async function apiGetSystemLogs() {
    const resp = await fetch("/api/tentacles/system-logs");
    if (!resp.ok) {
        showNotification(`HTTP Cannot fetch system logs: ${resp.status}`, "danger")
        throw new Error(`HTTP Cannot fetch system logs: ${resp.status}`);
    }
    return await resp.json();
}

async function apiGetTentacles() {
    const resp = await fetch("/api/tentacles");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    return json.tentacles || [];
}

async function apiGetLogs(tentacleName, logType) {
    const resp = await fetch(`/api/tentacles/${encodeURIComponent(tentacleName)}/logs/${encodeURIComponent(logType)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    return json.logs;
}

async function apiRestartTentacle(tentacleName, isClean) {
    const resp = await fetch(`/api/tentacles/${encodeURIComponent(tentacleName)}/restart/${isClean}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
}

/* UI — таблица тентаклей */

async function refreshData() {
    const btn = document.getElementById("refreshButton");
    const origDisabled = btn?.disabled ?? false;
    const origHTML = btn?.innerHTML ?? null;

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Refreshing...';
    }

    try {
        const tentacles = await apiGetTentacles();
        renderTentacleTable(tentacles);
    } catch (err) {
        console.error("refreshData error:", err);
        showNotification("Error refreshing tentacles: " + err.message, "danger");
    } finally {
        if (btn) {
            btn.disabled = origDisabled;
            btn.innerHTML = origHTML;
        }
    }
}

function renderTentacleTable(tentacles) {
    const tbody = document.getElementById("tentacles-tbody");
    tbody.innerHTML = "";

    for (const t of tentacles) {
        const tr = document.createElement("tr");
        tr.dataset.tentacle = t.name;

        tr.innerHTML = `
      <td class="tr-left">
        <a href="/tentacle/${encodeURIComponent(t.name)}/" class="text-decoration-none fw-bold">
          <i class="bi bi-box-arrow-up-right"></i> ${escapeHtml(t.name)}
        </a>
      </td>
      <td>
        <a href="http://${escapeHtml(t.url)}" target="_blank" class="text-muted text-decoration-none">
          <i class="bi bi-globe"></i> ${escapeHtml(t.url)}
        </a>
      </td>
      <td>${renderStatusBadge(t.is_build_success)}</td>
      <td>${renderStatusBadge(t.is_start_success)}</td>
      <td>
        <button class="btn btn-sm btn-outline-info logs-btn" data-tentacle="${escapeHtml(t.name)}">
          <i class="bi bi-file-text"></i> Logs
        </button>
        <button class="btn btn-sm restart-btn" data-tentacle="${escapeHtml(t.name)}">
          <i class="bi bi-arrow-repeat"></i> Restart
        </button>
      </td>
      <td class="tr-left">${escapeHtml(t.last_commit || "")}</td>
    `;

        tbody.appendChild(tr);
    }

    tbody.querySelectorAll(".logs-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            viewLogs(btn.dataset.tentacle);
        });
    });

    tbody.querySelectorAll(".restart-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            showRestartModal(btn.dataset.tentacle);
        });
    });
}

function renderStatusBadge(status) {
    if (status === true) return `<span class="badge status-badge" data-status="success"><i class="bi bi-check-circle"></i> OK</span>`;
    if (status === false) return `<span class="badge status-badge" data-status="danger"><i class="bi bi-x-circle"></i> FAIL</span>`;
    return `<span class="badge status-badge" data-status="warning"><i class="bi bi-clock"></i> WAIT</span>`;
}

function updateTentacleStatus(tentacleName, buildStatus, startStatus) {
    const row = document.querySelector(`tr[data-tentacle="${CSS.escape(tentacleName)}"]`);
    if (!row) return;
    row.children[2].innerHTML = renderStatusBadge(buildStatus);
    row.children[3].innerHTML = renderStatusBadge(startStatus);
}

/* Logs UI */

function viewLogs(tentacleName) {
    currentTentacle = tentacleName;
    const currentSpan = document.getElementById("current-tentacle");
    if (currentSpan) currentSpan.textContent = tentacleName;

    // Reset tabs
    const buildTab = document.getElementById("build-tab");
    const startTab = document.getElementById("start-tab");
    const buildPane = document.getElementById("build-logs");
    const startPane = document.getElementById("start-logs");

    buildTab.classList.add("active");
    startTab.classList.remove("active");
    buildPane.classList.add("show", "active");
    startPane.classList.remove("show", "active");

    // Loading placeholders
    document.getElementById("buildCommandTabs").innerHTML = `
    <li class="nav-item" role="presentation">
      <span class="nav-link active">
        <div class="spinner-border spinner-border-sm text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        Loading...
      </span>
    </li>
  `;
    document.getElementById("buildCommandTabContent").innerHTML = "";

    document.getElementById("start-logs-content").innerHTML = `
    <div class="text-center py-3">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>
    </div>
  `;

    tentacleLogsModal.show();

    // Load historic logs by HTTP
    loadLogs(tentacleName, "build");
    loadLogs(tentacleName, "start");

    // Request real-time logs via WS if connected
    if (socket && wsConnected) {
        socket.emit("request_logs", {tentacle: tentacleName, log_type: "start"});
        socket.emit("request_logs", {tentacle: tentacleName, log_type: "build"});
    }
}

async function loadLogs(tentacleName, logType) {
    try {
        const logs = await apiGetLogs(tentacleName, logType);
        updateLogsContent(logType, logs);
    } catch (err) {
        console.error(`Error loading ${logType} logs:`, err);
        const id = logType === "build" ? "buildCommandTabContent" : `${logType}-logs-content`;
        const el = document.getElementById(id);
        if (el) el.innerHTML = `<div class="alert alert-danger">Ошибка: ${escapeHtml(err.message)}</div>`;
    }
}

async function reloadSystemLogs() {
    clearSystemLogs();

    let json = await apiGetSystemLogs();
    json.logs.forEach(function (log, i, _) {
        console.log(log);
        addSystemLogLine(log.message, log.log_type);
    });
}

function clearSystemLogs() {
    const containerElement = document.getElementById("tentaclePreview-logs-container");

    containerElement.innerHTML = "";
}

function addSystemLogLine(logLine, status) {
    const containerElement = document.getElementById("tentaclePreview-logs-container");
    if (!logLine) {
        return;
    }

    const newLine = document.createElement('pre');
    newLine.classList.add("logs-content", "system-logs-content");

    switch (status) {
        case "error":
            newLine.classList.add("system-logs-error");
            break;
        case "grey":
            newLine.classList.add("system-logs-grey");
            break;
        case "header":
            newLine.classList.add("system-logs-header");
            break;
        case "success":
            newLine.classList.add("system-logs-success");
            break;
        case "warning":
            newLine.classList.add("system-logs-warning");
            break;
        default:
            newLine.classList.add("system-logs-info");
            break;
    }

    newLine.textContent = logLine;

    containerElement.appendChild(newLine);
    containerElement.scrollTop = containerElement.scrollHeight;
}

function updateLogsContent(logType, logs) {
    if (logType === "build") updateBuildLogs(logs);
    else if (logType === "start") updateStartLogs(logs);
}

function updateBuildLogs(logs) {
    const tabsContainer = document.getElementById("buildCommandTabs")
    const contentContainer = document.getElementById("buildCommandTabContent")

    if (!logs || !Array.isArray(logs) || logs.length === 0) {
        tabsContainer.innerHTML = `
      <li class="nav-item" role="presentation">
        <span class="nav-link active text-muted">No build commands</span>
      </li>
    `
        contentContainer.innerHTML = `
      <div class="text-muted text-center p-4"><i class="bi bi-info-circle"></i> No build logs available</div>
    `
        return
    }

    // Store currently active tab before rebuilding
    const currentActiveTab = tabsContainer.querySelector(".nav-link.active")
    const currentActiveIndex = currentActiveTab
        ? Array.from(tabsContainer.querySelectorAll(".nav-link")).indexOf(currentActiveTab)
        : 0

    tabsContainer.innerHTML = ""
    contentContainer.innerHTML = ""

    logs.forEach((cmd, idx) => {
        const commandName = cmd.command || `cmd-${idx}`
        const output = cmd.output || "(No output)"
        const tabId = `build-command-${idx}`
        // Preserve active state or default to first tab, but prefer the last tab for new builds
        const isActive =
            logs.length > currentActiveIndex + 1
                ? idx === logs.length - 1
                : // If new commands added, show the latest
                idx === Math.min(currentActiveIndex, logs.length - 1) // Otherwise preserve selection

        const li = document.createElement("li")
        li.className = "nav-item"
        li.setAttribute("role", "presentation")

        const btn = document.createElement("button")
        btn.className = `nav-link ${isActive ? "active" : ""}`
        btn.id = `${tabId}-tab`
        btn.type = "button"
        btn.setAttribute("data-bs-toggle", "tab")
        btn.setAttribute("data-bs-target", `#${tabId}`)
        btn.setAttribute("role", "tab")
        btn.setAttribute("aria-controls", tabId)
        btn.setAttribute("aria-selected", isActive.toString())
        btn.title = commandName
        btn.textContent = commandName

        li.appendChild(btn)
        tabsContainer.appendChild(li)

        const pane = document.createElement("div")
        pane.className = `tab-pane fade ${isActive ? "show active" : ""}`
        pane.id = tabId
        pane.setAttribute("role", "tabpanel")
        pane.setAttribute("aria-labelledby", `${tabId}-tab`)

        const contentDiv = document.createElement("div")
        contentDiv.className = "build-command-content"

        const pre = document.createElement("pre")
        pre.textContent = output

        contentDiv.appendChild(pre)
        pane.appendChild(contentDiv)
        contentContainer.appendChild(pane)
    })

    // Reinitialize bootstrap tabs after rebuilding
    const bootstrap = window.bootstrap // Declare the bootstrap variable
    Array.from(tabsContainer.querySelectorAll('button[data-bs-toggle="tab"]')).forEach((btn) => {
        // Remove any existing tab instances
        const existingTab = bootstrap.Tab.getInstance(btn)
        if (existingTab) {
            existingTab.dispose()
        }
        // Create new tab instance
        new bootstrap.Tab(btn)
    })

    console.log("Build tabs updated, total commands:", logs.length)
}

function updateStartLogs(logs) {
    const contentElement = document.getElementById("start-logs-content");
    if (!logs || !Array.isArray(logs) || logs.length === 0) {
        contentElement.textContent = "No start logs available";
        return;
    }

    contentElement.textContent = logs.join("\n");

    const container = contentElement.parentElement;
    if (container) container.scrollTop = container.scrollHeight;
}

function appendStartLogLine(line) {
    const contentElement = document.getElementById("start-logs-content");
    if (!contentElement) return;

    // Если внутри есть spinner — очистить и перейти к тексту
    if (contentElement.querySelector && contentElement.querySelector(".spinner-border")) {
        contentElement.textContent = "";
    }

    contentElement.textContent += (contentElement.textContent ? "\n" : "") + line;

    const container = contentElement.parentElement;
    if (container) container.scrollTop = container.scrollHeight;
}

function showRestartModal(tentacleName) {
    currentTentacle = tentacleName;
    const currentSpan = document.getElementById("current-tentacle-restart");
    if (currentSpan) currentSpan.textContent = tentacleName;

    restartTentacleModal.show();
}

/* WebSocket (Socket.IO) */

function initWebSocket(forceReconnect = false) {
    if (socket && wsConnected && !forceReconnect) return;

    if (socket) {
        try {
            socket.disconnect();
        } catch {
        }
        socket = null;
        wsConnected = false;
    }

    socket = io({transports: ["websocket"]});

    socket.on("connect", () => {
        wsConnected = true;
        console.info("WS connected");
        socket.emit("request_status");
    });

    socket.on("disconnect", () => {
        wsConnected = false;
        console.warn("WS disconnected");
    });

    socket.on("status_update", (data) => {
        if (!data) return;
        if (Array.isArray(data.tentacles)) {
            renderTentacleTable(data.tentacles);
        } else if (data.tentacle) {
            updateTentacleStatus(data.tentacle, data.build_status, data.start_status);
        }
    });

    socket.on("logs_update", (data) => {
        if (!data || data.tentacle !== currentTentacle) return;

        const logType = data.log_type;
        const payload = data.logs;

        if (data.stream === true) {
            if (logType === "start" && payload && payload.output) {
                appendStartLogLine(payload.output);
            }
            return;
        }

        updateLogsContent(logType, payload);
    });

    socket.on("connection_status", (d) => {
        console.debug("connection_status:", d);
    });

    socket.on("connect_error", (err) => {
        wsConnected = false;
        console.warn("WS connect_error", err);
    });

    socket.on("system_logs_update", (log_entry) => {
        console.log("WS system logs", log_entry);
        addSystemLogLine(log_entry.message, log_entry.log_type)
    })
}

/* Utilities */

function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return "";
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showNotification(message, type = "info") {
    const notification = document.createElement("div");
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = "top: 20px; right: 20px; z-index: 9999; min-width: 300px;";
    notification.innerHTML = `${escapeHtml(message)}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;

    document.body.appendChild(notification);
    setTimeout(() => {
        if (notification.parentNode) notification.remove();
    }, 5000);
}

/* spin animation style */
(function addSpinStyle() {
    const s = document.createElement("style");
    s.textContent = `.spin{animation:spin 1s linear infinite}@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`;
    document.head.appendChild(s);
})();
