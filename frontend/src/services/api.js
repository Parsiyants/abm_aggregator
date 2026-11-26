import axios from 'axios'

// Базовый URL вашего FastAPI (должен совпадать с тем, где запущен бэкенд)
const API_URL = import.meta.env.VITE_API_URL

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Интерсептор: добавляет токен в заголовок Authorization для всех запросов
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('userToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// Интерсептор ответа: токен истёк/отозван → выкидываем на логин.
// /auth/login исключён: там 401 значит «неверный пароль», а не «сессия истекла».
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const url = String(error?.config?.url || '')

    if (status === 401 && !url.includes('/auth/login')) {
      localStorage.removeItem('userToken')
      localStorage.removeItem('userEmail')

      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
    }

    return Promise.reject(error)
  },
)

export default api
