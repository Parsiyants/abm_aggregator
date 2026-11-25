// src/stores/orders.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notifications'

export const useOrdersStore = defineStore('orders', () => {
  // ── State ────────────────────────────────────────────────
  const orders = ref({
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    limit: 20,
    skip: 0,
    total_price: 0,
    total_purchase: 0,
  })
  const newOrders = ref({
    items: [],
    total: 0,
    page: 1,
    pages: 1,
    limit: 20,
    skip: 0,
    total_price: 0,
    total_purchase: 0,
  })
  const loading = ref(false)
  const error = ref(null)

  const notificationStore = useNotificationStore()

  // ── Печать этикеток ──────────────────────────────────────
  const selectedOrdersForPrint = ref([])

  const hasSelectedOrders = computed(() => selectedOrdersForPrint.value.length > 0)
  const selectedOrdersCount = computed(() => selectedOrdersForPrint.value.length)

  const groupedOrdersByMarket = computed(() => {
    const groups = {}
    for (const order of selectedOrdersForPrint.value) {
      if (!groups[order.market_type]) {
        groups[order.market_type] = {
          market: order.market_type,
          orders: [],
          count: 0,
        }
      }
      groups[order.market_type].orders.push(order)
      groups[order.market_type].count++
    }
    return groups
  })

  const toggleOrderSelection = (orderData) => {
    const index = selectedOrdersForPrint.value.findIndex(
      (o) => o.order_id === orderData.order_id && o.cabinet_id === orderData.cabinet_id,
    )
    if (index === -1) {
      selectedOrdersForPrint.value.push(orderData)
    } else {
      selectedOrdersForPrint.value.splice(index, 1)
    }
  }

  const clearSelectedOrders = () => {
    selectedOrdersForPrint.value = []
  }

  const isOrderSelected = (orderId) => {
    return selectedOrdersForPrint.value.find((o) => o.order_id === orderId)
  }

  // ── Загрузка ─────────────────────────────────────────────
  async function fetchOrders(params = {}, status_new = 'order') {
    loading.value = true
    error.value = null

    try {
      const response = await api.get('/orders/', { params })
      const data = response.data

      if (status_new === 'new') {
        newOrders.value = {
          items: [...data.items] || [],
          total: data.total || 0,
          page: data.page || 1,
          pages: data.pages || 1,
          limit: data.limit || 10,
          skip: data.skip || 0,
          total_price: data.total_price || 0,
          total_purchase: data.total_purchase || 0,
        }
      } else if (status_new === 'order') {
        orders.value = {
          items: [...data.items] || [],
          total: data.total || 0,
          page: data.page || 1,
          pages: data.pages || 1,
          limit: data.limit || 20,
          skip: data.skip || 0,
          total_price: data.total_price || 0,
          total_purchase: data.total_purchase || 0,
        }
      }

      return data
    } catch (err) {
      console.error('Ошибка загрузки заказов:', err)
      error.value = err.message || 'Не удалось загрузить заказы'
      return { items: [], total: 0, page: 1, pages: 1, limit: 20, skip: 0 }
    } finally {
      loading.value = false
    }
  }

  // ── WebSocket: новый заказ ───────────────────────────────
  function addLiveOrder(newOrder) {
    if (!newOrder?.order_id) return

    // Проверяем, есть ли уже в списке
    const existingIndex = newOrders.items.findIndex((o) => o.order_id === newOrder.order_id)
    
    if (existingIndex !== -1) {
      // Обновляем существующий
      newOrders.items[existingIndex] = { ...newOrders.items[existingIndex], ...newOrder }
      return
    }

    // Добавляем новый в начало
    newOrders.items.unshift(newOrder)
    newOrders.total = (newOrders.total || 0) + 1
    notificationStore.add(`🆕 Новый заказ #${newOrder.order_id}`, 'info')
    console.log(`✅ Добавлен новый заказ #${newOrder.order_id}`)
  }

  // ── WebSocket: обновлённый заказ ────────────────────────
  function updateLiveOrder(orderData) {
    if (!orderData?.order_id) return

    // Обновляем в orders
    const ordersIndex = orders.items.findIndex((o) => o.order_id === orderData.order_id)
    if (ordersIndex !== -1) {
      orders.items[ordersIndex] = { ...orders.items[ordersIndex], ...orderData }
    }

    // Обновляем в newOrders
    const newOrdersIndex = newOrders.items.findIndex((o) => o.order_id === orderData.order_id)
    if (newOrdersIndex !== -1) {
      // Если статус изменился на Process/Done/Cancel — удаляем из новых
      if (orderData.process_status !== 'New') {
        newOrders.items.splice(newOrdersIndex, 1)
        newOrders.total = Math.max(0, (newOrders.total || 0) - 1)
        console.log(`🗑️ Заказ #${orderData.order_id} удалён из новых (статус: ${orderData.process_status})`)
      } else {
        newOrders.items[newOrdersIndex] = { ...newOrders.items[newOrdersIndex], ...orderData }
        console.log(`🔄 Заказ #${orderData.order_id} обновлён в новых`)
      }
    }
  }

  // ── Получение заказа по ID ──────────────────────────────
  async function fetchOrderById(id) {
    loading.value = true
    error.value = null

    try {
      const { data } = await api.get(`/orders/${id}`)
      return data
    } catch (err) {
      console.error(`[Orders] fetchOrderById(${id}) failed:`, err)
      return null
    } finally {
      loading.value = false
    }
  }

  // ── Обработка заказа ─────────────────────────────────────
  async function handleOrder(orderId, payload) {
    try {
      const response = await api.patch(`/orders/${orderId}/handle`, payload)

      if (response) {
        const data = response.data
        const orderIdDisplay = data?.order?.order_id || orderId

        // Обновляем в основном списке
        const mainIndex = orders.value.items.findIndex((o) => o._id === orderId || o.id === orderId)
        if (mainIndex !== -1 && data?.order) {
          orders.value.items.splice(mainIndex, 1, {
            ...orders.value.items[mainIndex],
            ...data.order,
          })
        }

        // Обновляем в newOrders
        const newIndex = newOrders.value.items.findIndex((o) => o._id === orderId || o.id === orderId)
        if (newIndex !== -1) {
          if (data?.order?.process_status === 'Process') {
            newOrders.value.items.splice(newIndex, 1)
            newOrders.value.total = Math.max(0, (newOrders.value.total || 0) - 1)
          } else if (data?.order) {
            newOrders.value.items.splice(newIndex, 1, {
              ...newOrders.value.items[newIndex],
              ...data.order,
            })
          }
        }

        notificationStore.add(`✅ Заказ #${orderIdDisplay} обновлён`, 'success')
        return { success: true, message: 'Заказ успешно обновлён', order: data?.order }
      }
      return { success: false, message: 'Не удалось обновить заказ' }
    } catch (err) {
      console.error('Ошибка обработки заказа:', err)
      return {
        success: false,
        message: err.response?.data?.detail || 'Не удалось обработать заказ',
      }
    }
  }

  // ── Массовое обновление статусов товаров ────────────────
  async function bulkUpdateItemStatuses(updates) {
    try {
      const payload = Array.from(updates.entries()).map(([item_id, status]) => ({
        item_id,
        status,
      }))

      const response = await api.patch('/orders/items/status', { updates: payload })
      if (response) {
        notificationStore.add('Статусы товаров успешно обновлены', 'success')

        payload.forEach(({ item_id, status }) => {
          for (const order of orders.value.items) {
            const item = order.items?.find((i) => i._id === item_id)
            if (item) item.status = status
          }
        })

        return true
      }
      return false
    } catch (err) {
      notificationStore.add('Ошибка при обновлении статусов товаров', 'error')
      console.error('Ошибка обновления статусов товаров:', err)
    }
  }

  // ── Public API ───────────────────────────────────────────
  return {
    // state
    orders,
    newOrders,
    loading,
    error,

    // print state
    selectedOrdersForPrint,
    hasSelectedOrders,
    selectedOrdersCount,
    groupedOrdersByMarket,

    // print actions
    toggleOrderSelection,
    clearSelectedOrders,
    isOrderSelected,

    // actions
    fetchOrders,
    addLiveOrder,
    updateLiveOrder,
    fetchOrderById,
    handleOrder,
    bulkUpdateItemStatuses,
  }
})