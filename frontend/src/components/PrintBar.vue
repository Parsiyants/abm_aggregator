<!-- components/PrintBar.vue -->
<script setup>
import { ref, computed } from 'vue'
import { useOrdersStore } from '@/stores/orders'
import { useNotificationStore } from '@/stores/notifications'
import api from '@/services/api'

const ordersStore = useOrdersStore()
const notify = useNotificationStore()

const isPrinting = ref(false)

// Цвета для кнопок маркетов
const marketColors = {
  ozon: { bg: 'bg-blue-600 hover:bg-blue-700', text: 'text-white' },
  yandex: { bg: 'bg-yellow-500 hover:bg-yellow-600', text: 'text-gray-800' },
  wb: { bg: 'bg-purple-600 hover:bg-purple-700', text: 'text-white' },
  avito: { bg: 'bg-green-600 hover:bg-green-700', text: 'text-white' },
}

const marketLabels = {
  ozon: 'Ozon',
  yandex: 'Яндекс',
  wb: 'WB',
  avito: 'Avito',
}

const printLabels = async (market, orders) => {
  if (orders.length === 0) {
    notify.add({ type: 'warning', message: `Нет заказов ${marketLabels[market]} для печати` })
    return
  }

  // Формируем payload для бекенда
  const payload = {
    orders: orders.map((order) => ({
      order_id: order.order_id,
      status: order.status,
      cabinet_id: order.cabinet_id,
    })),
  }

  isPrinting.value = true

  try {
    const response = await api.post('/orders/labels/print', payload)
    const data = response.data

    // Проверяем, есть ли этикетки в ответе
    if (data.labels) {
      // Открываем PDF в новой вкладке
      const pdfBase64 = data.labels
      const byteCharacters = atob(pdfBase64)
      const byteNumbers = new Array(byteCharacters.length)
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
      }
      const byteArray = new Uint8Array(byteNumbers)
      const blob = new Blob([byteArray], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
      URL.revokeObjectURL(url)

      // Показываем результат
      const successCount = data.results.filter((r) => r.status === 'ready').length
      const errorCount = data.results.filter((r) => r.status === 'error').length

      if (successCount > 0) {
        notify.add({
          type: 'success',
          message: `Напечатано ${successCount} этикеток для ${marketLabels[market]}`,
        })
      }

      if (errorCount > 0) {
        notify.add({
          type: 'error',
          message: `Не удалось напечатать ${errorCount} этикеток для ${marketLabels[market]}`,
        })
      }

      // Очищаем выбор после успешной печати
      ordersStore.clearSelectedOrders()
    } else {
      // Если нет labels, показываем ошибки
      const errors = data.results?.filter((r) => r.status === 'error') || []
      if (errors.length > 0) {
        notify.add({
          type: 'error',
          message: `Не удалось напечатать ${errors.length} этикеток для ${marketLabels[market]}`,
        })
      }
    }
  } catch (error) {
    console.error('Print error:', error)
    notify.add({ type: 'error', message: `Ошибка при печати этикеток ${marketLabels[market]}` })
  } finally {
    isPrinting.value = false
  }
}
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="ordersStore.hasSelectedOrders"
      class="fixed bottom-4 left-1/2 transform -translate-x-1/2 bg-white border border-slate-200 rounded-2xl shadow-2xl px-6 py-4 z-50 min-w-[500px]"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <span class="text-gray-700">
            Выбрано заказов: <b class="text-lg">{{ ordersStore.selectedOrdersCount }}</b>
          </span>

          <!-- Кнопки для каждого маркетплейса -->
          <div class="flex gap-2">
            <button
              v-for="(group, market) in ordersStore.groupedOrdersByMarket"
              :key="market"
              @click="printLabels(market, group.orders)"
              :disabled="isPrinting"
              :class="[
                marketColors[market]?.bg || 'bg-gray-600',
                marketColors[market]?.text || 'text-white',
              ]"
              class="px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span class="material-symbols-outlined text-lg">print</span>
              {{ marketLabels[market] }} ({{ group.count }})
            </button>
          </div>
        </div>

        <button
          @click="ordersStore.clearSelectedOrders"
          class="ml-4 p-2 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <!-- Индикатор загрузки -->
      <div v-if="isPrinting" class="mt-3">
        <div class="flex items-center gap-2 text-sm text-gray-500">
          <div
            class="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"
          ></div>
          Печать этикеток... (может занять до 30 секунд)
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.45s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(80%) scale(0.94);
  opacity: 0;
}

.slide-up-enter-to,
.slide-up-leave-from {
  transform: translateY(0) scale(1);
  opacity: 1;
}
</style>
