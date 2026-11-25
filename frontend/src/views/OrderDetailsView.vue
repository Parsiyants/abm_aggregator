<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { useAppStore } from '@/stores/app'
import { useReferenceStore } from '@/stores/references'
import { useNotificationStore } from '@/stores/notifications'
import { useFunction } from '@/composables/function'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()
const ordersStore = useOrdersStore()
const app = useAppStore()
const refStore = useReferenceStore()
const notification = useNotificationStore()
const { formatPrice, copy, formatDate, getRussianStatus, getStatusDescription, getStatusBadgeClasses, getProcessStatus, getSubstatusLabel, getMarketColor, sortByIndex } = useFunction()

const order = ref(null)
const loading = ref(true)
const error = ref(null)
const statuses = ref([])
const showStatusDropdown = ref({})
const updatingStatus = ref(false)
const isPrinting = ref(false)

// ── История заказа ─────────────────────────────────────────
const history = ref({ items: [], total: 0 })
const historyLoading = ref(false)
const historyError = ref(null)
const expandedChanges = ref({}) // { [logId]: true }

// ── Computed ────────────────────────────────────────────────
const totalPurchase = computed(() => {
  return order.value?.items?.reduce((sum, item) => sum + (item.purchase || 0) * (item.count || 1), 0) || 0
})

const netProfit = computed(() => {
  return (order.value?.analytics?.profit || 0) - totalPurchase.value
})

const formatAnalytics = (value) => {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(value)
}

// ── Можно ли печатать этикетку ─────────────────────────────
const canPrintLabel = computed(() => {
  if (!order.value) return false
  const printableStatuses = ['awaiting_deliver', 'awaiting_packaging', 'PROCESSING', 'READY_TO_SHIP', 'DELIVERY']
  return printableStatuses.includes(order.value.market_status) && order.value.market_type !== 'wb' || order.value.market_type === 'yandex'
})

// ── Печать этикетки ────────────────────────────────────────
const printLabel = async () => {
  if (!order.value || !canPrintLabel.value) return

  isPrinting.value = true

  try {
    const payload = {
      orders: [{
        order_id: order.value.order_id,
        status: order.value.market_status,
        cabinet_id: order.value.cabinet?._id || order.value.cabinet_id,
      }]
    }

    console.log('📤 Sending print request:', JSON.stringify(payload, null, 2))

    const response = await api.post('/orders/labels/print', payload)
    const data = response.data

    console.log('📥 Print response:', data)

    if (data.labels) {
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

      const successCount = data.results?.filter((r) => r.status === 'ready').length || 0
      if (successCount > 0) {
        notification.add(`Этикетка для заказа ${order.value.order_id} напечатана`, 'success')
      }
    } else {
      const errors = data.results?.filter((r) => r.status === 'error') || []
      if (errors.length > 0) {
        notification.add(`${errors[0]?.message || 'Ошибка печати этикетки'}`, 'error')
      }
    }
  } catch (error) {
    console.error('Print error:', error)
    if (error.response?.data?.detail) {
      notification.add(`${error.response.data.detail}`, 'error')
    } else {
      notification.add('Ошибка при печати этикетки', 'error')
    }
  } finally {
    isPrinting.value = false
  }
}

// ── Статус товара ───────────────────────────────────────────
const getItemColor = (status) => {
  if (!status) return '#6b7280'
  const statusObj = statuses.value.find((s) => s.code === status || s.name === status)
  return statusObj?.color || '#6b7280'
}

const toggleDropdown = (index) => {
  showStatusDropdown.value[index] = !showStatusDropdown.value[index]
}

const changeItemStatus = async (item, newStatus, index) => {
  if (!order.value) return

  updatingStatus.value = true
  try {
    const payload = {
      items: [{
        item_id: item._id,
        status: newStatus,
      }]
    }

    const result = await ordersStore.handleOrder(order.value._id, payload)
    if (result.success) {
      item.status = newStatus
      notification.add(`Статус товара ${item.article} обновлён на "${newStatus}"`, 'success')
      loadHistory()
    } else {
      notification.add('Ошибка при обновлении статуса', 'error')
    }
  } catch (err) {
    notification.add('Ошибка при обновлении статуса', 'error')
  } finally {
    updatingStatus.value = false
    showStatusDropdown.value[index] = false
  }
}

// ── Загрузка заказа ────────────────────────────────────────
const loadOrder = async () => {
  const id = route.params.id
  if (!id) {
    error.value = 'ID заказа не указан'
    loading.value = false
    return
  }

  loading.value = true
  error.value = null

  try {
    const data = await ordersStore.fetchOrderById(id)
    if (data) {
      order.value = data
    } else {
      error.value = 'Заказ не найден'
    }
  } catch (err) {
    console.error('Ошибка загрузки заказа:', err)
    error.value = 'Не удалось загрузить заказ'
  } finally {
    loading.value = false
  }
}

// ── Загрузка истории ───────────────────────────────────────
const loadHistory = async () => {
  const id = route.params.id
  if (!id) return

  historyLoading.value = true
  historyError.value = null

  try {
    const response = await api.get(`/logs/history/${id}`, {
      params: { limit: 100 }
    })
    history.value = response.data
  } catch (err) {
    console.error('Ошибка загрузки истории:', err)
    historyError.value = 'Не удалось загрузить историю заказа'
  } finally {
    historyLoading.value = false
  }
}

// ── Хелперы истории ────────────────────────────────────────
const eventLabels = {
  created: 'Создан',
  status_changed: 'Изменён статус',
  market_status_changed: 'Статус МП',
  process_status_changed: 'Статус обработки',
  item_status_changed: 'Статус товара',
  updated: 'Обновлён',
  deleted: 'Удалён',
  cancelled: 'Отменён',
  comment_added: 'Комментарий',
  label_printed: 'Этикетка напечатана',
  sync: 'Синхронизация',
}

const eventIcons = {
  created: 'add_circle',
  status_changed: 'swap_horiz',
  market_status_changed: 'storefront',
  process_status_changed: 'flag',
  item_status_changed: 'inventory',
  updated: 'edit',
  deleted: 'delete',
  cancelled: 'block',
  comment_added: 'comment',
  label_printed: 'barcode',
  sync: 'sync',
}

const eventColors = {
  created: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  status_changed: 'bg-blue-100 text-blue-700 border-blue-200',
  market_status_changed: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  process_status_changed: 'bg-violet-100 text-violet-700 border-violet-200',
  item_status_changed: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  updated: 'bg-amber-100 text-amber-700 border-amber-200',
  deleted: 'bg-rose-100 text-rose-700 border-rose-200',
  cancelled: 'bg-rose-100 text-rose-700 border-rose-200',
  comment_added: 'bg-gray-100 text-gray-700 border-gray-200',
  label_printed: 'bg-purple-100 text-purple-700 border-purple-200',
  sync: 'bg-sky-100 text-sky-700 border-sky-200',
}

const sourceLabels = {
  poller: 'Поллер',
  user: 'Пользователь',
  system: 'Система',
  api: 'API',
  webhook: 'Webhook',
  sync: 'Синхронизация',
}

const getEventLabel = (type) => eventLabels[type] || type || 'Событие'
const getEventIcon = (type) => eventIcons[type] || 'info'
const getEventColor = (type) => eventColors[type] || 'bg-gray-100 text-gray-700 border-gray-200'
const getSourceLabel = (source) => sourceLabels[source] || source || '—'

// Расшифровка ключей changes в человекочитаемый вид
const changeLabels = {
  order_created: 'Заказ создан',
  market_status: 'Статус МП',
  process_status: 'Статус обработки',
  status: 'Статус',
  comment: 'Комментарий',
  my_send_date: 'Наша отгрузка',
  send_date: 'Отгрузка',
  cancellation_type: 'Тип отмены',
  is_loaded: 'Загружен',
}

const getChangeLabel = (key) => changeLabels[key] || key

const formatChangeValue = (value) => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
  if (typeof value === 'object') return `<div class="flex items-center gap-2 text-xs flex-wrap"><span class="inline-flex items-center px-2 py-0.5 rounded-md bg-white text-gray-500 border border-gray-200 line-through" title="Было: ${value?.old}">${value?.old}</span><span class="material-symbols-outlined text-sm text-gray-400">arrow_forward</span><span class="inline-flex items-center px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 font-medium" title="Стало: ${value?.new}">${formatDate(value?.new)}</span></div>`
  return String(value)
}

const toggleChangesExpand = (logId) => {
  expandedChanges.value[logId] = !expandedChanges.value[logId]
}

const hasChanges = (log) => {
  return log.changes && Object.keys(log.changes).length > 0
}

const changeEntries = (log) => {
  if (!log.changes) return []
  return Object.entries(log.changes)
}

// ── Следим за изменением ID в URL ─────────────────────────
watch(
  () => route.params.id,
  (newId) => {
    if (newId) {
      loadOrder(newId)
      loadHistory()
    }
  },
  { immediate: true }
)

// ── Жизненный цикл ──────────────────────────────────────────
onMounted(async () => {
  if (!refStore.statuses.length) await refStore.fetchAll('statuses')
  statuses.value = sortByIndex(refStore.statuses)
  await loadOrder()
  await loadHistory()

  window.addEventListener('click', (e) => {
    if (!e.target.closest('.status-dropdown') && !e.target.closest('.status-button')) {
      showStatusDropdown.value = {}
    }
  })
})
</script>

<template>
  <div class="space-y-5">
    <!-- Загрузка -->
    <div v-if="loading" class="flex flex-col items-center justify-center gap-3 py-24">
      <span class="h-10 w-10 animate-spin rounded-full border-[3px] border-slate-200 border-t-slate-900"></span>
      <span class="text-sm text-slate-500">Загрузка заказа…</span>
    </div>

    <!-- Ошибка -->
    <div
      v-else-if="error"
      class="panel border-rose-200 bg-rose-50 p-10 text-center"
    >
      <span class="material-symbols-outlined mb-3 block text-4xl text-rose-400">error</span>
      <p class="text-base font-medium text-rose-700">{{ error }}</p>
      <router-link
        to="/orders"
        class="mt-3 inline-block text-sm text-rose-700 underline-offset-2 hover:underline"
      >
        ← Вернуться назад
      </router-link>
    </div>

    <!-- Контент -->
    <template v-else-if="order">
      <!-- ─── Верхний блок: ID + статусы + кнопки ─── -->
      <div class="panel p-5">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="flex flex-wrap items-center gap-2.5">
            <div class="flex items-center gap-1.5">
              <button
                @click="copy(order.order_id)"
                class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                title="Копировать номер заказа"
              >
                <span class="material-symbols-outlined text-[21px]">content_copy</span>
              </button>
              <span class="text-[22px] font-semibold tracking-tight text-slate-900">
                {{ order.order_id }}
              </span>
            </div>

            <span
              class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium"
              :class="getMarketColor(order.market_type).chip"
              :title="`Кабинет: ${order.cabinet_name}`"
            >
              <span
                class="h-2 w-2 rounded-full"
                :style="{ backgroundColor: getMarketColor(order.market_type).hex }"
              ></span>
              {{ order.cabinet_name }}
            </span>

            <span
              class="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-600"
              :title="`Маркетплейс: ${order.market_type}`"
            >
              <span class="material-symbols-outlined text-[18px]">storefront</span>
              {{ order.market_type }}
            </span>

            <span
              v-if="order.cabinet?.model"
              class="inline-flex items-center rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-600"
              :title="`Модель: ${order.cabinet.model}`"
            >
              {{ order.cabinet.model }}
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button
              v-if="canPrintLabel"
              @click="printLabel"
              :disabled="isPrinting"
              class="btn-primary h-10 px-4"
              title="Распечатать этикетку"
            >
              <span class="material-symbols-outlined text-[19px]" v-if="!isPrinting">barcode</span>
              <span
                v-else
                class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
              ></span>
              {{ isPrinting ? 'Печать…' : 'Этикетка' }}
            </button>

            <button
              @click="app.openHandleOrderModal(order)"
              class="inline-flex h-10 items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 text-sm font-medium text-indigo-700 transition-all hover:bg-indigo-100 active:scale-95"
              title="Открыть окно обработки заказа"
            >
              <span class="material-symbols-outlined text-[19px]">edit_note</span>
              Редактировать
            </button>

            <router-link
              to="/orders"
              class="btn-secondary h-10"
              title="Вернуться к списку заказов"
            >
              <span class="material-symbols-outlined text-[19px]">arrow_back</span>
              Назад
            </router-link>
          </div>
        </div>

        <!-- Статусы -->
        <div class="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
          <span
            class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-semibold"
            :class="[
              getStatusBadgeClasses(order.market_status).bg,
              getStatusBadgeClasses(order.market_status).text,
              getStatusBadgeClasses(order.market_status).border || 'border-transparent',
            ]"
            :title="`Статус МП: ${getStatusDescription(order.market_status)}`"
          >
            <span class="material-symbols-outlined text-[18px]">storefront</span>
            {{ getRussianStatus(order.market_status) }}
          </span>

          <span
            v-if="order.substatus"
            class="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-600"
            :title="`Детализированный статус МП: ${order.substatus}`"
          >
            {{ getSubstatusLabel(order.substatus) }}
          </span>

          <span
            class="inline-flex items-center rounded-lg px-3 py-1.5 text-sm font-semibold"
            :class="getProcessStatus(order.process_status).color"
            :title="`Статус обработки: ${getProcessStatus(order.process_status).label}`"
          >
            {{ getProcessStatus(order.process_status).label }}
          </span>

          <span
            v-if="order.cancellation_type"
            class="inline-flex items-center gap-1.5 rounded-lg bg-rose-50 px-3 py-1.5 text-sm font-semibold text-rose-600"
            :title="`Инициатор отмены: ${order.cancellation_type === 'seller' ? 'Продавец' : 'Клиент'}`"
          >
            <span class="material-symbols-outlined text-[18px]">block</span>
            {{ order.cancellation_type === 'seller' ? 'Отмена (мы)' : 'Отмена (клиент)' }}
          </span>

          <span
            v-if="order.is_loaded !== undefined"
            class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium"
            :class="
              order.is_loaded ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
            "
            :title="order.is_loaded ? 'Заказ загружен в систему' : 'Заказ ещё не загружен'"
          >
            <span class="material-symbols-outlined text-[18px]">cloud_done</span>
            {{ order.is_loaded ? 'Загружен' : 'Не загружен' }}
          </span>
        </div>
      </div>

      <!-- ─── Основная информация ─── -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <!-- Информация о заказе -->
        <div class="card">
          <div class="mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-blue-500">info</span>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Информация о заказе</h3>
          </div>
          <div class="space-y-3 text-[15px]">
            <div class="flex justify-between border-b border-gray-100 pb-3">
              <span class="text-gray-500">Создан</span>
              <span class="font-medium text-gray-800" :title="`Дата создания: ${formatDate(order.order_date)}`">
                {{ formatDate(order.order_date) }}
              </span>
            </div>
            <div class="flex justify-between border-b border-gray-100 pb-3">
              <span class="text-gray-500">Отгрузка</span>
              <span class="font-medium text-gray-800" :title="`Дата отгрузки: ${formatDate(order.send_date, true)}`">
                {{ formatDate(order.send_date, true) }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Наша отгрузка</span>
              <span class="font-medium text-gray-800" :title="`Наша дата отгрузки: ${formatDate(order.my_send_date, true) || 'не указана'}`">
                {{ formatDate(order.my_send_date, true) || '—' }}
              </span>
            </div>
            <div v-if="order.order_number" class="flex justify-between">
              <span class="text-gray-500">Номер заказа</span>
              <span class="font-medium text-gray-800">{{ order.order_number }}</span>
            </div>
            <div v-if="order.delivery_schema" class="flex justify-between">
              <span class="text-gray-500">Схема доставки</span>
              <span class="font-medium text-gray-800 uppercase">{{ order.delivery_schema }}</span>
            </div>
            <div v-if="order.tracking_number" class="flex justify-between">
              <span class="text-gray-500">Трек-номер</span>
              <span class="font-medium text-gray-800 font-mono">{{ order.tracking_number }}</span>
            </div>
            <div v-if="order.scanit" class="flex justify-between">
              <span class="text-gray-500">Штрихкод отправления</span>
              <span class="font-medium text-gray-800 font-mono">{{ order.scanit }}</span>
            </div>
          </div>
        </div>

        <!-- Информация о кабинете -->
        <div class="card">
          <div class="mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-blue-500">business_center</span>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Кабинет</h3>
          </div>
          <div class="space-y-3 text-[15px]">
            <div class="flex justify-between border-b border-gray-100 pb-3">
              <span class="text-gray-500">Название</span>
              <span class="font-medium text-gray-800">{{ order.cabinet_name }}</span>
            </div>
            <div v-if="order.cabinet?.market_slug" class="flex justify-between border-b border-gray-100 pb-3">
              <span class="text-gray-500">Маркетплейс</span>
              <span class="font-medium text-gray-800">{{ order.cabinet.market_slug }}</span>
            </div>
            <div v-if="order.cabinet?.model" class="flex justify-between pb-3">
              <span class="text-gray-500">Модель работы</span>
              <span class="font-medium text-gray-800">{{ order.cabinet.model }}</span>
            </div>
          </div>
        </div>

        <!-- Итоговая сумма -->
        <div class="card">
          <div class="mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-emerald-500">payments</span>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Итого</h3>
          </div>
          <div class="space-y-3 text-[15px]">
            <div class="flex justify-between border-b border-gray-100 pb-3">
              <span class="text-gray-500">Сумма заказа</span>
              <span class="font-medium text-black">{{ formatPrice(order.price) }}</span>
            </div>
            <div class="flex justify-between border-b border-gray-100 pb-3">
              <span class="text-gray-500">Сумма закупок</span>
              <span class="font-medium text-emerald-600">{{ formatPrice(totalPurchase) }}</span>
            </div>
            <div class="flex justify-between pb-3">
              <span class="text-gray-500">Количество позиций</span>
              <span class="font-medium text-gray-800">{{ order.order_count || 0 }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── Комментарий ─── -->
      <div v-if="order.comment" class="panel border-amber-200/70 bg-amber-50/60 p-5">
        <div class="mb-2 flex items-center gap-2">
          <span class="material-symbols-outlined text-amber-500">comment</span>
          <h3 class="text-xs font-semibold uppercase tracking-wider text-amber-700/80">Комментарий</h3>
        </div>
        <p class="text-[15px] leading-snug text-amber-900">{{ order.comment }}</p>
      </div>

      <!-- ─── Товары ─── -->
      <div class="panel overflow-visible p-0">
        <div class="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-blue-500">inventory_2</span>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Товары в заказе</h3>
          </div>
          <span class="text-[13px] font-medium text-slate-500">{{ order.items?.length || 0 }} позиций</span>
        </div>

        <div v-if="order.items?.length" class="divide-y divide-slate-100">
          <div
            v-for="(item, index) in order.items"
            :key="item._id"
            class="px-5 py-4 transition-colors hover:bg-slate-50/70"
          >
            <div class="flex flex-col sm:flex-row sm:items-center gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-2">
                  <button
                    @click="copy(item.article)"
                    class="text-gray-400 hover:text-blue-600 transition-colors flex items-center justify-center shrink-0 cursor-pointer"
                    title="Копировать артикул"
                  >
                    <span class="material-symbols-outlined text-sm">content_copy</span>
                  </button>
                  <span class="font-mono text-[15px] font-semibold text-slate-800">{{ item.article }}</span>
                  <span class="hidden text-slate-300 sm:inline">·</span>
                  <span class="truncate text-sm text-slate-600" :title="item.name">
                    {{ item.name }}
                  </span>
                </div>
                <div class="mt-2 flex flex-wrap items-center gap-3 text-[14px]">
                  <span class="text-slate-500" :title="`Количество: ${item.count} шт`">
                    {{ item.count }} шт
                  </span>
                  <span class="text-slate-300">|</span>
                  <span
                    class="font-semibold text-slate-800"
                    :title="`Цена за все: ${formatPrice(item.price)}${item.count > 1 ? `\nЦена за 1 шт: ${formatPrice(item.price / item.count)}` : ''}`"
                  >
                    {{ formatPrice(item.price) }}
                  </span>
                  <span class="text-slate-300">|</span>
                  <span
                    v-if="item.purchase"
                    class="font-semibold text-emerald-600"
                    :title="`Закуп за все: ${formatPrice(item.purchase)}${item.count > 1 ? `\nЗакуп за 1 шт: ${formatPrice(item.purchase / item.count)}` : ''}`"
                  >
                    {{ formatPrice(item.purchase) }}
                  </span>
                  <span v-else class="text-slate-400">закуп не указан</span>
                  <span class="text-slate-300">|</span>

                  <span
                    v-if="item.provider"
                    class="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[12.5px] font-medium text-indigo-700"
                    :title="`Поставщик: ${item.provider}`"
                  >
                    <span class="material-symbols-outlined text-[14px]">business</span>
                    {{ item.provider }}
                  </span>
                  <span v-else class="text-slate-400">поставщик не указан</span>

                  <span class="text-slate-300">|</span>

                  <div class="relative flex items-center rounded-lg border border-slate-200 bg-white">
                    <span
                      :style="{ backgroundColor: getItemColor(item.status) }"
                      class="flex h-8 items-center rounded-l-[7px] px-3 text-[13px] font-medium text-white"
                      :title="`Текущий статус: ${item.status || '—'}`"
                    >
                      {{ item.status || '—' }}
                    </span>
                    <button
                      @click.stop="toggleDropdown(index)"
                      :style="{ backgroundColor: getItemColor(item.status) }"
                      class="status-button flex h-8 w-7 items-center justify-center rounded-r-[7px] text-white"
                      title="Изменить статус товара"
                    >
                      <span class="material-symbols-outlined text-[18px]">keyboard_arrow_down</span>
                    </button>

                    <Transition name="slide-up">
                      <div
                        v-if="showStatusDropdown[index]"
                        class="status-dropdown absolute right-0 top-full z-30 mt-1.5 min-w-[170px] rounded-xl border border-slate-200 bg-white py-1.5 shadow-[0_16px_40px_-12px_rgba(15,23,42,0.28)]"
                      >
                        <button
                          v-for="status in statuses"
                          :key="status._id"
                          @click="changeItemStatus(item, status.name, index)"
                          class="flex w-full items-center gap-2.5 whitespace-nowrap px-3.5 py-2 text-sm transition-colors hover:bg-slate-50"
                          :disabled="updatingStatus"
                          :title="`Установить статус: ${status.name}`"
                        >
                          <div
                            class="h-3.5 w-3.5 shrink-0 rounded-full"
                            :style="{ backgroundColor: status?.color || '#6b7280' }"
                          ></div>
                          <span class="text-slate-700">{{ status?.name }}</span>
                        </button>
                      </div>
                    </Transition>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="px-5 py-10 text-center text-slate-500">
          <span class="material-symbols-outlined mb-2 block text-3xl text-slate-300">inventory_2</span>
          Нет товаров в заказе
        </div>
      </div>

      <!-- ─── Аналитика ─── -->
      <div class="panel p-5">
        <div class="mb-4 flex items-center gap-2">
          <span class="material-symbols-outlined text-blue-500">bar_chart</span>
          <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Финансовая аналитика</h3>
        </div>

        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3 text-center">
            <p class="text-[12.5px] text-slate-500">Комиссия МП</p>
            <p class="mt-1 text-[15px] font-semibold text-slate-800">{{ formatAnalytics(order.analytics?.commission_market_total) }}</p>
          </div>
          <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3 text-center">
            <p class="text-[12.5px] text-slate-500">Комиссия оплаты</p>
            <p class="mt-1 text-[15px] font-semibold text-slate-800">{{ formatAnalytics(order.analytics?.commission_payment_total) }}</p>
          </div>
          <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3 text-center">
            <p class="text-[12.5px] text-slate-500">Последняя миля</p>
            <p class="mt-1 text-[15px] font-semibold text-slate-800">{{ formatAnalytics(order.analytics?.last_mile_total) }}</p>
          </div>
          <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3 text-center">
            <p class="text-[12.5px] text-slate-500">Логистика</p>
            <p class="mt-1 text-[15px] font-semibold text-slate-800">{{ formatAnalytics(order.analytics?.logistics_total) }}</p>
          </div>
          <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3 text-center">
            <p class="text-[12.5px] text-slate-500">Обработка</p>
            <p class="mt-1 text-[15px] font-semibold text-slate-800">{{ formatAnalytics(order.analytics?.processing_fixed) }}</p>
          </div>
          <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3 text-center">
            <p class="text-[12.5px] text-slate-500">Штраф</p>
            <p class="mt-1 text-[15px] font-semibold text-rose-600">{{ formatAnalytics(order.analytics?.penalty) }}</p>
          </div>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3 border-t border-slate-200/70 pt-4 sm:grid-cols-4">
          <div class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-center">
            <p class="text-[13px] font-medium text-slate-500">Итого расходов</p>
            <p class="mt-1 text-xl font-bold text-rose-600">{{ formatAnalytics(order.analytics?.total_expenses) }}</p>
          </div>
          <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
            <p class="text-[13px] font-medium text-slate-500">Закупка</p>
            <p class="mt-1 text-xl font-bold text-emerald-600">{{ formatAnalytics(totalPurchase) }}</p>
          </div>
          <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
            <p class="text-[13px] font-medium text-slate-500">Прибыль</p>
            <p class="mt-1 text-xl font-bold text-emerald-600">{{ formatAnalytics(order.analytics?.profit) }}</p>
          </div>
          <div class="rounded-xl border border-violet-200 bg-violet-50 p-4 text-center">
            <p class="text-[13px] font-medium text-slate-500">Чистая прибыль</p>
            <p class="mt-1 text-xl font-bold text-violet-600">{{ formatAnalytics(netProfit) }}</p>
          </div>
        </div>
        <p class="mt-3 text-center text-xs text-slate-400">* чистая прибыль = прибыль − закупка товаров</p>
      </div>

      <!-- ─── ИСТОРИЯ ЗАКАЗА ─── -->
      <div class="panel p-5">
        <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-blue-500">history</span>
            <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">История заказа</h3>
            <span
              v-if="history.total"
              class="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold"
              title="Всего событий в истории"
            >
              {{ history.total }}
            </span>
          </div>

          <button
            @click="loadHistory"
            :disabled="historyLoading"
            class="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
            title="Обновить историю заказа"
          >
            <span
              class="material-symbols-outlined text-[16px]"
              :class="{ 'animate-spin': historyLoading }"
            >
              refresh
            </span>
            Обновить
          </button>
        </div>

        <!-- Загрузка истории -->
        <div v-if="historyLoading && !history.items?.length" class="flex items-center justify-center py-10">
          <div class="flex flex-col items-center gap-2">
            <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-xs text-gray-500">Загрузка истории...</span>
          </div>
        </div>

        <!-- Ошибка истории -->
        <div v-else-if="historyError" class="bg-rose-50 border border-rose-100 rounded-xl px-4 py-3 text-center">
          <p class="text-sm text-rose-600">{{ historyError }}</p>
        </div>

        <!-- Пустая история -->
        <div v-else-if="!history.items?.length" class="text-center py-10">
          <span class="material-symbols-outlined text-4xl text-gray-300 block mb-2">history_toggle_off</span>
          <p class="text-sm text-gray-500">История пуста</p>
          <p class="text-xs text-gray-400 mt-1">События по этому заказу ещё не зафиксированы</p>
        </div>

        <!-- Таймлайн -->
        <div v-else class="relative">
          <!-- Вертикальная линия -->
          <div class="absolute bottom-3 left-[19px] top-3 w-0.5 bg-linear-to-b from-slate-200 via-slate-100 to-transparent"></div>

          <div class="space-y-3">
            <div
              v-for="(log, idx) in history.items"
              :key="log._id"
              class="relative pl-12"
            >
              <!-- Иконка события -->
              <div
                class="absolute left-0 top-1 w-10 h-10 rounded-full border-2 flex items-center justify-center bg-white z-10"
                :class="getEventColor(log.event_type)"
                :title="`Событие: ${getEventLabel(log.event_type)}`"
              >
                <span class="material-symbols-outlined text-lg">{{ getEventIcon(log.event_type) }}</span>
              </div>

              <div class="rounded-xl border border-slate-200/70 bg-slate-50/70 p-4 transition-colors hover:bg-white">
                <!-- Верхняя строка: событие + источник + время -->
                <div class="flex items-center justify-between gap-2 flex-wrap">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span
                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border"
                      :class="getEventColor(log.event_type)"
                      :title="`Тип события: ${getEventLabel(log.event_type)}`"
                    >
                      {{ getEventLabel(log.event_type) }}
                    </span>

                    <span
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-white text-gray-600 border border-gray-200"
                      :title="`Источник события: ${getSourceLabel(log.event_source)}`"
                    >
                      <span class="material-symbols-outlined text-xs">
                        {{ log.event_source === 'poller' ? 'sync' : log.event_source === 'user' ? 'person' : 'settings' }}
                      </span>
                      {{ getSourceLabel(log.event_source) }}
                    </span>

                    <span
                      v-if="log.user_email"
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-white text-gray-600 border border-gray-200"
                      :title="`Пользователь: ${log.user_email}`"
                    >
                      <span class="material-symbols-outlined text-xs">person</span>
                      {{ log.user_email }}
                    </span>
                  </div>

                  <span
                    class="whitespace-nowrap text-[12.5px] text-slate-400"
                    :title="`Дата события: ${log.created_at_iso}`"
                  >
                    {{ formatDate(log.created_at_iso) }}
                  </span>
                </div>

                <!-- Комментарий -->
                <p v-if="log.comment" class="mt-2 text-sm leading-snug text-slate-700">
                  {{ log.comment }}
                </p>

                <!-- Переход статуса -->
                <div
                  v-if="log.old_status || log.new_status"
                  class="flex items-center gap-2 mt-2 text-xs flex-wrap"
                >
                  <span
                    v-if="log.old_status"
                    class="inline-flex items-center px-2 py-0.5 rounded-md bg-white text-gray-500 border border-gray-200 line-through"
                    :title="`Было: ${log.old_status}`"
                  >
                    {{ log.old_status }}
                  </span>
                  <span v-if="log.old_status && log.new_status" class="material-symbols-outlined text-sm text-gray-400">arrow_forward</span>
                  <span
                    v-if="log.new_status"
                    class="inline-flex items-center px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 font-medium"
                    :title="`Стало: ${log.new_status}`"
                  >
                    {{ log.new_status }}
                  </span>
                </div>

                <!-- Изменения (changes) -->
                <div v-if="hasChanges(log)" class="mt-2">
                  <button
                    @click="toggleChangesExpand(log._id)"
                    class="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-blue-600 transition-colors cursor-pointer"
                    title="Показать или скрыть детали изменений"
                  >
                    <span class="material-symbols-outlined text-sm transition-transform" :class="{ 'rotate-90': expandedChanges[log._id] }">
                      chevron_right
                    </span>
                    {{ expandedChanges[log._id] ? 'Скрыть' : 'Показать' }} детали ({{ changeEntries(log).length }})
                  </button>

                  <Transition name="expand">
                    <div
                      v-if="expandedChanges[log._id]"
                      class="mt-2 bg-white rounded-lg border border-gray-200 overflow-hidden"
                    >
                      <div
                        v-for="([key, value], i) in changeEntries(log)"
                        :key="key"
                        class="flex items-start justify-between gap-3 px-3 py-2 text-xs"
                        :class="{ 'border-t border-gray-100': i > 0 }"
                      >
                        <span class="text-gray-500 font-medium shrink-0">{{ getChangeLabel(key) }}</span>
                        <span class="text-gray-800 text-right break-all" v-html="formatChangeValue(value)"></span>
                      </div>
                    </div>
                  </Transition>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.2s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(8px);
  opacity: 0;
}

.slide-up-enter-to,
.slide-up-leave-from {
  transform: translateY(0);
  opacity: 1;
}

/* Анимация раскрытия блока изменений */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  margin-top: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 400px;
}
</style>