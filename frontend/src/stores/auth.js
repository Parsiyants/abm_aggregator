// src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import wsService from '@/services/websocket.service'
import { useRouter } from 'vue-router'

export const useAuthStore = defineStore('auth', () => {
  // ── State ────────────────────────────────────────────────
  const token = ref(localStorage.getItem('userToken') || null)
  const user_email = ref(null)
  const wsConnected = ref(false)

  // ── Getters ──────────────────────────────────────────────
  const isLoggedIn = computed(() => !!token.value)

  // ── Actions ──────────────────────────────────────────────
  async function login(email, password) {
    try {
      const { data } = await api.post('/auth/login', { email, password })
      const { access_token } = data

      token.value = access_token
      user_email.value = email
      localStorage.setItem('userToken', access_token)
      localStorage.setItem('userEmail', email)

      connectWebSocket(access_token)

      return true
    } catch (err) {
      logout()
      throw err
    }
  }

  async function register(email, password) {
    // Регистрация закрыта для анонимов: пользователей создаёт только
    // авторизованный админ. Текущую сессию не трогаем (токен не перезаписываем).
    const { data } = await api.post('/auth/register', { email, password })
    return data
  }

  function logout() {
    token.value = null
    user_email.value = null
    localStorage.removeItem('userToken')
    localStorage.removeItem('userEmail')
    disconnectWebSocket()
  }

  // ── WebSocket handlers ───────────────────────────────────
  function connectWebSocket(t = token.value) {
    if (!t) return

    wsService.connect(t)

    wsService.on('open', () => {
      wsConnected.value = true
      console.log('WS Status: Connected')
      // wsService.send('get_user_data') // ← можно раскомментировать
    })

    wsService.on('close', () => {
      wsConnected.value = false
      console.log('WS Status: Disconnected')
    })
  }

  function disconnectWebSocket() {
    wsService.disconnect()
    wsConnected.value = false
  }

  // ── Инициализация при создании стора ─────────────────────
  function initialize() {
    if (isLoggedIn.value) {
      connectWebSocket()
    }
  }

  // Автоматическая инициализация при первом обращении к стору
  initialize()

  // ── Public API стора ─────────────────────────────────────
  return {
    // state
    token,
    user_email,
    wsConnected,

    // getters
    isLoggedIn,

    // actions
    login,
    register,
    logout,
    connectWebSocket,
    disconnectWebSocket,
    initialize,
  }
})