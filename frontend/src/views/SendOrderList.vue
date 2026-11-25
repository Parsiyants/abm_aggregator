<script setup>
import { computed, onMounted, ref } from 'vue'
import { useOrdersStore } from '@/stores/orders'
import { useReferenceStore } from '@/stores/references'
import { useAppStore } from '@/stores/app'
import MultiSelectDropdown from '@/components/MultiSelectDropdown.vue'
import DateRange from '@/components/DateRange.vue'
import OrderCard from '@/components/OrderCard.vue'
import { useFunction } from '@/composables/function'
import ShipmentPdfButton from '@/components/pdf/ShipmentPdfButton.vue'

const ordersStore = useOrdersStore()
const refStore = useReferenceStore()
const appStore = useAppStore()
const { formatDate, formatPrice, openPDF, getStatusFilterOptions, getStatusesForGroup, sortByIndex } = useFunction()

const sendDate = ref(new Date().toISOString().split('T')[0])

const filters = ref({
  search: '',
  market_type: [],
  market_status: [], // ← НОВЫЙ ФИЛЬТР
  cabinet_name: [],
  order_date_from: '',
  order_date_to: '',
  send_date_from: new Date().toISOString().split('T')[0],
  send_date_to: new Date().toISOString().split('T')[0],
  my_send_date_from: '',
  my_send_date_to: '',
  item_status: [],
  item_provider: [],
})

const pagination = ref({ page: 1, total: 0, limit: 100, pages: 1 })

// Подпись периода отгрузки в заголовке (без «Invalid Date»)
const sendRangeLabel = computed(() => {
  const fmt = (value, withYear = false) => {
    if (!value) return ''
    const d = new Date(value)
    if (isNaN(d.getTime())) return ''
    return d.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      ...(withYear ? { year: 'numeric' } : {}),
    })
  }

  const from = fmt(filters.value.send_date_from)
  const to = fmt(filters.value.send_date_to, true)

  if (!from && !to) return 'Период не выбран'
  if (!to) return `с ${from}`
  if (!from) return `до ${to}`
  return `${from} — ${to}`
})

// Локальные справочники
const providers = ref([])
const statuses = ref([])
const marketplaces = ref([])
const cabinets = ref([])

// === Исправленный computed для кабинетов ===
const activeCabinets = computed(() => {
  const map = new Map()

  ordersStore.orders?.items?.forEach((order) => {
    const name = order.cabinet_name
    if (!name) return

    if (!map.has(name)) {
      map.set(name, {
        name,
        count: 0,
        market: order.market_type || 'unknown',
      })
    }
    map.get(name).count += 1
  })

  return Array.from(map.values())
})

// Преобразование справочников
const marketplaceOptions = computed(() =>
  marketplaces.value.map((mp) => ({ value: mp.slug, label: mp.name })),
)

const statusOptions = computed(() => statuses.value.map((s) => ({ value: s.name, label: s.name })))

const providerOptions = computed(() =>
  providers.value.map((p) => ({ value: p.name, label: p.name })),
)

// ── Опции для статусов маркетплейсов ──────────────────────
const marketStatusOptions = computed(() => {
  const options = getStatusFilterOptions()
  return options.map((opt) => ({
    value: opt.value,
    label: opt.label,
  }))
})

// Цвета маркетплейсов для точек-индикаторов
const marketDot = {
  ozon: '#2563eb',
  yandex: '#f59e0b',
  wb: '#a855f7',
  avito: '#22c55e',
}

// === Безопасное переключение кабинета ===
function toggleCabinet(cabinetName) {
  const current = filters.value.cabinet_name

  if (current.includes(cabinetName)) {
    filters.value.cabinet_name = current.filter((name) => name !== cabinetName)
  } else {
    filters.value.cabinet_name = [...current, cabinetName]
  }
}

async function loadOrders() {
  const clearFilters = normalizeFilters(filters.value)

  await ordersStore.fetchOrders(
    {
      page: pagination.value.page,
      limit: pagination.value.limit,
      ...clearFilters,
    },
    'order',
  )

  pagination.value.total = ordersStore.orders.total || 0
  pagination.value.pages = ordersStore.orders.pages || 1
}

function normalizeFilters(f) {
  const result = {}
  for (const key in f) {
    const value = f[key]
    if (key === 'market_status' && value && value.length > 0) {
      // Преобразуем группу в список статусов МП
      const statuses = []
      value.forEach((group) => {
        statuses.push(...getStatusesForGroup(group))
      })
      result[key] = statuses
    } else {
      result[key] = value === '' || (Array.isArray(value) && value.length === 0) ? null : value
    }
  }
  return result
}

async function reset() {
  filters.value = {
    search: '',
    market_type: [],
    market_status: [], // ← НОВЫЙ ФИЛЬТР
    cabinet_name: [],
    order_date_from: '',
    order_date_to: '',
    send_date_from: new Date().toISOString().split('T')[0],
    send_date_to: new Date().toISOString().split('T')[0],
    my_send_date_from: '',
    my_send_date_to: '',
    item_status: [],
    item_provider: [],
  }

  pagination.value.page = 1
  await loadOrders()
}

// ── Поиск по Enter ──────────────────────────────────────────
const handleKeydown = (event) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    loadOrders()
  }
}

onMounted(async () => {
  await loadOrders()

  // Загружаем справочники
  if (!refStore.providers.length) await refStore.fetchAll('providers')
  providers.value = sortByIndex(refStore.providers)

  if (!refStore.statuses.length) await refStore.fetchAll('statuses')
  statuses.value = sortByIndex(refStore.statuses)

  if (!refStore.marketplaces.length) await refStore.fetchAll('marketplaces')
  marketplaces.value = refStore.marketplaces

  if (!refStore.cabinets.length) await refStore.fetchAll('cabinets')
  cabinets.value = refStore.cabinets
})
</script>

<template>
  <div class="space-y-5">
    <!-- Header -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Отгрузки</h1>
        <p class="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-slate-500">
          <span class="material-symbols-outlined text-[16px] text-slate-400">event</span>
          {{ sendRangeLabel }}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <span
          class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm"
        >
          <span class="material-symbols-outlined text-[16px] text-slate-400">inventory_2</span>
          {{ ordersStore.orders?.total }} заказов
        </span>
        <ShipmentPdfButton
          :orders="ordersStore.orders?.items"
          :selected-date-from="filters.send_date_from"
          :selected-date-to="filters.send_date_to"
        />
      </div>
    </div>

    <!-- Filters -->
    <div class="panel p-3 sm:p-4">
      <div class="grid grid-cols-1 gap-3 lg:grid-cols-12 lg:items-end">
        <!-- Поиск -->
        <div class="lg:col-span-10">
          <span class="field-label">Поиск</span>
          <div class="relative">
            <span
              class="material-symbols-outlined pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
            >
              search
            </span>
            <input
              v-model="filters.search"
              @keydown="handleKeydown"
              type="search"
              placeholder="Заказ, товар, кабинет…"
              class="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm text-slate-800 outline-none transition-all placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400 focus:ring-4 focus:ring-slate-900/5"
            />
          </div>
        </div>

        <!-- Кнопки -->
        <div class="flex items-center justify-end gap-2 lg:col-span-2">
          <button type="button" @click="reset" class="btn-icon" title="Сбросить фильтры">
            <span class="material-symbols-outlined text-[18px]">restart_alt</span>
          </button>
          <button type="button" @click="loadOrders" class="btn-primary">
            <span class="material-symbols-outlined text-[18px]">filter_alt</span>
            Применить
          </button>
        </div>

        <!-- Дата Заказа -->
        <div class="lg:col-span-4">
          <span class="field-label">Дата заказа</span>
          <DateRange v-model:from="filters.order_date_from" v-model:to="filters.order_date_to" />
        </div>

        <!-- Дата Отгрузки -->
        <div class="lg:col-span-4">
          <span class="field-label">Дата отгрузки</span>
          <DateRange v-model:from="filters.send_date_from" v-model:to="filters.send_date_to" />
        </div>

        <!-- Моя Дата Отгрузки -->
        <div class="lg:col-span-4">
          <span class="field-label">Моя дата отгрузки</span>
          <DateRange v-model:from="filters.my_send_date_from" v-model:to="filters.my_send_date_to" />
        </div>
      </div>

      <!-- Селекты -->
      <div class="mt-3 grid grid-cols-2 gap-2.5 border-t border-slate-100 pt-3 sm:grid-cols-4">
        <MultiSelectDropdown
          v-model="filters.market_type"
          :options="marketplaceOptions"
          placeholder="Маркетплейс"
          searchable
        />
        <MultiSelectDropdown
          v-model="filters.market_status"
          :options="marketStatusOptions"
          placeholder="Статус МП"
          searchable
        />
        <MultiSelectDropdown
          v-model="filters.item_status"
          :options="statusOptions"
          placeholder="Статус товара"
          searchable
        />
        <MultiSelectDropdown
          v-model="filters.item_provider"
          :options="providerOptions"
          placeholder="Поставщик"
          searchable
        />
      </div>
    </div>

    <!-- Кабинеты -->
    <div v-if="activeCabinets.length > 0" class="flex flex-wrap gap-2">
      <button
        v-for="cabinet in activeCabinets"
        :key="cabinet.name"
        type="button"
        @click="toggleCabinet(cabinet.name)"
        class="inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-all duration-200"
        :class="
          filters.cabinet_name.includes(cabinet.name)
            ? 'border-slate-900 bg-slate-900 text-white shadow-sm'
            : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
        "
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :style="{ backgroundColor: marketDot[cabinet.market] || '#94a3b8' }"
        ></span>
        <span class="font-medium">{{ cabinet.name }}</span>
        <span
          class="rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
          :class="filters.cabinet_name.includes(cabinet.name) ? 'bg-white/15' : 'bg-slate-100'"
        >
          {{ cabinet.count }}
        </span>
      </button>
    </div>

    <!-- Skeleton Товары -->
    <div v-if="ordersStore.loading">
      <div
        v-for="key in 6"
        :key="key"
        class="mb-3 h-[220px] w-full animate-pulse rounded-2xl bg-slate-200/70"
      ></div>
    </div>
    <!-- Товары -->
    <div v-else>
      <div v-if="ordersStore.orders.total > 0" class="space-y-3">
        <OrderCard v-for="order in ordersStore.orders.items" :key="order._id" :order="order" />
      </div>

      <div v-else class="panel flex flex-col items-center justify-center gap-1.5 border-2 border-dashed border-slate-200 px-6 py-16 text-center">
        <span class="material-symbols-outlined text-3xl text-slate-300"> box </span>
        <h3 class="text-sm font-medium text-slate-700">Отгрузки на эту дату не найдены</h3>
        <p class="text-sm text-slate-400">Попробуйте изменить параметры поиска</p>
      </div>
    </div>
  </div>
</template>