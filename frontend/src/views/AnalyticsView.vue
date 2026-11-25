<script setup>
import { ref, onMounted, computed } from 'vue'
import dayjs from 'dayjs'
import api from '@/services/api'
import MultiSelectDropdown from '@/components/MultiSelectDropdown.vue'
import DateRange from '@/components/DateRange.vue'
import { useReferenceStore } from '@/stores/references'
import { useFunction } from '@/composables/function'
import LineChart from '@/components/LineChart.vue'

const refStore = useReferenceStore()
const { formatDate, formatPrice, sortByIndex } = useFunction()

// HEX-цвета маркетплейсов (для индикаторов и акцентов)
const MARKET_HEX = {
  ozon: '#2563eb',
  yandex: '#fbbf24',
  wb: '#a855f7',
  avito: '#22c55e',
}

const marketHex = (type) => MARKET_HEX[type] || '#94a3b8'

const currentPeriodType = ref('day')

// Options для MultiSelect
const marketOptions = ref([])
const cabinetOptions = ref([])
const statusOptions = ref([])
const providerOptions = ref([])

const processStatusOptions = ref([
  { value: 'New', label: 'Новый' },
  { value: 'Process', label: 'В процессе' },
  { value: 'Done', label: 'Завершён' },
  { value: 'Cancel', label: 'Отменён' },
])

const chartDateFrom = ref(dayjs().startOf('month').format('YYYY-MM-DD'))
const chartDateTo = ref(dayjs().format('YYYY-MM-DD'))

// Фильтры
const filters = ref({
  date_from: dayjs().startOf('month').format('YYYY-MM-DD'),
  date_to: dayjs().format('YYYY-MM-DD'),
  search: '',
  market_types: [],
  cabinet_names: [],
  process_statuses: [],
  item_providers: [],
  item_statuses: [],
})

// Быстрые периоды
const quickPeriods = [
  { label: 'Этот месяц', value: 'this_month' },
  { label: 'Прошлый месяц', value: 'last_month' },
  { label: '3 Месяца', value: '3_month' },
]

function setPeriod(period) {
  const today = dayjs()
  if (period === 'this_month') {
    filters.value.date_from = today.startOf('month').format('YYYY-MM-DD')
    filters.value.date_to = today.format('YYYY-MM-DD')
  } else if (period === 'last_month') {
    filters.value.date_from = today.subtract(1, 'month').startOf('month').format('YYYY-MM-DD')
    filters.value.date_to = today.subtract(1, 'month').endOf('month').format('YYYY-MM-DD')
  } else if (period === '3_month') {
    filters.value.date_from = today.subtract(3, 'month').startOf('month').format('YYYY-MM-DD')
    filters.value.date_to = today.format('YYYY-MM-DD')
  }

  loadAnalytics()
}

const loading = ref(false)
const analytics = ref(null)

// ==================== ЗАГРУЗКА ====================
async function loadAnalytics() {
  loading.value = true
  try {
    const params = { ...filters.value }

    if (!params.market_types?.length) delete params.market_types
    if (!params.cabinet_names?.length) delete params.cabinet_names
    if (!params.process_statuses?.length) delete params.process_statuses
    if (!params.item_providers?.length) delete params.item_providers
    if (!params.item_statuses?.length) delete params.item_statuses

    const { data } = await api.get('/orders/analytics', { params })
    analytics.value = data
    chartDateFrom.value = filters.value.date_from
    chartDateTo.value = filters.value.date_to
  } catch (err) {
    console.error('Ошибка загрузки аналитики:', err)
    analytics.value = null
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.value = {
    date_from: dayjs().startOf('month').format('YYYY-MM-DD'),
    date_to: dayjs().format('YYYY-MM-DD'),
    search: '',
    market_types: [],
    cabinet_names: [],
    process_statuses: [],
    item_providers: [],
    item_statuses: [],
  }
  loadAnalytics()
}

onMounted(async () => {
  await Promise.all([
    refStore.fetchAll('marketplaces'),
    refStore.fetchAll('providers'),
    refStore.fetchAll('cabinets'),
    refStore.fetchAll('statuses'),
  ])

  marketOptions.value = refStore.marketplaces.map((m) => ({ value: m.slug, label: m.name }))
  providerOptions.value = sortByIndex(refStore.providers).map((p) => ({ value: p.name, label: p.name }))
  cabinetOptions.value = refStore.cabinets.map((c) => ({ value: c.name, label: c.name }))
  statusOptions.value = sortByIndex(refStore.statuses).map((s) => ({ value: s.name, label: s.name }))

  await loadAnalytics()
})
</script>

<template>
  <div class="space-y-5 pb-12">
    <!-- Заголовок -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Аналитика</h1>
        <p class="mt-1 text-sm text-slate-500">
          Продажи, расходы и прибыль по маркетплейсам и кабинетам
        </p>
      </div>

      <span
        class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm"
      >
        <span class="material-symbols-outlined text-[16px] text-slate-400">event</span>
        {{ formatDate(filters.date_from) }} — {{ formatDate(filters.date_to) }}
      </span>
    </div>

    <!-- ==================== ФИЛЬТРЫ ==================== -->
    <div class="panel p-3 sm:p-4">
      <div class="grid grid-cols-1 gap-3 lg:grid-cols-12 lg:items-end">
        <!-- Поиск -->
        <div class="lg:col-span-5">
          <span class="field-label">Поиск</span>
          <div class="relative">
            <span
              class="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
            >
              search
            </span>
            <input
              v-model="filters.search"
              type="text"
              placeholder="Номер заказа, артикул, название…"
              class="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm text-slate-800 outline-none transition-all placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400 focus:ring-4 focus:ring-slate-900/5"
            />
          </div>
        </div>

        <div class="lg:col-span-4">
          <span class="field-label">Период</span>
          <DateRange v-model:from="filters.date_from" v-model:to="filters.date_to" />
        </div>

        <div class="flex items-center gap-2 lg:col-span-3 lg:justify-end">
          <button @click="resetFilters" class="btn-icon" title="Сбросить фильтры">
            <span class="material-symbols-outlined text-[18px]">restart_alt</span>
          </button>
          <button @click="loadAnalytics" class="btn-primary flex-1 lg:flex-none">
            <span class="material-symbols-outlined text-[18px]">filter_alt</span>
            Применить
          </button>
        </div>
      </div>

      <!-- Быстрые периоды -->
      <div class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3">
        <span class="mr-1 text-[13px] font-medium text-slate-500">Период:</span>
        <button
          v-for="tab in quickPeriods"
          :key="tab.value"
          @click="setPeriod(tab.value)"
          class="rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors"
          :class="
            filters.date_from === dayjs().startOf('month').format('YYYY-MM-DD') &&
            tab.value === 'this_month'
              ? 'bg-slate-900 text-white'
              : 'text-slate-600 hover:bg-slate-100'
          "
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Селекты -->
      <div class="mt-3 grid grid-cols-2 gap-2.5 border-t border-slate-100 pt-3 md:grid-cols-5">
        <MultiSelectDropdown
          v-model="filters.market_types"
          :options="marketOptions"
          placeholder="Маркетплейсы"
          searchable
        />
        <MultiSelectDropdown
          v-model="filters.cabinet_names"
          :options="cabinetOptions"
          placeholder="Кабинеты"
          searchable
        />
        <MultiSelectDropdown
          v-model="filters.process_statuses"
          :options="processStatusOptions"
          placeholder="Процесс"
        />
        <MultiSelectDropdown
          v-model="filters.item_providers"
          :options="providerOptions"
          placeholder="Поставщики"
          searchable
        />
        <MultiSelectDropdown
          v-model="filters.item_statuses"
          :options="statusOptions"
          placeholder="Статусы товаров"
          searchable
        />
      </div>
    </div>

    <!-- ==================== ОБЩАЯ СТАТИСТИКА ==================== -->
    <div class="card p-6 relative">
      <div
        v-if="loading"
        class="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-white/70 backdrop-blur-[2px]"
      >
        <span class="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"></span>
      </div>

      <div class="mb-2 text-lg font-semibold tracking-tight text-slate-900">Общая аналитика</div>
      <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
          <div class="text-[13px] font-medium text-slate-500">Заказов</div>
          <div class="mt-1.5 text-2xl font-semibold tracking-tight text-slate-900">{{ analytics?.grand_total?.total_orders || 0 }}</div>
        </div>
        <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
          <div class="text-[13px] font-medium text-slate-500">Товаров</div>
          <div class="mt-1.5 text-2xl font-semibold tracking-tight text-slate-900">
            {{ analytics?.grand_total?.total_items || 0 }} шт
          </div>
        </div>
        <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
          <div class="text-[13px] font-medium text-slate-500">Сумма продаж</div>
          <div class="mt-1.5 text-2xl font-semibold tracking-tight text-slate-900">
            {{ formatPrice(analytics?.grand_total?.total_price) }}
          </div>
        </div>
        <div class="rounded-xl border border-rose-200/70 bg-rose-50/60 p-4">
          <div class="flex items-center gap-1.5">
            <div class="text-[13px] font-medium text-slate-500">Сумма расходов</div>
            <!-- Кнопка информации о расходах -->
            <div class="relative group">
              <button
                class="group flex items-center justify-center text-gray-500 rounded-xl transition-all"
                title="Детализация расходов"
              >
                <span class="material-symbols-outlined text-xl">info</span>
              </button>

              <!-- Подсказка при hover -->
              <div
                class="absolute right-0 top-10 w-72 bg-white border border-gray-200 rounded-2xl shadow-xl p-5 text-sm z-50 hidden group-hover:block"
              >
                <div class="font-medium mb-3 text-gray-900">Расходы</div>
                <div class="space-y-2 text-xs">
                  <div class="flex justify-between">
                    <span class="text-gray-600">Комиссия маркетплейса</span>
                    <span>{{
                      formatPrice(analytics?.grand_total?.commission_market_total || 0)
                    }}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-gray-600">Комиссия оплаты</span>
                    <span>{{
                      formatPrice(analytics?.grand_total?.commission_payment_total || 0)
                    }}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-gray-600">Последняя миля</span>
                    <span>{{ formatPrice(analytics?.grand_total?.last_mile_total || 0) }}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-gray-600">Обработка (фиксировано)</span>
                    <span>{{
                      formatPrice(analytics?.grand_total?.processing_fixed_total || 0)
                    }}</span>
                  </div>
                  <div class="flex justify-between">
                    <span class="text-gray-600">Логистика</span>
                    <span>{{ formatPrice(analytics?.grand_total?.logistics_total || 0) }}</span>
                  </div>
                  <div class="border-t border-gray-200 pt-3 mt-2 flex justify-between font-medium">
                    <span class="text-gray-700">Итого расходов</span>
                    <span class="text-red-600">{{
                      formatPrice(analytics?.grand_total?.total_expenses || 0)
                    }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-1.5 text-2xl font-semibold tracking-tight text-rose-600">
            {{ formatPrice(analytics?.grand_total?.total_expenses) }}
          </div>
        </div>
        <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
          <div class="text-[13px] font-medium text-slate-500">Закуп</div>
          <div class="mt-1.5 text-2xl font-semibold tracking-tight text-slate-900">
            {{ formatPrice(analytics?.grand_total?.total_purchase) }}
          </div>
        </div>
        <div class="rounded-xl border border-emerald-200/70 bg-emerald-50/60 p-4">
          <div class="text-[13px] font-medium text-slate-500">Прибыль от маркета</div>
          <div class="mt-1.5 text-2xl font-semibold tracking-tight text-emerald-600">
            {{ formatPrice(analytics?.grand_total?.total_profit) }}
          </div>
        </div>
        <div class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
          <div class="text-[13px] font-medium text-slate-500">Чистая прибыль</div>
          <div
            class="mt-1.5 text-2xl font-semibold tracking-tight"
            :class="
              analytics?.grand_total?.total_profit - analytics?.grand_total?.total_purchase > 0
                ? 'text-emerald-600'
                : 'text-rose-600'
            "
          >
            {{
              formatPrice(
                analytics?.grand_total?.total_profit - analytics?.grand_total?.total_purchase,
              )
            }}
          </div>
        </div>
      </div>
    </div>

    <!-- ГРАФИК -->
    <div class="card p-6 relative">
      <div
        v-if="loading"
        class="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-white/70 backdrop-blur-[2px]"
      >
        <span class="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"></span>
      </div>
      <div class="mb-5 flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-lg font-semibold tracking-tight text-slate-900">Динамика продаж по дням</h2>
        <div class="text-[13px] font-medium text-slate-500">
          {{ formatDate(filters.date_from) }} — {{ formatDate(filters.date_to) }}
        </div>
      </div>

      <div class="">
        <LineChart
          :daily-stats="analytics?.daily_stats || []"
          :date-from="chartDateFrom"
          :date-to="chartDateTo"
          v-model:period-type="currentPeriodType"
        />
      </div>
    </div>

    <!-- ==================== МАРКЕТПЛЕЙСЫ С КАБИНЕТАМИ ==================== -->
    <div class="space-y-10">
      <div v-for="market in analytics?.market_groups" :key="market._id" class="card p-6">
        <!-- Название маркетплейса + сводка -->
        <div class="flex items-center justify-between mb-8">
          <div class="flex items-center gap-3">
            <div
              class="h-5 w-5 rounded-full"
              :style="{ backgroundColor: marketHex(market._id) }"
            ></div>
            <h3 class="text-lg font-semibold capitalize tracking-tight text-slate-900">{{ market._id }}</h3>
          </div>

          <div class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl bg-slate-50 px-4 py-3 text-[13.5px]">
            <div>
              <span class="text-gray-500">Заказов:</span>
              <span class="font-semibold ml-1">{{ market.total_orders }}</span>
            </div>
            <div>
              <span class="text-gray-500">Сумма продаж:</span>
              <span class="font-semibold ml-1">{{ formatPrice(market.total_price) }}</span>
            </div>
            <div>
              <span class="text-gray-500">Закуп:</span>
              <span class="font-semibold ml-1">{{ formatPrice(market.total_purchase) }}</span>
            </div>
            <div class="flex items-center">
              <span class="text-gray-500">Расходы:</span>
              <span class="font-semibold ml-1">{{ formatPrice(market.total_expenses) }}</span>
              <!-- Кнопка информации о расходах -->
              <div class="relative group ml-2">
                <button
                  class="group w-7 h-7 flex items-center justify-center rounded-xl transition-all text-slate-600 hover:text-gray-800 cursor-pointer"
                  title="Детализация расходов"
                >
                  <span class="material-symbols-outlined text-xl">info</span>
                </button>

                <!-- Подсказка при hover -->
                <div
                  class="absolute right-0 top-10 w-72 bg-white border border-gray-200 rounded-2xl shadow-xl p-5 text-sm z-50 hidden group-hover:block"
                >
                  <div class="font-medium mb-3 text-gray-900">Расходы по кабинету</div>
                  <div class="space-y-2 text-xs">
                    <div class="flex justify-between">
                      <span class="text-gray-600">Комиссия маркетплейса</span>
                      <span>{{ formatPrice(market.commission_market_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Комиссия оплаты</span>
                      <span>{{ formatPrice(market.commission_payment_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Последняя миля</span>
                      <span>{{ formatPrice(market.last_mile_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Обработка (фиксировано)</span>
                      <span>{{ formatPrice(market.processing_fixed_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Логистика</span>
                      <span>{{ formatPrice(market.logistics_total || 0) }}</span>
                    </div>
                    <div
                      class="border-t border-gray-200 pt-3 mt-2 flex justify-between font-medium"
                    >
                      <span class="text-gray-700">Итого расходов</span>
                      <span class="text-red-600">{{
                        formatPrice(market.total_expenses || 0)
                      }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div>
              <span class="text-gray-500">Прибыль от маркета:</span>
              <span
                class="font-bold ml-1"
                :class="market.total_profit > 0 ? 'text-emerald-600' : 'text-red-600'"
                >{{ formatPrice(market.total_profit || 0) }}</span
              >
            </div>
            <div>
              <span class="text-gray-500">Чистая прибыль:</span>
              <span
                class="font-bold ml-1"
                :class="
                  market.total_profit - market.total_purchase > 0
                    ? 'text-emerald-600'
                    : 'text-red-600'
                "
                >{{ formatPrice(market.total_profit - market.total_purchase || 0) }}</span
              >
            </div>
          </div>
        </div>

        <!-- Кабинеты -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="cab in market.cabinet_details"
            :key="cab.cabinet_name"
            class="relative rounded-2xl border p-5"
            :style="{
              borderColor: marketHex(market._id) + '55',
              backgroundColor: marketHex(market._id) + '0d',
            }"
          >
            <div class="flex justify-between items-start mb-6">
              <div>
                <div class="text-[17px] font-semibold tracking-tight text-slate-900">{{ cab.cabinet_name || '—' }}</div>
                <div class="text-[13px] text-slate-500">Кабинет</div>
              </div>

              <!-- Кнопка информации о расходах -->
              <div class="relative group">
                <button
                  class="group flex h-8 w-8 items-center justify-center rounded-full transition-all duration-200 cursor-help"
                  :style="{
                    backgroundColor: marketHex(market._id) + '1f',
                    color: marketHex(market._id),
                  }"
                  title="Детализация расходов"
                >
                  <span class="material-symbols-outlined text-xl">info</span>
                </button>

                <!-- Подсказка при hover -->
                <div
                  class="absolute right-0 top-10 w-72 bg-white border border-gray-200 rounded-2xl shadow-xl p-5 text-sm z-50 hidden group-hover:block"
                >
                  <div class="font-medium mb-3 text-gray-900">Расходы по маркету</div>
                  <div class="space-y-2 text-xs">
                    <div class="flex justify-between">
                      <span class="text-gray-600">Комиссия маркетплейса</span>
                      <span>{{ formatPrice(cab.commission_market_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Комиссия оплаты</span>
                      <span>{{ formatPrice(cab.commission_payment_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Последняя миля</span>
                      <span>{{ formatPrice(cab.last_mile_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Обработка (фиксировано)</span>
                      <span>{{ formatPrice(cab.processing_fixed_total || 0) }}</span>
                    </div>
                    <div class="flex justify-between">
                      <span class="text-gray-600">Логистика</span>
                      <span>{{ formatPrice(cab.logistics_total || 0) }}</span>
                    </div>
                    <div
                      class="border-t border-gray-200 pt-3 mt-2 flex justify-between font-medium"
                    >
                      <span class="text-gray-700">Итого расходов</span>
                      <span class="text-red-600">{{ formatPrice(cab.total_expenses || 0) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Основные показатели -->
            <div class="space-y-3 text-[13.5px]">
              <div class="flex justify-between">
                <span class="text-gray-600">Заказов</span>
                <span class="font-medium">{{ cab.total_orders }} шт</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Сумма продаж</span>
                <span class="font-medium">{{ formatPrice(cab.total_price) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Закуп</span>
                <span class="font-medium">{{ formatPrice(cab.total_purchase) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Расходы</span>
                <span class="font-medium text-red-600">{{
                  formatPrice(cab.total_expenses || 0)
                }}</span>
              </div>
              <div
                class="flex justify-between border-t pt-3"
                :style="{ borderColor: marketHex(market._id) + '55' }"
              >
                <span class="text-gray-700 font-medium">Прибыль от маркета</span>
                <span
                  class="font-bold"
                  :class="cab.total_profit > 0 ? 'text-emerald-600' : 'text-red-600'"
                  >{{ formatPrice(cab.total_profit || 0) }}</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-700 font-medium">Чистая прибыль</span>
                <span
                  class="font-bold"
                  :class="
                    cab.total_profit - cab.total_purchase > 0 ? 'text-emerald-600' : 'text-red-600'
                  "
                  >{{ formatPrice(cab.total_profit - cab.total_purchase || 0) }}</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== ПОСТАВЩИКИ ==================== -->
    <div class="card p-6 relative">
      <div
        v-if="loading"
        class="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-white/70 backdrop-blur-[2px]"
      >
        <span class="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"></span>
      </div>
      <h2 class="mb-6 text-lg font-semibold tracking-tight text-slate-900">По поставщикам</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="p in analytics?.providers"
          :key="p.provider"
          class="rounded-2xl border border-slate-200/70 bg-slate-50/60 p-5"
        >
          <div class="mb-4 text-[17px] font-semibold tracking-tight text-slate-900">{{ p._id || 'Без поставщика' }}</div>
          <div class="grid grid-cols-2 gap-y-3 text-[13.5px]">
            <div class="text-gray-600">Товаров</div>
            <div class="text-right font-medium">{{ p.total_items }}</div>
            <div class="text-gray-600">Продажи</div>
            <div class="text-right font-medium">{{ formatPrice(p.total_price) }}</div>
            <div class="text-gray-600">Закуп</div>
            <div class="text-right font-medium">{{ formatPrice(p.total_purchase) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== ТАБЛИЦА ЗАКАЗОВ ==================== -->
    <div class="card p-6 relative">
      <div
        v-if="loading"
        class="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-white/70 backdrop-blur-[2px]"
      >
        <span class="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"></span>
      </div>
      <h2 class="mb-6 text-lg font-semibold tracking-tight text-slate-900">
        Список заказов ({{ analytics?.orders_list?.length || 0 }})
      </h2>
      <div class="overflow-x-auto">
        <table class="w-full text-[14px]">
          <thead>
            <tr
              class="border-b border-slate-100 bg-slate-50/60 text-[11px] uppercase tracking-wider text-slate-400"
            >
              <th class="py-4 px-4 text-left">Дата</th>
              <th class="py-4 px-4 text-left">Заказ</th>
              <th class="py-4 px-4">Маркет</th>
              <th class="py-4 px-4">Кабинет</th>
              <th class="py-4 px-4 text-right">Сумма</th>
              <th class="py-4 px-4 text-right">Закуп</th>
              <th class="py-4 px-4 text-right">Прибыль</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr
              v-for="order in analytics?.orders_list"
              :key="order._id"
              class="border-b border-slate-100 transition-colors hover:bg-slate-50"
            >
              <td class="py-4 px-4">{{ formatDate(order.my_send_date) }}</td>
              <td class="py-4 px-4 font-mono">{{ order.order_id }}</td>
              <td class="py-4 px-4 capitalize">{{ order.market_type }}</td>
              <td class="py-4 px-4">{{ order.cabinet_name || '—' }}</td>
              <td class="py-4 px-4 text-right font-medium">{{ formatPrice(order.price) }}</td>
              <td class="py-4 px-4 text-right">{{ formatPrice(order.purchase_total) }}</td>
              <td
                class="py-4 px-4 text-right font-bold"
                :class="
                  (order.price || 0) - (order.purchase_total || 0) <= 0
                    ? 'text-red-600'
                    : 'text-emerald-600'
                "
              >
                {{ formatPrice((order.price || 0) - (order.purchase_total || 0)) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
