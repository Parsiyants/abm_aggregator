<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useNotificationStore } from '@/stores/notifications'
import { useAppStore } from '@/stores/app'
import { useOrdersStore } from '@/stores/orders'
import { useFunction } from '@/composables/function'
import Pagination from '@/components/Pagination.vue'
import { useReferenceStore } from '@/stores/references'
import MultiSelectDropdown from '@/components/MultiSelectDropdown.vue'
import DateRange from '@/components/DateRange.vue'
import { all } from 'axios'

const notify = useNotificationStore()
const app = useAppStore()
const { formatPrice, copy, formatDate, getRussianStatus, getStatusDescription, getStatusBadgeClasses, getProcessStatus } = useFunction()
const ordersStore = useOrdersStore()
const refStore = useReferenceStore()

const loading = ref(false)
const initialized = ref(false)

const marketplaces = ref([])
const cabinets = ref([])

// === Фильтры ===
const filters = ref({
  search: '',
  process_status: ['New'],
  market_type: [],
  cabinet_name: [],
  order_date_from: '',
  order_date_to: '',
  send_date_from: '',
  send_date_to: '',
  all: true
})

// === Пагинация ===
const pagination = ref({
  page: 1,
  limit: 10,
})

// === Computed ===
const totalItems = computed(() => ordersStore.newOrders.total || 0)
const totalPages = computed(() => Math.ceil(totalItems.value / pagination.value.limit) || 1)

const displayOrders = computed(() => {
  const start = (pagination.value.page - 1) * pagination.value.limit
  const end = start + pagination.value.limit
  return ordersStore.newOrders.items.slice(start, end)
})

// === Справочники ===
const marketplaceOptions = computed(() =>
  marketplaces.value.map((mp) => ({
    value: mp.slug,
    label: mp.name,
  })),
)

const cabinetOptions = computed(() =>
  cabinets.value.map((c) => ({
    value: c.name,
    label: c.name,
  })),
)

// === Методы ===
const MARKET_ACCENT = {
  ozon: 'bg-blue-500',
  yandex: 'bg-amber-400',
  wb: 'bg-purple-500',
  avito: 'bg-emerald-500',
}

const MARKET_CHIP = {
  ozon: 'border-blue-200 bg-blue-50 text-blue-700',
  yandex: 'border-amber-200 bg-amber-50 text-amber-700',
  wb: 'border-purple-200 bg-purple-50 text-purple-700',
  avito: 'border-emerald-200 bg-emerald-50 text-emerald-700',
}

const marketAccent = (type) => MARKET_ACCENT[type] || 'bg-slate-400'
const marketChip = (type) => MARKET_CHIP[type] || 'border-slate-200 bg-slate-100 text-slate-600'

function normalizeFilters(filters) {
  const result = {}
  for (const key in filters) {
    const value = filters[key]
    result[key] = value === '' ? null : value
  }
  return result
}

async function loadOrders() {
  if (loading.value) return
  loading.value = true

  try {
    const clearFilters = normalizeFilters(filters.value)

    await ordersStore.fetchOrders(
      {
        ...clearFilters,
      },
      'new',
    )

    pagination.value.page = 1
    initialized.value = true
  } catch (err) {
    console.error('Ошибка загрузки заказов:', err)
  } finally {
    loading.value = false
  }
}

function applyFilters(newFilters) {
  filters.value = newFilters
  loadOrders()
}

function resetFilters() {
  filters.value = {
    search: '',
    process_status: ['New'],
    market_type: [],
    cabinet_name: [],
    order_date_from: '',
    order_date_to: '',
    send_date_from: '',
    send_date_to: '',
  }
  loadOrders()
}

function changePage(page) {
  if (page < 1 || page > totalPages.value) return
  pagination.value.page = page
}

const handleKeydown = (event) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    loadOrders()
  }
}

// === Инициализация ===
onMounted(async () => {
  // Загружаем справочники
  if (!refStore.marketplaces.length) await refStore.fetchAll('marketplaces')
  marketplaces.value = refStore.marketplaces

  if (!refStore.cabinets.length) await refStore.fetchAll('cabinets')
  cabinets.value = refStore.cabinets

  // Загружаем заказы, только если их ещё нет
  if (ordersStore.newOrders.items.length === 0) {
    await loadOrders()
  } else {
    initialized.value = true
    // Пересчитываем пагинацию при уже загруженных данных
    pagination.value.page = 1
  }
})

// Следим за добавлением новых заказов через WebSocket
watch(
  () => ordersStore.newOrders.total,
  () => {
    // Если мы на первой странице — обновляем отображение
    if (pagination.value.page === 1) {
      // computed сам обновится
    }
  }
)
</script>

<template>
  <section class="space-y-5">
    <div class="space-y-8">
      <!-- Header -->
      <div class="space-y-4">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 class="page-title">Новые заказы</h1>
            <p class="mt-1 text-sm text-slate-500">Заказы, которые ещё не взяты в работу</p>
          </div>

          <span
            class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm"
          >
            <span class="h-2 w-2 rounded-full bg-blue-500"></span>
            {{ ordersStore.newOrders.total }} новых
          </span>
        </div>

        <!-- Filters -->
        <div class="panel p-3 sm:p-4">
          <div class="grid grid-cols-1 gap-3 lg:grid-cols-12 lg:items-end">
            <!-- Поиск -->
            <div class="lg:col-span-9">
              <span class="field-label">Поиск</span>
              <div class="relative">
                <span
                  class="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
                >
                  search
                </span>
                <input
                  v-model="filters.search"
                  type="search"
                  @keydown="handleKeydown"
                  placeholder="Заказ, товар, кабинет…"
                  class="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm text-slate-800 outline-none transition-all placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400 focus:ring-4 focus:ring-slate-900/5"
                />
              </div>
            </div>

            <!-- Кнопки -->
            <div class="flex items-center gap-2 lg:col-span-3">
              <button type="button" @click="resetFilters(filters)" class="btn-ghost flex-1">
                <span class="material-symbols-outlined text-[18px]">restart_alt</span>
                Сбросить
              </button>
              <button type="button" @click="applyFilters(filters)" class="btn-primary flex-1">
                <span class="material-symbols-outlined text-[18px]">filter_alt</span>
                Применить
              </button>
            </div>

            <!-- Маркетплейс -->
            <div class="lg:col-span-2">
              <span class="field-label">Маркетплейс</span>
              <MultiSelectDropdown
                v-model="filters.market_type"
                :options="marketplaceOptions"
                placeholder="Все"
                searchable
              />
            </div>

            <!-- Кабинет -->
            <div class="lg:col-span-2">
              <span class="field-label">Кабинет</span>
              <MultiSelectDropdown
                v-model="filters.cabinet_name"
                :options="cabinetOptions"
                placeholder="Все"
                searchable
              />
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
          </div>
        </div>
      </div>

      <div v-if="ordersStore.loading">
        <div
          v-for="value in 6"
          :key="value"
          class="mb-3 h-[116px] w-full animate-pulse rounded-2xl bg-slate-200/70"
        ></div>
      </div>
      <!-- Товары -->
      <div>
        <div v-if="ordersStore.newOrders.total > 0" class="grid grid-cols-1 gap-3">
          <div
            v-for="order in displayOrders"
            :key="order._id"
            class="panel group relative py-4 pl-7 pr-4 transition-all duration-200 hover:shadow-[0_2px_14px_rgba(15,23,42,0.06)]"
          >
            <!-- Цветовая полоса маркетплейса -->
            <span
              class="absolute bottom-4 left-3 top-4 w-0.75 rounded-full"
              :class="marketAccent(order.market_type)"
            ></span>

            <div class="flex flex-col justify-between gap-6 md:flex-row md:items-center">
              <!-- Информация о заказе -->
              <div class="flex flex-1 items-center gap-4">
                <div
                  class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border"
                  :class="marketChip(order.market_type)"
                >
                  <span class="material-symbols-outlined text-[24px]">shopping_bag</span>
                </div>

                <div class="space-y-2.5">
                  <!-- Номер заказа -->
                  <div class="flex items-center gap-3">
                    <div class="flex items-center gap-1">
                      <button
                        @click="copy(order.order_id)"
                        class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                        title="Копировать ID"
                      >
                        <span class="material-symbols-outlined text-[19px]">content_copy</span>
                      </button>
                      <span class="text-[17px] font-semibold leading-none tracking-tight text-slate-900">
                        {{ order.order_id }}
                      </span>
                    </div>

                    <span
                      class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[13px] font-medium"
                      :class="marketChip(order.market_type)"
                      :title="`Кабинет: ${order.cabinet_name}`"
                    >
                      <span
                        class="h-2 w-2 rounded-full"
                        :class="marketAccent(order.market_type)"
                      ></span>
                      {{ order.cabinet_name }}
                    </span>
                  </div>

                  <!-- Товары -->
                  <div class="flex max-w-[760px] flex-col gap-1.5">
                    <div
                      v-for="item in order.items"
                      :key="item._id || item.article"
                      class="flex flex-wrap items-center gap-2 text-[13.5px] text-slate-600"
                    >
                      <button
                        @click="copy(item.article)"
                        class="flex cursor-pointer items-center justify-center text-slate-400 transition-colors hover:text-slate-700"
                        title="Копировать артикул"
                      >
                        <span class="material-symbols-outlined text-[16px]">content_copy</span>
                      </button>
                      <span class="whitespace-nowrap font-mono text-sm font-semibold text-slate-800">{{ item.article }}</span>
                      <span class="text-slate-300">·</span>
                      <span class="whitespace-nowrap">{{ item.count }} шт</span>
                      <span class="text-slate-300">·</span>
                      <span class="whitespace-nowrap font-semibold text-slate-800">{{ formatPrice(item.price) }}</span>
                      <span class="text-slate-300">·</span>
                      <span class="line-clamp-1" :title="item.name">{{ item.name }}</span>
                    </div>
                  </div>

                  <!-- Даты -->
                  <p class="flex flex-wrap items-center gap-2 text-[13px] text-slate-500">
                    <span
                      >Создан:
                      <span class="font-medium text-slate-700">{{ formatDate(order.order_date) }}</span></span
                    >
                    <span class="text-slate-300">|</span>
                    <span
                      >Отгрузка:
                      <span class="font-medium text-slate-700">{{ formatDate(order.send_date, true) }}</span></span
                    >
                    <span class="text-slate-300">|</span>
                    <span class="font-semibold text-slate-600">{{ order.items?.length || 0 }} поз.</span>
                  </p>
                </div>
              </div>

              <!-- Цены -->
              <div class="flex shrink-0 items-center justify-between gap-5 md:justify-end">
                <div class="flex flex-col items-end gap-2">
                  <p class="text-2xl font-semibold leading-none tracking-tight text-slate-900">
                    {{ formatPrice(order.price) }}
                  </p>
                  <span
                    class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[13px] font-semibold"
                    :class="[
                      getStatusBadgeClasses(order.market_status).bg,
                      getStatusBadgeClasses(order.market_status).text,
                      getStatusBadgeClasses(order.market_status).border || 'border-transparent',
                    ]"
                    :title="`Статус МП: ${getStatusDescription(order.market_status)}`"
                  >
                    <span class="material-symbols-outlined text-[16px]">storefront</span>
                    {{ getRussianStatus(order.market_status) }}
                  </span>
                </div>

                <button
                  @click="app.openHandleOrderModal(order)"
                  class="btn-primary h-11 px-5 active:scale-95"
                >
                  <span>В работу</span>
                  <span class="material-symbols-outlined text-[19px]">arrow_forward</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="panel flex flex-col items-center justify-center gap-1.5 border-2 border-dashed border-slate-200 px-6 py-16 text-center">
          <span class="material-symbols-outlined text-3xl text-slate-300"> box </span>
          <h3 class="text-sm font-medium text-slate-700">Заказы не найдены</h3>
          <p class="text-sm text-slate-400">Попробуйте изменить параметры поиска</p>
        </div>
      </div>

      <!-- Пагинация -->
    <Pagination
      v-if="totalPages > 1"
      :page="pagination.page"
      :total-pages="totalPages"
      :total-items="totalItems"
      @change-page="changePage"
    />
    </div>
  </section>
</template>
