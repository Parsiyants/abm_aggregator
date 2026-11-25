<script setup>
import { ref, onMounted, computed } from 'vue'
import { useOrdersStore } from '@/stores/orders'
import { useReferenceStore } from '@/stores/references'

import OrderCard from '@/components/OrderCard.vue'
import Pagination from '@/components/Pagination.vue'
import Filters from '@/components/Filters.vue'
import { useFunction } from '@/composables/function'

const ordersStore = useOrdersStore()
const refStore = useReferenceStore()
const { getStatusFilterOptions, getStatusesForGroup, formatPrice } = useFunction()

const loading = ref(false)

const filters = ref({
  search: '',
  process_status: ['Process'], // ← добавлен New
  market_type: [],
  market_status: [], // ← НОВЫЙ ФИЛЬТР
  cabinet_name: [],
  order_date_from: '',
  order_date_to: '',
  send_date_from: '',
  send_date_to: '',
  my_send_date_from: '',
  my_send_date_to: '',
  item_status: [],
  item_provider: [],
})

const cancellation_type = ref('')

const pagination = ref({
  page: 1,
  limit: 20,
  total: 0,
  pages: 1,
})

// ── Опции для статусов маркетплейсов ──────────────────────
const marketStatusOptions = computed(() => {
  const options = getStatusFilterOptions()
  return options.map((opt) => ({
    value: opt.value,
    label: opt.label,
  }))
})

// Основная функция загрузки заказов
async function loadOrders() {
  loading.value = true

  try {
    const clearFilters = normalizeFilters({
      ...filters.value,
      cancellation_type: cancellation_type.value,
    })

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
  } catch (err) {
    console.error('Ошибка загрузки заказов:', err)
  } finally {
    loading.value = false
  }
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

// Применение фильтров (вызывается из компонента Filters)
function applyFilters(newFilters) {
  filters.value = { ...newFilters }
  pagination.value.page = 1
  loadOrders()
}

// Сброс всех фильтров
function resetFilters() {
  filters.value = {
    search: '',
    process_status: ['Process', 'New'],
    market_type: [],
    market_status: [],
    cabinet_name: [],
    order_date_from: '',
    order_date_to: '',
    send_date_from: '',
    send_date_to: '',
    my_send_date_from: '',
    my_send_date_to: '',
    item_status: [],
    item_provider: [],
  }

  cancellation_type.value = ''

  pagination.value.page = 1
  loadOrders()
}

// Смена страницы (вызывается из Pagination)
function changePage(page) {
  pagination.value.page = page
  loadOrders()
}

// Инициализация при монтировании
onMounted(async () => {
  await loadOrders()
})
</script>

<template>
  <div class="space-y-5">
    <!-- Заголовок -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Заказы</h1>
        <p class="mt-1 text-sm text-slate-500">
          Все заказы маркетплейсов — статусы, суммы и обработка
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <span
          class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm"
        >
          <span class="material-symbols-outlined text-[16px] text-slate-400">receipt_long</span>
          {{ ordersStore.orders.total }} заказов
        </span>
        <span
          class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-emerald-200/70 bg-emerald-50 px-3 text-xs font-medium text-emerald-700"
        >
          Сумма: {{ formatPrice(ordersStore.orders.total_price) }}
        </span>
        <span
          class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm"
        >
          Закуп: {{ formatPrice(ordersStore.orders.total_purchase) }}
        </span>
      </div>
    </div>

    <!-- Фильтры -->
    <Filters
      :initialFilters="filters"
      :marketStatusOptions="marketStatusOptions"
      @apply="applyFilters"
      @reset="resetFilters"
    />

    <!-- Загрузка -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 6" :key="i" class="h-40 animate-pulse rounded-2xl bg-slate-200/70"></div>
    </div>

    <!-- Пусто -->
    <div
      v-else-if="!ordersStore.orders.items?.length"
      class="panel flex flex-col items-center justify-center gap-1.5 px-6 py-20 text-center"
    >
      <span class="material-symbols-outlined text-3xl text-slate-300">inbox</span>
      <p class="text-sm font-medium text-slate-700">Заказов не найдено</p>
      <p class="text-sm text-slate-400">Попробуйте изменить фильтры</p>
    </div>

    <!-- Список -->
    <div v-else class="space-y-3">
      <div v-if="filters.process_status.includes('Cancel')" class="flex flex-wrap items-center gap-2">
        <span class="text-xs font-medium text-slate-500">Инициатор отмены:</span>
        <select
          v-model="cancellation_type"
          class="input-field h-9 w-auto pr-8 text-[13px]"
          @change="loadOrders"
        >
          <option value="">Любой</option>
          <option value="seller">Мы</option>
          <option value="other">Клиент</option>
        </select>
      </div>

      <OrderCard v-for="order in ordersStore.orders.items" :key="order._id" :order="order" />
    </div>

    <!-- Пагинация -->
    <Pagination
      v-if="pagination.pages > 1"
      :page="pagination.page"
      :total-pages="pagination.pages"
      :total-items="pagination.total"
      @change-page="changePage"
    />
  </div>
</template>