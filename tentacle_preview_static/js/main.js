let currentTentacle = null
let logsModal = null
const bootstrap = window.bootstrap // Declare the bootstrap variable

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Bootstrap modal
  logsModal = new bootstrap.Modal(document.getElementById("logsModal"))

  // Setup WebSocket event listeners
  // setupWebSocketListeners()

  // Auto-refresh data every 5 seconds
  setInterval(refreshData, 5000)
})

// function setupWebSocketListeners() {
//   // Listen for status updates
//   window.wsManager.on("status_update", (data) => {
//     updateTentacleStatus(data.tentacle, data.build_status, data.start_status)
//   })
//
//   // Listen for logs updates
//   window.wsManager.on("logs_update", (data) => {
//     if (data.tentacle === currentTentacle) {
//       updateLogsContent(data.log_type, data.logs)
//     }
//   })
// }

function updateTentacleStatus(tentacleName, buildStatus, startStatus) {
  const row = document.querySelector(`tr[data-tentacle="${tentacleName}"]`)
  if (!row) return

  const buildBadge = row.querySelector("td:nth-child(3) .status-badge")
  const startBadge = row.querySelector("td:nth-child(4) .status-badge")

  if (buildBadge) {
    updateStatusBadge(buildBadge, buildStatus)
  }

  if (startBadge) {
    updateStatusBadge(startBadge, startStatus)
  }
}

function updateStatusBadge(badge, status) {
  badge.classList.add("updating")

  setTimeout(() => {
    let statusClass, statusText, iconClass

    if (status === true) {
      statusClass = "success"
      statusText = "OK"
      iconClass = "check-circle"
    } else if (status === false) {
      statusClass = "danger"
      statusText = "FAIL"
      iconClass = "x-circle"
    } else {
      statusClass = "warning"
      statusText = "WAIT"
      iconClass = "clock"
    }

    badge.setAttribute("data-status", statusClass)
    badge.innerHTML = `<i class="bi bi-${iconClass}"></i> ${statusText}`
    badge.classList.remove("updating")
  }, 150)
}

function refreshData() {
  const button = document.querySelector('button[onclick="refreshData()"]')
  const originalContent = button.innerHTML

  button.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Refreshing...'
  button.disabled = true

  fetch("/api/tentacles")
    .then((response) => response.json())
    .then((data) => {
      updateTentaclesTable(data.tentacles)
    })
    .catch((error) => {
      console.error("Error refreshing data:", error)
      showNotification("Error refreshing data", "danger")
    })
    .finally(() => {
      button.innerHTML = originalContent
      button.disabled = false
    })
}

function updateTentaclesTable(tentacles) {
  const tbody = document.getElementById("tentacles-tbody")

  tentacles.forEach((tentacle) => {
    updateTentacleStatus(tentacle.name, tentacle.is_build_success, tentacle.is_start_success)
  })
}

function viewLogs(tentacleName) {
  currentTentacle = tentacleName
  document.getElementById("current-tentacle").textContent = tentacleName

  // Reset tabs to build logs
  const buildTab = document.getElementById("build-tab")
  const startTab = document.getElementById("start-tab")
  const buildPane = document.getElementById("build-logs")
  const startPane = document.getElementById("start-logs")

  buildTab.classList.add("active")
  startTab.classList.remove("active")
  buildPane.classList.add("show", "active")
  startPane.classList.remove("show", "active")

  // Show loading state for build logs
  const buildTabsContainer = document.getElementById("buildCommandTabs")
  const buildContentContainer = document.getElementById("buildCommandTabContent")
  buildTabsContainer.innerHTML = `
    <li class="nav-item" role="presentation">
      <span class="nav-link active">
        <div class="spinner-border spinner-border-sm text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        Loading...
      </span>
    </li>
  `
  buildContentContainer.innerHTML = ""

  // Show loading state for start logs
  document.getElementById("start-logs-content").innerHTML = `
    <div class="text-center">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
    </div>
  `

  // Show modal
  logsModal.show()

  // Load logs
  loadLogs(tentacleName, "build")
  loadLogs(tentacleName, "start")
}

function loadLogs(tentacleName, logType) {
  fetch(`/api/tentacles/${tentacleName}/logs/${logType}`)
    .then((response) => response.json())
    .then((data) => {
      updateLogsContent(logType, data.logs)
    })
    .catch((error) => {
      console.error(`Error loading ${logType} logs:`, error)
      if (logType === "build") {
        const tabsContainer = document.getElementById("buildCommandTabs")
        const contentContainer = document.getElementById("buildCommandTabContent")
        tabsContainer.innerHTML = ""
        contentContainer.innerHTML = `
          <div class="alert alert-danger" role="alert">
            <i class="bi bi-exclamation-triangle"></i>
            Error loading logs: ${error.message}
          </div>
        `
      } else {
        const contentElement = document.getElementById(`${logType}-logs-content`)
        contentElement.innerHTML = `Error loading logs: ${error.message}`
      }
    })
}

function updateLogsContent(logType, logs) {
  if (logType === "build") {
    updateBuildLogs(logs)
  } else if (logType === "start") {
    updateStartLogs(logs)
  }
}

function updateBuildLogs(logs) {
  const tabsContainer = document.getElementById("buildCommandTabs")
  const contentContainer = document.getElementById("buildCommandTabContent")

  if (!logs || !logs.commands || logs.commands.length === 0) {
    tabsContainer.innerHTML = `
      <li class="nav-item" role="presentation">
        <span class="nav-link active text-muted">No build commands</span>
      </li>
    `
    contentContainer.innerHTML = `
      <div class="text-muted text-center p-4">
        <i class="bi bi-info-circle"></i>
        No build logs available
      </div>
    `
    return
  }

  // Clear existing content
  tabsContainer.innerHTML = ""
  contentContainer.innerHTML = ""

  // Create tabs and content for each command
  logs.commands.forEach((commandData, index) => {
    const commandName = commandData.command
    const commandOutput = commandData.output
    const tabId = `build-command-${index}`
    const isActive = index === 0

    // Create tab
    const tabItem = document.createElement("li")
    tabItem.className = "nav-item"
    tabItem.setAttribute("role", "presentation")

    const tabButton = document.createElement("button")
    tabButton.className = `nav-link ${isActive ? "active" : ""}`
    tabButton.id = `${tabId}-tab`
    tabButton.setAttribute("data-bs-toggle", "tab")
    tabButton.setAttribute("data-bs-target", `#${tabId}`)
    tabButton.setAttribute("type", "button")
    tabButton.setAttribute("role", "tab")
    tabButton.setAttribute("aria-controls", tabId)
    tabButton.setAttribute("aria-selected", isActive.toString())
    tabButton.textContent = commandName
    tabButton.title = commandName // Tooltip for long command names

    tabItem.appendChild(tabButton)
    tabsContainer.appendChild(tabItem)

    // Create content
    const contentPane = document.createElement("div")
    contentPane.className = `tab-pane fade ${isActive ? "show active" : ""}`
    contentPane.id = tabId
    contentPane.setAttribute("role", "tabpanel")
    contentPane.setAttribute("aria-labelledby", `${tabId}-tab`)

    const contentDiv = document.createElement("div")
    contentDiv.className = "build-command-content"

    const preElement = document.createElement("pre")
    preElement.textContent = commandOutput || "(No output)"

    contentDiv.appendChild(preElement)
    contentPane.appendChild(contentDiv)
    contentContainer.appendChild(contentPane)
  })

  // Initialize Bootstrap tabs after creating them
  const tabTriggerList = [].slice.call(tabsContainer.querySelectorAll('button[data-bs-toggle="tab"]'))
  tabTriggerList.map((tabTriggerEl) => new bootstrap.Tab(tabTriggerEl))
}

function updateStartLogs(logs) {
  const contentElement = document.getElementById("start-logs-content")

  if (!logs || !logs.output) {
    contentElement.textContent = "No start logs available"
    return
  }

  contentElement.textContent = logs.output

  // Auto-scroll to bottom
  const container = contentElement.parentElement
  container.scrollTop = container.scrollHeight
}

function getLogEntryClass(level) {
  switch (level.toLowerCase()) {
    case "error":
      return "error"
    case "warning":
    case "warn":
      return "warning"
    case "info":
      return "info"
    default:
      return ""
  }
}

function escapeHtml(text) {
  const div = document.createElement("div")
  div.textContent = text
  return div.innerHTML
}

function refreshLogs() {
  if (currentTentacle) {
    loadLogs(currentTentacle, "build")
    loadLogs(currentTentacle, "start")
  }
}

function showNotification(message, type = "info") {
  // Create notification element
  const notification = document.createElement("div")
  notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`
  notification.style.cssText = "top: 20px; right: 20px; z-index: 9999; min-width: 300px;"
  notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `

  document.body.appendChild(notification)

  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.remove()
    }
  }, 5000)
}

// Add CSS for spinning animation
const style = document.createElement("style")
style.textContent = `
    .spin {
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`
document.head.appendChild(style)
