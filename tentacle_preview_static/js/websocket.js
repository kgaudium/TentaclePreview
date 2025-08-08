class WebSocketManager {
  constructor() {
    this.socket = null
    this.isConnected = false
    this.callbacks = {
      status_update: [],
      logs_update: [],
      connection_change: [],
    }
  }

  connect() {
    try {
      this.socket = io({ path: "/socket.io" })

      this.socket.on("connect", () => {
        console.log("Socket.IO connected")
        this.isConnected = true
        this.trigger("connection_change", { connected: true })
        this.updateConnectionStatus(true)
      })

      this.socket.on("disconnect", () => {
        console.warn("Socket.IO disconnected")
        this.isConnected = false
        this.trigger("connection_change", { connected: false })
        this.updateConnectionStatus(false)
      })

      this.socket.on("status_update", (data) => {
        this.trigger("status_update", data)
      })

      this.socket.on("logs_update", (data) => {
        this.trigger("logs_update", data)
      })

      this.socket.on("connect_error", (err) => {
        console.error("Socket.IO connection error:", err)
      })
    } catch (error) {
      console.error("Failed to connect via Socket.IO:", error)
    }
  }

  send(event, data) {
    if (this.isConnected && this.socket) {
      this.socket.emit(event, data)
    }
  }

  on(event, callback) {
    if (this.callbacks[event]) {
      this.callbacks[event].push(callback)
    }
  }

  trigger(event, data) {
    if (this.callbacks[event]) {
      this.callbacks[event].forEach((cb) => cb(data))
    }
  }

  updateConnectionStatus(connected) {
    const statusElement = document.getElementById("connection-status")
    if (statusElement) {
      if (connected) {
        statusElement.className = "badge bg-success online"
        statusElement.innerHTML = '<i class="bi bi-circle-fill"></i> Online'
      } else {
        statusElement.className = "badge bg-secondary offline"
        statusElement.innerHTML = '<i class="bi bi-circle-fill"></i> Offline'
      }
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
    }
  }
}

window.wsManager = new WebSocketManager()

document.addEventListener("DOMContentLoaded", () => {
  window.wsManager.connect()
})
