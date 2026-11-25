import { defineStore } from 'pinia'
import api from '@/services/api'
import { ref } from 'vue'
import { useNotificationStore } from './notifications'

export const useReferenceStore = defineStore('references', () => {
  const notify = useNotificationStore()
  const providers = ref([])
  const statuses = ref([])
  const marketplaces = ref([])
  const cabinets = ref([])
  const loading = ref(false)

  // Универсальный загрузчик данных
  const fetchAll = async (refType) => {
    loading.value = true
    try {
      const { data } = await api.get(`/references/${refType}`)
      if (refType === 'providers')
        ((providers.value = data), console.log(`providers - ${providers.value}`))
      if (refType === 'statuses')
        ((statuses.value = data), console.log(`statuses - ${statuses.value}`))
      if (refType === 'marketplaces')
        ((marketplaces.value = data), console.log(`marketplaces - ${marketplaces.value}`))
      if (refType === 'cabinets')
        ((cabinets.value = data), console.log(`cabinets - ${cabinets.value}`))
    } catch (e) {
      notify.add(`Ошибка загрузки ${refType}`, 'error')
    } finally {
      loading.value = false
    }
  }

  // Универсальный метод создания/обновления
  const upsertItem = async (refType, item) => {
    try {
      const id = item._id || item.id // Проверяем оба варианта

      // Подготовка данных: удаляем служебные поля перед отправкой, если нужно
      const payload = { ...item }
      delete payload._id
      delete payload.id

      if (id) {
        await api.put(`/references/${refType}/${id}`, payload)
        notify.add('Обновлено', 'success')
      } else {
        await api.post(`/references/${refType}`, payload)
        notify.add('Создано', 'success')
      }

      await fetchAll(refType)
      return true
    } catch (e) {
      console.error(e)
      notify.add('Ошибка валидации или сервера', 'error')
      return false
    }
  }

  const deleteItem = async (refType, id) => {
    try {
      await api.delete(`/references/${refType}/${id}`)
      notify.add('Удалено', 'success')
      await fetchAll(refType)
    } catch (e) {
      notify.add('Ошибка при удалении', 'error')
    }
  }

  /**
   * Сохранить ручную очерёдность (статусы, поставщики).
   * Принимает массив id в новом порядке.
   */
  const reorderItems = async (refType, ids) => {
    try {
      await api.post(`/references/${refType}/reorder`, { ids })
      await fetchAll(refType)
      return true
    } catch (e) {
      console.error(e)
      notify.add('Не удалось сохранить порядок', 'error')
      await fetchAll(refType)
      return false
    }
  }

  return {
    providers,
    statuses,
    marketplaces,
    cabinets,
    loading,
    fetchAll,
    upsertItem,
    deleteItem,
    reorderItems,
  }
})
