import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = ref([])

  const add = (message, type = 'info', duration = 4000) => {
    const id = Date.now()
    notifications.value.push({ id, message, type })

    setTimeout(() => {
      remove(id)
    }, duration)
  }

  const remove = (id) => {
    notifications.value = notifications.value.filter((n) => n.id !== id)
  }

  return { notifications, add, remove }
})
