// URL WebSocket определяется в _getWebSocketUrl():
// - VITE_WS_URL, если задан при сборке (dev / отдельный домен API);
// - иначе ws(s)://<текущий host>/api/v1/ws (прод за nginx).

class WebSocketService {
  constructor() {
    this.socket = null
    this.listeners = new Map()
    this.reconnectTimeout = null
  }

  connect(token) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) return

    // Передаем токен для авторизации WS
    const url = this._getWebSocketUrl(token)
    this.socket = new WebSocket(url)

    this.socket.onopen = () => {
      console.log('WebSocket подключен.')
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout)
        this.reconnectTimeout = null
      }
      this._notify('open', null)
    }

    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        this._notify(message.type, message.data)
      } catch (e) {
        console.error('Ошибка парсинга сообщения WebSocket:', e)
      }
    }

    this.socket.onclose = (event) => {
      console.warn('WebSocket отключен.', event.code, event.reason)
      this._notify('close', event)

      // Если закрытие не нормальное (1000), пытаемся переподключиться
      if (event.code !== 1000) {
        this.reconnectTimeout = setTimeout(() => {
          console.log('Попытка переподключения...')
          this.connect(token)
        }, 5000)
      }
    }

    this.socket.onerror = (error) => {
      console.error('Ошибка WebSocket:', error)
      this._notify('error', error)
    }
  }

   _getWebSocketUrl(token) {
    // 1. Проверяем, есть ли явный URL в переменных окружения
    const customWsUrl = import.meta.env.VITE_WS_URL
    
    if (customWsUrl) {
      // Если есть — используем его (для продакшена)
      let url = customWsUrl
      if (token) {
        url += `${url.includes('?') ? '&' : '?'}token=${token}`
      }
      return url
    }

    // 2. Иначе определяем автоматически (для разработки и прод-сборки за nginx)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const path = '/api/v1/ws'
    let url = `${protocol}//${host}${path}`
    
    if (token) {
      url += `?token=${token}`
    }
    
    return url
  }

  send(type, data = {}) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ type, data })
      this.socket.send(message)
    } else {
      console.error('WebSocket не подключен. Невозможно отправить сообщение:', type)
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.close(1000, 'User logout')
      this.socket = null
    }
  }

  // Методы для подписки и отписки компонентов на сообщения
  on(type, callback) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type).add(callback)
  }

  off(type, callback) {
    if (this.listeners.has(type)) {
      this.listeners.get(type).delete(callback)
    }
  }

  _notify(type, data) {
    if (this.listeners.has(type)) {
      this.listeners.get(type).forEach((callback) => callback(data))
    }
  }
}

export default new WebSocketService()
