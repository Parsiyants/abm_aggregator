<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useFunction } from '@/composables/function'
import { useReferenceStore } from '@/stores/references'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notifications'

const notify = useNotificationStore()
const refStore = useReferenceStore()
const { formatDate, formatPrice, getMarketColor } = useFunction()

// ── State ─────────────────────────────────────────────────
const activeTab = ref('polling') // 'polling' | 'sync'
const loading = ref(false)

const pollingLogs = ref({ items: [], total: 0 })
const syncLogs = ref({ items: [], total: 0 })

const stats = ref(null)

// ── Фильтры ───────────────────────────────────────────────
const pollingFilters = ref({
  market_type: null,
  status: null,
  cabinet_id: null,
})

const syncFilters = ref({
  market_type: null,
  sync_type: null,
  status: null,
  cabinet_id: null,
})

// ── Пагинация ─────────────────────────────────────────────
const pagination = ref({
  page: 1,
  limit: 50,
})

const totalPages = computed(() => {
  const total = activeTab.value === 'polling'
    ? pollingLogs.value.total
    : syncLogs.value.total
  return Math.ceil(total / pagination.value.limit) || 1
})

// ── Опции фильтров ────────────────────────────────────────
const marketOptions = computed(() => [
  { value: null, label: 'Все маркетплейсы' },
  ...refStore.marketplaces.map((m) => ({ value: m.slug, label: m.name })),
])

// Кабинеты: фильтруем по выбранному маркетплейсу активной вкладки
const cabinetOptions = computed(() => {
  const market =
    activeTab.value === 'polling'
      ? pollingFilters.value.market_type
      : syncFilters.value.market_type

  const list = market
    ? refStore.cabinets.filter((c) => c.market_slug === market)
    : refStore.cabinets

  return [
    { value: null, label: 'Все кабинеты' },
    ...list.map((c) => ({ value: c._id, label: c.name })),
  ]
})

const statusOptions = [
  { value: null, label: 'Все статусы' },
  { value: 'success', label: 'Успех' },
  { value: 'error', label: 'Ошибка' },
  { value: 'pending', label: 'В процессе' },
  { value: 'partial', label: 'Частично' },
]

const syncTypeOptions = [
  { value: null, label: 'Все типы' },
  { value: 'prices', label: 'Цены' },
  { value: 'stocks', label: 'Остатки' },
  { value: 'orders', label: 'Заказы' },
  { value: 'full', label: 'Полная' },
]

// ── Загрузка логов ────────────────────────────────────────
const loadPollingLogs = async () => {
  loading.value = true
  try {
    const params = {
      limit: pagination.value.limit,
      skip: (pagination.value.page - 1) * pagination.value.limit,
    }

    if (pollingFilters.value.market_type) params.market_type = pollingFilters.value.market_type
    if (pollingFilters.value.status) params.status = pollingFilters.value.status
    if (pollingFilters.value.cabinet_id) params.cabinet_id = pollingFilters.value.cabinet_id

    const response = await api.get('/logs/polling', { params })
    pollingLogs.value = response.data
  } catch (error) {
    console.error('Ошибка загрузки логов поллинга:', error)
    notify.add('Ошибка загрузки логов', 'error')
  } finally {
    loading.value = false
  }
}

const loadSyncLogs = async () => {
  loading.value = true
  try {
    const params = {
      limit: pagination.value.limit,
      skip: (pagination.value.page - 1) * pagination.value.limit,
    }

    if (syncFilters.value.market_type) params.market_type = syncFilters.value.market_type
    if (syncFilters.value.sync_type) params.sync_type = syncFilters.value.sync_type
    if (syncFilters.value.status) params.status = syncFilters.value.status
    if (syncFilters.value.cabinet_id) params.cabinet_id = syncFilters.value.cabinet_id

    const response = await api.get('/logs/sync', { params })
    syncLogs.value = response.data
  } catch (error) {
    console.error('Ошибка загрузки логов синхронизации:', error)
    notify.add('Ошибка загрузки логов', 'error')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const response = await api.get('/logs/stats?days=7')
    stats.value = response.data
  } catch (error) {
    console.error('Ошибка загрузки статистики:', error)
  }
}

// ── Переключение вкладок ──────────────────────────────────
const switchTab = (tab) => {
  activeTab.value = tab
  pagination.value.page = 1
  if (tab === 'polling') loadPollingLogs()
  else loadSyncLogs()
}

// ── Применение фильтров ───────────────────────────────────
const applyFilters = () => {
  pagination.value.page = 1
  if (activeTab.value === 'polling') loadPollingLogs()
  else loadSyncLogs()
}

const resetFilters = () => {
  if (activeTab.value === 'polling') {
    pollingFilters.value = { market_type: null, status: null, cabinet_id: null }
  } else {
    syncFilters.value = { market_type: null, sync_type: null, status: null, cabinet_id: null }
  }
  pagination.value.page = 1
  applyFilters()
}

// ── Смена страницы ────────────────────────────────────────
const changePage = (page) => {
  if (page < 1 || page > totalPages.value) return
  pagination.value.page = page
  if (activeTab.value === 'polling') loadPollingLogs()
  else loadSyncLogs()
}

// ── Удаление лога ─────────────────────────────────────────
const deleteLog = async (log) => {
  if (!confirm(`Удалить лог от ${formatDate(log.started_at_iso)}?`)) return

  try {
    const endpoint = activeTab.value === 'polling'
      ? `/logs/polling/${log._id}`
      : `/logs/sync/${log._id}`

    await api.delete(endpoint)
    notify.add('Лог удалён', 'success')

    if (activeTab.value === 'polling') loadPollingLogs()
    else loadSyncLogs()
  } catch (error) {
    notify.add('Ошибка удаления лога', 'error')
  }
}

// ── Очистка старых логов ──────────────────────────────────
const clearOldLogs = async () => {
  if (!confirm('Удалить все логи старше 30 дней?')) return

  try {
    const endpoint = activeTab.value === 'polling'
      ? '/logs/polling?older_than_days=30'
      : '/logs/sync?older_than_days=30'

    const response = await api.delete(endpoint)
    notify.add(`Удалено ${response.data.deleted_count} логов`, 'success')

    if (activeTab.value === 'polling') loadPollingLogs()
    else loadSyncLogs()
  } catch (error) {
    notify.add('Ошибка очистки логов', 'error')
  }
}

// ── Форматирование длительности ──────────────────────────
const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '—'
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}мс`
  if (seconds < 60) return `${seconds.toFixed(1)}с`
  return `${Math.floor(seconds / 60)}м ${(seconds % 60).toFixed(0)}с`
}

// ── Цвет статуса ──────────────────────────────────────────
const getStatusColor = (status) => {
  const colors = {
    success: 'bg-emerald-100 text-emerald-700',
    error: 'bg-rose-100 text-rose-700',
    pending: 'bg-amber-100 text-amber-700',
    partial: 'bg-orange-100 text-orange-700',
  }
  return colors[status] || 'bg-slate-100 text-slate-700'
}

const getStatusLabel = (status) => {
  const labels = {
    success: 'Успех',
    error: 'Ошибка',
    pending: 'В процессе',
    partial: 'Частично',
  }
  return labels[status] || status
}

// ── Словари для синхронизации ─────────────────────────────
const syncTypeLabels = {
  full: 'Полная',
  prices: 'Цены',
  stocks: 'Остатки',
  orders: 'Заказы',
}

const getSyncTypeLabel = (type) => syncTypeLabels[type] || type

const getSyncTypeColor = (type) => {
  const colors = {
    full: 'bg-indigo-100 text-indigo-700',
    prices: 'bg-amber-100 text-amber-700',
    stocks: 'bg-cyan-100 text-cyan-700',
    orders: 'bg-purple-100 text-purple-700',
  }
  return colors[type] || 'bg-slate-100 text-slate-700'
}

const getSyncTypeIcon = (type) => {
  const icons = {
    full: 'sync',
    prices: 'sell',
    stocks: 'inventory',
    orders: 'shopping_cart',
  }
  return icons[type] || 'sync'
}

// ── Хелперы для детализации синхронизации WB ──────────────
// Ищем в log.items подзапись по типу (prices / stocks)
const getSyncItem = (log, type) => {
  if (!log.items?.length) return null
  return log.items.find((it) => it.sync_type === type) || null
}

// Для цен: обновлено / без изменений
const getPricesBreakdown = (log) => {
  const prices = getSyncItem(log, 'prices')
  if (!prices) {
    // fallback на плоские поля
    return {
      count: log.matched || 0,
      updated: log.prices_updated || 0,
      skipped: log.prices_skipped || 0,
      zeroed: 0,
    }
  }
  return {
    count: prices.count || 0,
    updated: prices.updated ?? log.prices_updated ?? 0,
    skipped: prices.skipped ?? log.prices_skipped ?? 0,
    zeroed: 0,
  }
}

// Для остатков: обновлено / обнулено / без изменений
const getStocksBreakdown = (log) => {
  const stocks = getSyncItem(log, 'stocks')
  if (!stocks) {
    return {
      count: log.matched || 0,
      updated: log.stocks_updated || 0,
      skipped: log.stocks_skipped || 0,
      zeroed: log.stocks_zeroed || 0,
    }
  }
  return {
    count: stocks.count || 0,
    updated: stocks.updated ?? log.stocks_updated ?? 0,
    skipped: stocks.skipped ?? log.stocks_skipped ?? 0,
    zeroed: stocks.zeroed ?? log.stocks_zeroed ?? 0,
  }
}

// Есть ли у лога новая (расширенная) структура — чтобы показывать блок «XML→WB»
const hasSourceStats = (log) => {
  return (
    typeof log.yml_items_total === 'number' ||
    typeof log.wb_goods_total === 'number' ||
    typeof log.matched === 'number'
  )
}

// ── Развёрнутые ошибки ────────────────────────────────────
const expandedErrors = ref({}) // { [logId]: true }

const toggleErrorExpand = (logId) => {
  expandedErrors.value[logId] = !expandedErrors.value[logId]
}

// Обрезаем длинную ошибку для свёрнутого вида
const truncateError = (msg, max = 160) => {
  if (!msg) return ''
  return msg.length > max ? msg.slice(0, max) + '…' : msg
}

// Достаём текст ошибки: приоритет у error_message, fallback — первый из errors[]
const getErrorMessage = (log) => {
  if (log.error_message) return log.error_message
  if (log.errors?.length) return log.errors[0].error
  return null
}

// ── Жизненный цикл ────────────────────────────────────────
onMounted(async () => {
  loadPollingLogs()
  loadStats()

  if (!refStore.marketplaces.length) await refStore.fetchAll('marketplaces')
  if (!refStore.cabinets.length) await refStore.fetchAll('cabinets')
})

// Сброс кабинета при смене маркетплейса
watch(
  () => pollingFilters.value.market_type,
  () => {
    pollingFilters.value.cabinet_id = null
  },
)

watch(
  () => syncFilters.value.market_type,
  () => {
    syncFilters.value.cabinet_id = null
  },
)

// Автоматическое обновление при смене страницы
watch(() => pagination.value.page, () => {
  if (activeTab.value === 'polling') loadPollingLogs()
  else loadSyncLogs()
})
</script>

<template>
  <div class="space-y-5">
    <!-- Заголовок -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Логи системы</h1>
        <p class="mt-1 text-sm text-slate-500">История операций поллера и синхронизации</p>
      </div>

      <button
        @click="clearOldLogs"
        class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
        title="Удалить все логи текущей вкладки старше 30 дней. Действие необратимо."
      >
        <span class="material-symbols-outlined text-[16px]">delete_sweep</span>
        Очистить старые
      </button>
    </div>

    <!-- Статистика (поллер + расширенные поля синхронизации, если бэк их отдаёт) -->
    <div v-if="stats" class="grid grid-cols-2 gap-3 md:grid-cols-5">
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Общее количество записей логов поллера за последние 7 дней"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Логов поллера (7 дн.)</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_logs || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Сколько раз поллер касался заказов: создал новые или обновил существующие"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Касаний заказов</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_touched || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-emerald-200/70 bg-emerald-50/60 p-4"
        title="Новые заказы, которых не было в базе до запуска поллера"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Создано заказов</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-emerald-600">
          {{ stats.total_created || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Заказы, у которых изменился статус или другие поля при поллинге"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Обновлено заказов</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_updated || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-rose-200/70 bg-rose-50/60 p-4"
        title="Количество логов поллера со статусом «Ошибка» за последние 7 дней"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Ошибок</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-rose-600">
          {{ stats.total_errors || 0 }}
        </p>
      </div>
    </div>

    <!-- Дополнительная статистика по синхронизации (появится, если бэк добавит поля в /logs/stats) -->
    <div
      v-if="stats && (stats.total_stocks_zeroed !== undefined || stats.total_prices_updated !== undefined)"
      class="grid grid-cols-2 gap-3 md:grid-cols-4"
    >
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Сколько цен было реально изменено за 7 дней"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Цен обновлено</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_prices_updated || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Сколько ненулевых остатков отправлено в WB за 7 дней"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Остатков обновлено</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_stocks_updated || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Сколько остатков обнулено (нет в XML или остаток меньше кратности) за 7 дней"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Остатков обнулено</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_stocks_zeroed || 0 }}
        </p>
      </div>
      <div
        class="rounded-xl border border-slate-200/70 bg-white p-4"
        title="Товары WB, для которых не нашлось соответствие в XML-фиде"
      >
        <p class="text-[12.5px] font-medium text-slate-500">Не сопоставлено</p>
        <p class="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
          {{ stats.total_unmatched_wb || 0 }}
        </p>
      </div>
    </div>

    <!-- Вкладки -->
    <div class="inline-flex items-center gap-1 rounded-xl bg-slate-100/80 p-1">
      <button
        @click="switchTab('polling')"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
        :class="
          activeTab === 'polling'
            ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
            : 'text-slate-500 hover:text-slate-900'
        "
        title="Логи периодического опроса маркетплейсов — сбор и обновление заказов"
      >
        <span class="material-symbols-outlined text-[18px]">sync</span>
        Логи поллера
      </button>
      <button
        @click="switchTab('sync')"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
        :class="
          activeTab === 'sync'
            ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
            : 'text-slate-500 hover:text-slate-900'
        "
        title="Логи синхронизации цен, остатков и других данных в маркетплейсы"
      >
        <span class="material-symbols-outlined text-[18px]">cloud_sync</span>
        Логи синхронизации
      </button>
    </div>

    <!-- Фильтры: Polling -->
    <div v-if="activeTab === 'polling'" class="panel p-3 sm:p-4">
      <div class="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <span class="field-label">Маркетплейс</span>
          <select
            v-model="pollingFilters.market_type"
            class="input-field w-full"
            title="Фильтр по маркетплейсу. Выберите конкретный маркет или оставьте «Все маркеты»"
          >
            <option v-for="opt in marketOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div>
          <span class="field-label">Статус</span>
          <select
            v-model="pollingFilters.status"
            class="input-field w-full"
            title="Фильтр по результату поллинга: успех, ошибка, в процессе или частично"
          >
            <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div>
          <span class="field-label">Кабинет</span>
          <select
            v-model="pollingFilters.cabinet_id"
            class="input-field w-full"
            title="Фильтр по конкретному кабинету"
          >
            <option v-for="opt in cabinetOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="resetFilters"
            class="btn-icon"
            title="Сбросить все фильтры к значениям по умолчанию"
          >
            <span class="material-symbols-outlined text-[18px]">restart_alt</span>
          </button>
          <button
            @click="applyFilters"
            class="btn-primary flex-1"
            title="Применить выбранные фильтры к списку логов"
          >
            Применить
          </button>
        </div>
      </div>
    </div>

    <!-- Фильтры: Sync -->
    <div v-if="activeTab === 'sync'" class="panel p-3 sm:p-4">
      <div class="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <span class="field-label">Маркетплейс</span>
          <select
            v-model="syncFilters.market_type"
            class="input-field w-full"
            title="Фильтр по маркетплейсу. Выберите конкретный маркет или оставьте «Все маркеты»"
          >
            <option v-for="opt in marketOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div>
          <span class="field-label">Тип синхронизации</span>
          <select
            v-model="syncFilters.sync_type"
            class="input-field w-full"
            title="Что синхронизировалось: цены, остатки, заказы или полная синхронизация"
          >
            <option v-for="opt in syncTypeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div>
          <span class="field-label">Статус</span>
          <select
            v-model="syncFilters.status"
            class="input-field w-full"
            title="Фильтр по результату синхронизации: успех, ошибка, в процессе или частично"
          >
            <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div>
          <span class="field-label">Кабинет</span>
          <select
            v-model="syncFilters.cabinet_id"
            class="input-field w-full"
            title="Фильтр по конкретному кабинету"
          >
            <option v-for="opt in cabinetOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="resetFilters"
            class="btn-icon"
            title="Сбросить все фильтры к значениям по умолчанию"
          >
            <span class="material-symbols-outlined text-[18px]">restart_alt</span>
          </button>
          <button
            @click="applyFilters"
            class="btn-primary flex-1"
            title="Применить выбранные фильтры к списку логов"
          >
            Применить
          </button>
        </div>
      </div>
    </div>

    <!-- Загрузка -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="panel animate-pulse p-4">
        <div class="mb-2 h-4 w-1/3 rounded bg-slate-200/80"></div>
        <div class="h-4 w-2/3 rounded bg-slate-100"></div>
      </div>
    </div>

    <!-- Логи поллера -->
    <template v-else-if="activeTab === 'polling'">
      <div v-if="pollingLogs.items?.length" class="space-y-3">
        <div
          v-for="log in pollingLogs.items"
          :key="log._id"
          class="panel p-4 transition-shadow hover:shadow-[0_4px_18px_-10px_rgba(15,23,42,0.18)]"
        >
          <div class="flex flex-col justify-between gap-3 md:flex-row md:items-start">
            <!-- Левая часть -->
            <div class="min-w-0 flex-1">
              <!-- Верхняя строка: статус, маркет, кабинет -->
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12.5px] font-semibold"
                  :class="getStatusColor(log.status)"
                  :title="'Результат поллинга: ' + getStatusLabel(log.status)"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    :class="
                      log.status === 'success'
                        ? 'bg-emerald-500'
                        : log.status === 'error'
                          ? 'bg-rose-500'
                          : log.status === 'partial'
                            ? 'bg-orange-500'
                            : 'bg-amber-500'
                    "
                  ></span>
                  {{ getStatusLabel(log.status) }}
                </span>

                <span
                  class="inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 text-[12.5px] font-medium"
                  :class="getMarketColor(log.market_type).chip"
                  title="Маркетплейс, по которому выполнялся опрос"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    :style="{ backgroundColor: getMarketColor(log.market_type).hex }"
                  ></span>
                  {{ log.market_type }}
                </span>

                <span
                  class="text-[15px] font-semibold text-slate-900"
                  title="Название кабинета продавца, к которому относится лог"
                >
                  {{ log.cabinet_name || 'Без имени' }}
                </span>
              </div>

              <!-- Мета-строка -->
              <div class="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-slate-500">
                <span class="flex items-center gap-1.5" title="Дата и время запуска поллинга">
                  <span class="material-symbols-outlined text-[16px] text-slate-400">schedule</span>
                  {{ formatDate(log.started_at_iso) }}
                </span>

                <span class="flex items-center gap-1.5" title="Сколько времени занял поллинг">
                  <span class="material-symbols-outlined text-[16px] text-slate-400">timer</span>
                  {{ formatDuration(log.duration_seconds) }}
                </span>

                <!-- Всего обработано -->
                <span
                  class="flex items-center gap-1.5 font-medium text-slate-700"
                  title="Общее количество заказов, которые поллер обработал в этом цикле"
                >
                  <span class="material-symbols-outlined text-[16px] text-slate-400">touch_app</span>
                  Всего: {{ log.orders_touched || 0 }}
                </span>

                <!-- Создано -->
                <span
                  class="flex items-center gap-1.5 font-medium"
                  :class="log.orders_created > 0 ? 'text-emerald-600' : 'text-slate-400'"
                  title="Новые заказы, которых не было в базе до этого цикла"
                >
                  <span class="material-symbols-outlined text-[16px]">add_circle</span>
                  Создано: {{ log.orders_created || 0 }}
                </span>

                <!-- Обновлено -->
                <span
                  class="flex items-center gap-1.5 font-medium"
                  :class="log.orders_updated > 0 ? 'text-blue-600' : 'text-slate-400'"
                  title="Существующие заказы, у которых изменился статус или другие поля"
                >
                  <span class="material-symbols-outlined text-[16px]">sync</span>
                  Обновлено: {{ log.orders_updated || 0 }}
                </span>

                <!-- Ошибки -->
                <span
                  class="flex items-center gap-1.5 font-medium"
                  :class="log.orders_failed > 0 ? 'text-rose-600' : 'text-slate-400'"
                  title="Заказы, которые не удалось обработать из-за ошибки"
                >
                  <span class="material-symbols-outlined text-[16px]">error</span>
                  Ошибок: {{ log.orders_failed || 0 }}
                </span>
              </div>

              <!-- Ошибки -->
              <div
                v-if="getErrorMessage(log)"
                class="mt-2.5 rounded-lg border border-rose-200/70 bg-rose-50 px-3 py-2"
              >
                <p class="flex items-start gap-1.5 break-all text-[12.5px] font-medium text-rose-600">
                  <span class="material-symbols-outlined text-sm shrink-0 mt-0.5">error</span>
                  <span class="min-w-0">
                    {{
                      expandedErrors[log._id]
                        ? getErrorMessage(log)
                        : truncateError(getErrorMessage(log))
                    }}
                    <button
                      v-if="getErrorMessage(log).length > 160"
                      @click="toggleErrorExpand(log._id)"
                      class="ml-1 text-rose-700 underline hover:no-underline cursor-pointer font-semibold"
                      title="Показать или скрыть полный текст ошибки"
                    >
                      {{ expandedErrors[log._id] ? 'свернуть' : 'показать' }}
                    </button>
                  </span>
                </p>

                <p
                  v-if="log.errors?.length > 1"
                  class="text-xs text-rose-500 mt-1 ml-5"
                >
                  Всего ошибок: {{ log.errors.length }}
                </p>
              </div>
            </div>

            <!-- Кнопка удаления -->
            <button
              @click="deleteLog(log)"
              class="flex h-9 w-9 shrink-0 items-center justify-center self-start rounded-lg text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
              title="Удалить этот лог без возможности восстановления"
            >
              <span class="material-symbols-outlined text-[19px]">delete</span>
            </button>
          </div>
        </div>
      </div>

      <div v-else class="panel flex flex-col items-center justify-center gap-1.5 border-2 border-dashed border-slate-200 px-6 py-16 text-center">
        <span class="material-symbols-outlined text-3xl text-slate-300">list_alt</span>
        <h3 class="text-sm font-medium text-slate-700">Логов не найдено</h3>
        <p class="text-sm text-slate-400">Попробуйте изменить фильтры</p>
      </div>
    </template>

    <!-- Логи синхронизации -->
    <template v-else-if="activeTab === 'sync'">
      <div v-if="syncLogs.items?.length" class="space-y-3">
        <div
          v-for="log in syncLogs.items"
          :key="log._id"
          class="panel p-4 transition-shadow hover:shadow-[0_4px_18px_-10px_rgba(15,23,42,0.18)]"
        >
          <div class="flex flex-col justify-between gap-3 md:flex-row md:items-start">
            <div class="min-w-0 flex-1">
              <!-- Верхняя строка: статус, маркет, тип, кабинет -->
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12.5px] font-semibold"
                  :class="getStatusColor(log.status)"
                  :title="'Результат синхронизации: ' + getStatusLabel(log.status)"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    :class="
                      log.status === 'success'
                        ? 'bg-emerald-500'
                        : log.status === 'error'
                          ? 'bg-rose-500'
                          : log.status === 'partial'
                            ? 'bg-orange-500'
                            : 'bg-amber-500'
                    "
                  ></span>
                  {{ getStatusLabel(log.status) }}
                </span>

                <span
                  class="inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 text-[12.5px] font-medium"
                  :class="getMarketColor(log.market_type).chip"
                  title="Маркетплейс, в который отправлялись данные"
                >
                  <span
                    class="h-1.5 w-1.5 rounded-full"
                    :style="{ backgroundColor: getMarketColor(log.market_type).hex }"
                  ></span>
                  {{ log.market_type }}
                </span>

                <span
                  class="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[12.5px] font-medium"
                  :class="getSyncTypeColor(log.sync_type)"
                  :title="'Тип синхронизации: ' + getSyncTypeLabel(log.sync_type)"
                >
                  <span class="material-symbols-outlined text-[15px]">{{ getSyncTypeIcon(log.sync_type) }}</span>
                  {{ getSyncTypeLabel(log.sync_type) }}
                </span>

                <span
                  class="text-[15px] font-semibold text-slate-900"
                  title="Название кабинета продавца, к которому относится лог"
                >
                  {{ log.cabinet_name || 'Без имени' }}
                </span>
              </div>

              <!-- Мета-строка -->
              <div class="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-slate-500">
                <span class="flex items-center gap-1.5" title="Дата и время запуска синхронизации">
                  <span class="material-symbols-outlined text-[16px] text-slate-400">schedule</span>
                  {{ formatDate(log.started_at_iso) }}
                </span>

                <span class="flex items-center gap-1.5" title="Сколько времени заняла синхронизация">
                  <span class="material-symbols-outlined text-[16px] text-slate-400">timer</span>
                  {{ formatDuration(log.duration_seconds) }}
                </span>

                <!-- Всего -->
                <span
                  class="flex items-center gap-1.5 font-medium text-slate-700"
                  title="Общее количество товаров, обработанных в этой синхронизации"
                >
                  <span class="material-symbols-outlined text-[16px] text-slate-400">inventory_2</span>
                  Всего: {{ log.total_items || 0 }}
                </span>

                <!-- Успешно -->
                <span
                  class="flex items-center gap-1.5 font-medium"
                  :class="log.success_count > 0 ? 'text-emerald-600' : 'text-slate-400'"
                  title="Элементы, успешно отправленные в маркетплейс"
                >
                  <span class="material-symbols-outlined text-[16px]">check_circle</span>
                  Успешно: {{ log.success_count || 0 }}
                </span>

                <!-- Ошибок -->
                <span
                  class="flex items-center gap-1.5 font-medium"
                  :class="log.failed_count > 0 ? 'text-rose-600' : 'text-slate-400'"
                  title="Элементы, которые не удалось синхронизировать из-за ошибки"
                >
                  <span class="material-symbols-outlined text-[16px]">cancel</span>
                  Ошибок: {{ log.failed_count || 0 }}
                </span>
              </div>

              <!-- ── Источник данных: XML → WB → Сопоставлено ── -->
              <div
                v-if="hasSourceStats(log)"
                class="mt-2.5 flex flex-wrap items-center gap-2 text-[12.5px]"
              >
                <span
                  class="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-0.5 text-slate-700"
                  :title="'Сколько офферов было в XML-фиде'"
                >
                  <span class="material-symbols-outlined text-[15px] text-slate-400">description</span>
                  XML: <span class="font-semibold">{{ log.yml_items_total || 0 }}</span>
                </span>

                <span class="material-symbols-outlined text-[15px] text-slate-300">arrow_forward</span>

                <span
                  class="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-0.5 text-slate-700"
                  :title="'Сколько товаров вернул WB API'"
                >
                  <span class="material-symbols-outlined text-[15px] text-slate-400">storefront</span>
                  WB: <span class="font-semibold">{{ log.wb_goods_total || 0 }}</span>
                </span>

                <span class="material-symbols-outlined text-[15px] text-slate-300">arrow_forward</span>

                <span
                  class="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700"
                  :title="'Сколько артикулов WB сопоставилось с XML по vendorCode'"
                >
                  <span class="material-symbols-outlined text-[15px]">link</span>
                  Сопоставлено: <span class="font-semibold">{{ log.matched || 0 }}</span>
                </span>

                <span
                  v-if="log.unmatched_wb > 0"
                  class="inline-flex items-center gap-1 rounded-lg bg-orange-50 px-2 py-0.5 font-medium text-orange-700"
                  :title="'Товары WB, для которых не нашлось соответствия в XML — их остатки обнулены'"
                >
                  <span class="material-symbols-outlined text-[15px]">link_off</span>
                  Не сопоставлено: <span class="font-semibold">{{ log.unmatched_wb }}</span>
                </span>
              </div>

              <!-- ── Детализация: Цены и Остатки ── -->
              <div
                v-if="log.market_type === 'wb'"
                class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3"
              >
                <!-- Цены -->
                <div class="rounded-xl border border-amber-200/70 bg-amber-50/70 p-3.5">
                  <div class="mb-2 flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[17px] text-amber-600">sell</span>
                    <span class="text-[11.5px] font-semibold uppercase tracking-wider text-amber-800">Цены</span>
                  </div>
                  <div class="flex flex-wrap items-center gap-2.5 text-[12.5px]">
                    <span
                      class="inline-flex items-center gap-1 font-semibold text-amber-700"
                      title="Цены, которые реально изменились и были отправлены в WB"
                    >
                      <span class="material-symbols-outlined text-[15px]">edit</span>
                      Обновлено: <span class="font-bold">{{ getPricesBreakdown(log).updated }}</span>
                    </span>
                    <span class="text-amber-300">·</span>
                    <span
                      class="inline-flex items-center gap-1 text-slate-500"
                      title="Цены, которые совпали с текущими в WB и не отправлялись"
                    >
                      <span class="material-symbols-outlined text-[15px]">check</span>
                      Без изменений: <span class="font-semibold">{{ getPricesBreakdown(log).skipped }}</span>
                    </span>
                  </div>
                </div>

                <!-- Остатки -->
                <div class="rounded-xl border border-cyan-200/70 bg-cyan-50/70 p-3.5">
                  <div class="mb-2 flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[17px] text-cyan-600">inventory</span>
                    <span class="text-[11.5px] font-semibold uppercase tracking-wider text-cyan-800">Остатки</span>
                  </div>
                  <div class="flex flex-wrap items-center gap-2.5 text-[12.5px]">
                    <span
                      class="inline-flex items-center gap-1 font-semibold text-cyan-700"
                      title="Ненулевые остатки, отправленные в WB"
                    >
                      <span class="material-symbols-outlined text-[15px]">edit</span>
                      Обновлено: <span class="font-bold">{{ getStocksBreakdown(log).updated }}</span>
                    </span>
                    <span class="text-cyan-300">·</span>
                    <span
                      class="inline-flex items-center gap-1 font-semibold"
                      :class="getStocksBreakdown(log).zeroed > 0 ? 'text-orange-600' : 'text-slate-400'"
                      title="Остатки, обнулённые в WB: товар не найден в XML или остаток меньше кратности"
                    >
                      <span class="material-symbols-outlined text-[15px]">block</span>
                      Обнулено: <span class="font-bold">{{ getStocksBreakdown(log).zeroed }}</span>
                    </span>
                    <span class="text-cyan-300">·</span>
                    <span
                      class="inline-flex items-center gap-1 text-slate-500"
                      title="Остатки, которые совпали с текущими и не отправлялись"
                    >
                      <span class="material-symbols-outlined text-[15px]">check</span>
                      Без изменений: <span class="font-semibold">{{ getStocksBreakdown(log).skipped }}</span>
                    </span>
                  </div>
                </div>
              </div>

              <!-- Разбивка по подтипам (fallback для не-WB и старых логов) -->
              <div
                v-else-if="log.items?.length"
                class="mt-2.5 flex flex-wrap items-center gap-1.5"
              >
                <span class="text-[12.5px] text-slate-400" title="Разбивка обработки по подзадачам внутри одной синхронизации">
                  Детали:
                </span>
                <span
                  v-for="(item, idx) in log.items"
                  :key="idx"
                  class="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[12.5px] font-medium"
                  :class="getSyncTypeColor(item.sync_type)"
                  :title="`${getSyncTypeLabel(item.sync_type)}: обработано ${item.count} элементов`"
                >
                  <span class="material-symbols-outlined text-[15px]">{{ getSyncTypeIcon(item.sync_type) }}</span>
                  {{ getSyncTypeLabel(item.sync_type) }}:
                  <span class="font-bold">{{ item.count }}</span>
                </span>
              </div>

              <!-- Ошибки -->
              <div
                v-if="getErrorMessage(log)"
                class="mt-2.5 rounded-lg border border-rose-200/70 bg-rose-50 px-3 py-2"
              >
                <p class="flex items-start gap-1.5 break-all text-[12.5px] font-medium text-rose-600">
                  <span class="material-symbols-outlined text-sm shrink-0 mt-0.5">error</span>
                  <span class="min-w-0">
                    {{
                      expandedErrors[log._id]
                        ? getErrorMessage(log)
                        : truncateError(getErrorMessage(log))
                    }}
                    <button
                      v-if="getErrorMessage(log).length > 160"
                      @click="toggleErrorExpand(log._id)"
                      class="ml-1 text-rose-700 underline hover:no-underline cursor-pointer font-semibold"
                      title="Показать или скрыть полный текст ошибки"
                    >
                      {{ expandedErrors[log._id] ? 'свернуть' : 'показать' }}
                    </button>
                  </span>
                </p>

                <p
                  v-if="log.errors?.length > 1"
                  class="text-xs text-rose-500 mt-1 ml-5"
                >
                  Всего ошибок: {{ log.errors.length }}
                </p>
              </div>
            </div>

            <!-- Кнопка удаления -->
            <button
              @click="deleteLog(log)"
              class="flex h-9 w-9 shrink-0 items-center justify-center self-start rounded-lg text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
              title="Удалить этот лог без возможности восстановления"
            >
              <span class="material-symbols-outlined text-[19px]">delete</span>
            </button>
          </div>
        </div>
      </div>

      <div v-else class="panel flex flex-col items-center justify-center gap-1.5 border-2 border-dashed border-slate-200 px-6 py-16 text-center">
        <span class="material-symbols-outlined text-3xl text-slate-300">cloud_off</span>
        <h3 class="text-sm font-medium text-slate-700">Логов синхронизации не найдено</h3>
        <p class="text-sm text-slate-400">Попробуйте изменить фильтры</p>
      </div>
    </template>

    <!-- Пагинация -->
    <div v-if="totalPages > 1" class="mt-1 flex items-center justify-center gap-1">
      <button
        @click="changePage(pagination.page - 1)"
        :disabled="pagination.page <= 1"
        class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-40"
        title="Предыдущая страница"
      >
        <span class="material-symbols-outlined text-[20px]">chevron_left</span>
      </button>

      <span
        class="rounded-lg bg-slate-100/80 px-3 py-1.5 text-xs font-medium text-slate-600"
        title="Текущая страница и общее число страниц"
      >
        Страница {{ pagination.page }} из {{ totalPages }}
      </span>

      <button
        @click="changePage(pagination.page + 1)"
        :disabled="pagination.page >= totalPages"
        class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-40"
        title="Следующая страница"
      >
        <span class="material-symbols-outlined text-[20px]">chevron_right</span>
      </button>
    </div>
  </div>
</template>