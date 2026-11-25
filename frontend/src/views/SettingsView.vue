<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useReferenceStore } from '@/stores/references'
import { useNotificationStore } from '@/stores/notifications'
import { useFunction } from '@/composables/function'
import api from '@/services/api'

const refStore = useReferenceStore()
const notify = useNotificationStore()
const { getMarketColor } = useFunction()

// Состояние модалок
const isMarketModalOpen = ref(false)
const isCabinetModalOpen = ref(false)
const isStatusModalOpen = ref(false)
const isProviderModalOpen = ref(false)

// Состояние для миграции
const isMigrating = ref(false)
const migrationResult = ref(null)
const migrationError = ref(null)
const showMigrationResult = ref(false)

const isPolling = ref(false)
const pollResult = ref(null)

const isWbSyncing = ref(false)

// Сортировка по индексу на лету
const sortedProviders = computed(() => {
  return [...refStore.providers].sort((a, b) => a.index - b.index)
})

// Формы
const marketForm = reactive({ _id: null, name: '', slug: '', color: '#cccccc', active: true })
const cabinetForm = reactive({
  _id: null,
  market_slug: '',
  name: '',
  api_key: '',
  client_id: '',
  suffix: '',
  business_id: '',
  model: 'FBS',
  active: true,
})
const statusForm = reactive({
  _id: null,
  name: '',
  code: '',
  color: '#999999',
  index: 10,
  active: true,
})
const providerForm = reactive({
  _id: null,
  name: '',
  index: 10,
  active: true,
})

onMounted(() => {
  refStore.fetchAll('marketplaces')
  refStore.fetchAll('cabinets')
  refStore.fetchAll('statuses')
  refStore.fetchAll('providers')
})

// ── Миграция статусов ──────────────────────────────────────
const runStatusMigration = async () => {
  if (isMigrating.value) return

  isMigrating.value = true
  migrationError.value = null
  migrationResult.value = null
  showMigrationResult.value = false

  try {
    const response = await api.post('/orders/fix/statuses')
    migrationResult.value = response.data
    showMigrationResult.value = true

    if (response.data.fixed > 0) {
      notify.add(`Исправлено ${response.data.fixed} заказов`, 'success')
    } else {
      notify.add('Все статусы уже корректны', 'info')
    }
  } catch (error) {
    migrationError.value = error.response?.data?.detail || 'Ошибка при миграции статусов'
    notify.add('Ошибка при миграции статусов', 'error')
    console.error('Migration error:', error)
  } finally {
    isMigrating.value = false
  }
}

// ── Миграция цен WB ────────────────────────────────────────
const runWbPriceMigration = async () => {
  if (isMigrating.value) return

  isMigrating.value = true
  migrationError.value = null
  migrationResult.value = null
  showMigrationResult.value = false

  try {
    const response = await api.post('/orders/migrate/wb-prices')
    migrationResult.value = response.data
    showMigrationResult.value = true

    if (response.data.orders_updated > 0 || response.data.items_updated > 0) {
      notify.add(`Обновлено ${response.data.orders_updated} заказов и ${response.data.items_updated} товаров WB`, 'success')
    } else {
      notify.add('Цены WB уже корректны', 'info')
    }
  } catch (error) {
    migrationError.value = error.response?.data?.detail || 'Ошибка при миграции цен WB'
    notify.add('Ошибка при миграции цен WB', 'error')
    console.error('Migration error:', error)
  } finally {
    isMigrating.value = false
  }
}

// Запуск поллера
const runPolling = async (cabinetId = null) => {
  if (isPolling.value) return
  
  isPolling.value = true
  pollResult.value = null
  
  try {
    const url = cabinetId 
      ? `/orders/poller/run/${cabinetId}` 
      : '/orders/poller/run'
    
    const response = await api.post(url)
    pollResult.value = response.data
    
    notify.add(
      `✅ Поллинг завершён: создано ${response.data.total_created}, обновлено ${response.data.total_updated}`,
      'success'
    )
  } catch (error) {
    notify.add('❌ Ошибка при запуске поллинга', 'error')
  } finally {
    isPolling.value = false
  }
}

// Функция ручного запуска
const runWbSync = async () => {
  if (isWbSyncing.value) return
  
  isWbSyncing.value = true
  
  try {
    const response = await api.post('/sync/wb/run')
    const data = response.data
    
    if (data.success) {
      notify.add(
        `✅ WB синхронизирован: цены ${data.total_prices_updated}, остатки ${data.total_stocks_updated}`,
        'success'
      )
    } else {
      notify.add(
        `⚠️ WB: ошибки в ${data.errors.length} кабинетах. См. логи.`,
        'error'
      )
    }
  } catch (error) {
    notify.add('❌ Ошибка синхронизации WB', 'error')
    console.error('WB sync error:', error)
  } finally {
    isWbSyncing.value = false
  }
}

// ── Закрыть результат ──────────────────────────────────────
const closeMigrationResult = () => {
  showMigrationResult.value = false
  migrationResult.value = null
  migrationError.value = null
}

// Следующий свободный индекс для новых элементов
const nextIndex = (list) =>
  list.reduce((max, item) => Math.max(max, Number(item.index) || 0), 0) + 1

// ── CRUD ────────────────────────────────────────────────────
const confirmDelete = async (type, id) => {
  if (confirm('Вы уверены, что хотите удалить этот элемент?')) {
    await refStore.deleteItem(type, id)
    isMarketModalOpen.value = false
    isCabinetModalOpen.value = false
    isStatusModalOpen.value = false
    isProviderModalOpen.value = false
  }
}

const openMarketModal = (item = null) => {
  if (item) Object.assign(marketForm, item)
  else Object.assign(marketForm, { _id: null, name: '', slug: '', color: '#cccccc', active: true })
  isMarketModalOpen.value = true
}

const openCabinetModal = (item = null) => {
  if (item) Object.assign(cabinetForm, item)
  else
    Object.assign(cabinetForm, {
      _id: null,
      market_slug: refStore.marketplaces[0]?.slug || '',
      name: '',
      api_key: '',
      client_id: '',
      business_id: '',
      suffix: '',
      model: 'FBS',
      active: true,
    })
  isCabinetModalOpen.value = true
}

const openStatusModal = (item = null) => {
  if (item) Object.assign(statusForm, item)
  else
    Object.assign(statusForm, {
      _id: null,
      name: '',
      code: '',
      color: '#999999',
      index: nextIndex(refStore.statuses),
      active: true,
    })
  isStatusModalOpen.value = true
}

const openProviderModal = (item = null) => {
  if (item) {
    Object.assign(providerForm, item)
  } else {
    Object.assign(providerForm, {
      _id: null,
      name: '',
      index: nextIndex(refStore.providers),
      active: true,
    })
  }
  isProviderModalOpen.value = true
}

// Сохранение
const saveMarket = async () =>
  (await refStore.upsertItem('marketplaces', { ...marketForm })) &&
  (isMarketModalOpen.value = false)
const saveCabinet = async () =>
  (await refStore.upsertItem('cabinets', { ...cabinetForm })) && (isCabinetModalOpen.value = false)
const saveStatus = async () =>
  (await refStore.upsertItem('statuses', { ...statusForm })) && (isStatusModalOpen.value = false)
const saveProvider = async () =>
  (await refStore.upsertItem('providers', { ...providerForm })) &&
  (isProviderModalOpen.value = false)

const formatDate = (d) => (d ? new Date(d).toLocaleString() : '—')

// ── Вкладки ────────────────────────────────────────────────
const tabs = [
  { value: 'catalog', label: 'Маркетплейсы и кабинеты', icon: 'storefront' },
  { value: 'statuses', label: 'Статусы', icon: 'sell' },
  { value: 'providers', label: 'Поставщики', icon: 'local_shipping' },
  { value: 'tools', label: 'Сервис', icon: 'construction' },
]
const activeTab = ref('catalog')

// ── Фильтры ────────────────────────────────────────────────
const cabinetSearch = ref('')
const cabinetMarket = ref('')
const statusSearch = ref('')
const statusOnlyActive = ref(false)
const providerSearch = ref('')
const providerOnlyActive = ref(false)

const filteredCabinets = computed(() => {
  const q = cabinetSearch.value.trim().toLowerCase()
  return refStore.cabinets.filter((c) => {
    if (cabinetMarket.value && c.market_slug !== cabinetMarket.value) return false
    if (!q) return true
    return [c.name, c.suffix, c.client_id, c.business_id, c.model]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(q))
  })
})

const sortedStatuses = computed(() =>
  [...refStore.statuses].sort((a, b) => (a.index ?? 0) - (b.index ?? 0)),
)

const filteredStatuses = computed(() => {
  const q = statusSearch.value.trim().toLowerCase()
  return sortedStatuses.value.filter((s) => {
    if (statusOnlyActive.value && !s.active) return false
    if (!q) return true
    return `${s.name} ${s.code}`.toLowerCase().includes(q)
  })
})

const filteredProviders = computed(() => {
  const q = providerSearch.value.trim().toLowerCase()
  return sortedProviders.value.filter((p) => {
    if (providerOnlyActive.value && !p.active) return false
    if (!q) return true
    return p.name.toLowerCase().includes(q)
  })
})

const cabinetCount = (slug) => refStore.cabinets.filter((c) => c.market_slug === slug).length

const marketName = (slug) => refStore.marketplaces.find((m) => m.slug === slug)?.name || slug

const tabCounts = computed(() => ({
  catalog: refStore.marketplaces.length + refStore.cabinets.length,
  statuses: refStore.statuses.length,
  providers: refStore.providers.length,
  tools: null,
}))

// ── Ручная очерёдность (drag & drop) ──────────────────────
const dragId = ref(null)
const dragOverId = ref(null)
const isOrderSaving = ref(false)

const orderedLists = {
  statuses: sortedStatuses,
  providers: sortedProviders,
}

function onDragStart(item) {
  dragId.value = item._id
}

function onDragEnter(item) {
  if (item._id !== dragId.value) dragOverId.value = item._id
}

function onDragEnd() {
  dragId.value = null
  dragOverId.value = null
}

async function onDrop(type, target) {
  const list = [...orderedLists[type].value]
  const from = list.findIndex((i) => i._id === dragId.value)
  const to = list.findIndex((i) => i._id === target._id)

  onDragEnd()

  if (from < 0 || to < 0 || from === to) return

  const moved = list.splice(from, 1)[0]
  list.splice(to, 0, moved)

  await persistOrder(type, list)
}

function moveItem(type, item, direction) {
  const list = [...orderedLists[type].value]
  const index = list.findIndex((i) => i._id === item._id)
  const next = index + direction

  if (index < 0 || next < 0 || next >= list.length) return

  const moved = list.splice(index, 1)[0]
  list.splice(next, 0, moved)

  persistOrder(type, list)
}

async function persistOrder(type, list) {
  // Оптимистично обновляем index, чтобы UI не «прыгал»
  list.forEach((item, i) => {
    item.index = i + 1
  })

  isOrderSaving.value = true
  try {
    await refStore.reorderItems(
      type,
      list.map((i) => i._id),
    )
  } finally {
    isOrderSaving.value = false
  }
}
</script>

<template>
  <div class="space-y-5 pb-20">
    <!-- Заголовок -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Настройки</h1>
        <p class="mt-1 text-sm text-slate-500">Справочники, кабинеты и сервисные операции</p>
      </div>

      <span
        v-if="isOrderSaving"
        class="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 shadow-sm"
      >
        <span class="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"></span>
        Сохраняем порядок…
      </span>
    </div>

    <!-- Вкладки -->
    <div class="flex flex-wrap items-center gap-1 rounded-xl bg-slate-100/80 p-1">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        @click="activeTab = tab.value"
        class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
        :class="
          activeTab === tab.value
            ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
            : 'text-slate-500 hover:text-slate-900'
        "
      >
        <span class="material-symbols-outlined text-[18px]">{{ tab.icon }}</span>
        {{ tab.label }}
        <span
          v-if="tabCounts[tab.value] !== null"
          class="rounded-md px-1.5 py-0.5 text-[10px] font-semibold leading-none"
          :class="activeTab === tab.value ? 'bg-slate-900 text-white' : 'bg-white text-slate-500'"
        >
          {{ tabCounts[tab.value] }}
        </span>
      </button>
    </div>

    <!-- ═══════════ СЕРВИСНЫЕ ОПЕРАЦИИ ═══════════ -->
    <section v-if="activeTab === 'tools'" class="panel space-y-4 p-5">
      <div>
        <h2 class="text-[17px] font-semibold tracking-tight text-slate-900">
          Инструменты администрирования
        </h2>
        <p class="mt-0.5 text-[13px] text-slate-500">
          Исправление статусов, цен и ручной запуск синхронизации
        </p>
      </div>

      <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <button
          @click="runStatusMigration"
          :disabled="isMigrating"
          class="btn-primary"
        >
          <span
            v-if="isMigrating"
            class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
          ></span>
          <span v-else class="material-symbols-outlined text-[19px]">sync</span>
          {{ isMigrating ? 'Выполняется…' : 'Исправить статусы' }}
        </button>

        <button
          @click="runWbPriceMigration"
          :disabled="isMigrating"
          class="btn-secondary"
        >
          <span
            v-if="isMigrating"
            class="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"
          ></span>
          <span v-else class="material-symbols-outlined text-[19px] text-slate-400">payments</span>
          {{ isMigrating ? 'Выполняется…' : 'Исправить цены WB' }}
        </button>

        <button
          @click="runPolling()"
          :disabled="isPolling"
          class="btn-secondary"
        >
          <span
            v-if="isPolling"
            class="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"
          ></span>
          <span v-else class="material-symbols-outlined text-[19px] text-slate-400">play_arrow</span>
          {{ isPolling ? 'Выполняется…' : 'Запустить поллинг' }}
        </button>

        <button
          @click="runWbSync"
          :disabled="isWbSyncing"
          class="btn-secondary"
        >
          <span
            v-if="isWbSyncing"
            class="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900"
          ></span>
          <span v-else class="material-symbols-outlined text-[19px] text-slate-400">cloud_sync</span>
          {{ isWbSyncing ? 'Синхронизация…' : 'Синхронизировать WB' }}
        </button>
      </div>

      <!-- Результат миграции -->
      <div v-if="showMigrationResult && migrationResult" class="mt-1">
        <div class="space-y-3 rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
          <div class="flex items-center justify-between gap-2">
            <h4 class="text-[13px] font-semibold uppercase tracking-wider text-slate-400">
              Результат операции
            </h4>
            <button
              @click="closeMigrationResult"
              class="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white hover:text-slate-700"
            >
              <span class="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>

          <div class="grid grid-cols-2 gap-2.5 md:grid-cols-4">
            <div class="rounded-lg border border-slate-200/70 bg-white p-3 text-center">
              <p class="text-2xl font-semibold tracking-tight text-slate-900">{{ migrationResult.fixed || 0 }}</p>
              <p class="mt-0.5 text-[12px] text-slate-500">Исправлено</p>
            </div>
            <div
              v-if="migrationResult.orders_updated !== undefined"
              class="rounded-lg border border-slate-200/70 bg-white p-3 text-center"
            >
              <p class="text-2xl font-semibold tracking-tight text-slate-900">{{ migrationResult.orders_updated || 0 }}</p>
              <p class="mt-0.5 text-[12px] text-slate-500">Заказов обновлено</p>
            </div>
            <div
              v-if="migrationResult.items_updated !== undefined"
              class="rounded-lg border border-slate-200/70 bg-white p-3 text-center"
            >
              <p class="text-2xl font-semibold tracking-tight text-emerald-600">{{ migrationResult.items_updated || 0 }}</p>
              <p class="mt-0.5 text-[12px] text-slate-500">Товаров обновлено</p>
            </div>
            <div
              v-if="migrationResult.canceled_fixed !== undefined"
              class="rounded-lg border border-slate-200/70 bg-white p-3 text-center"
            >
              <p class="text-2xl font-semibold tracking-tight text-rose-600">{{ migrationResult.canceled_fixed || 0 }}</p>
              <p class="mt-0.5 text-[12px] text-slate-500">Отменённых</p>
            </div>
            <div
              v-if="migrationResult.delivered_fixed !== undefined"
              class="rounded-lg border border-slate-200/70 bg-white p-3 text-center"
            >
              <p class="text-2xl font-semibold tracking-tight text-emerald-600">{{ migrationResult.delivered_fixed || 0 }}</p>
              <p class="mt-0.5 text-[12px] text-slate-500">Доставленных</p>
            </div>
          </div>

          <p v-if="migrationResult.message" class="text-center text-[12.5px] text-slate-500">
            {{ migrationResult.message }}
          </p>
        </div>
      </div>

      <!-- Ошибка -->
      <div
        v-if="migrationError"
        class="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
      >
        <span class="material-symbols-outlined text-[18px]">error</span>
        {{ migrationError }}
      </div>

      <!-- Результат поллинга -->
      <div v-if="pollResult" class="space-y-3 rounded-xl border border-slate-200/70 bg-slate-50/60 p-4">
        <div class="grid grid-cols-2 gap-2.5 md:grid-cols-4">
          <div class="rounded-lg border border-slate-200/70 bg-white p-3 text-center">
            <p class="text-2xl font-semibold tracking-tight text-slate-900">{{ pollResult.total_created }}</p>
            <p class="mt-0.5 text-[12px] text-slate-500">Создано</p>
          </div>
          <div class="rounded-lg border border-slate-200/70 bg-white p-3 text-center">
            <p class="text-2xl font-semibold tracking-tight text-emerald-600">{{ pollResult.total_updated }}</p>
            <p class="mt-0.5 text-[12px] text-slate-500">Обновлено</p>
          </div>
          <div class="rounded-lg border border-slate-200/70 bg-white p-3 text-center">
            <p class="text-2xl font-semibold tracking-tight text-slate-900">{{ pollResult.total_cabinets }}</p>
            <p class="mt-0.5 text-[12px] text-slate-500">Кабинетов</p>
          </div>
          <div class="rounded-lg border border-slate-200/70 bg-white p-3 text-center">
            <p class="text-2xl font-semibold tracking-tight text-slate-900">{{ pollResult.duration_seconds }}s</p>
            <p class="mt-0.5 text-[12px] text-slate-500">Длительность</p>
          </div>
        </div>

        <div v-if="pollResult.errors?.length">
          <p class="text-[13px] font-semibold text-rose-600">Ошибки:</p>
          <ul class="mt-1 list-inside list-disc text-[12.5px] text-rose-600/90">
            <li v-for="(err, i) in pollResult.errors" :key="i">{{ err }}</li>
          </ul>
        </div>
      </div>
    </section>

    <!-- ═══════════ КАТАЛОГ: МАРКЕТПЛЕЙСЫ + КАБИНЕТЫ ═══════════ -->
    <template v-if="activeTab === 'catalog'">
      <section class="panel space-y-4 p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 class="text-[17px] font-semibold tracking-tight text-slate-900">Маркетплейсы</h2>
            <p class="mt-0.5 text-[13px] text-slate-500">Площадки и их цветовые схемы</p>
          </div>
          <button @click="openMarketModal()" class="btn-primary h-10 px-4">
            <span class="material-symbols-outlined text-[18px]">add</span>
            Добавить
          </button>
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <button
            v-for="m in refStore.marketplaces"
            :key="m._id"
            @click="openMarketModal(m)"
            class="group relative flex items-center justify-between gap-3 overflow-hidden rounded-xl border border-slate-200/70 bg-white p-4 text-left transition-all hover:border-slate-300 hover:shadow-[0_2px_14px_rgba(15,23,42,0.06)]"
          >
            <span
              class="absolute bottom-3 left-3 top-3 w-1.5 rounded-full"
              :style="{ backgroundColor: m.color }"
            ></span>

            <div class="min-w-0 pl-6">
              <p class="truncate text-[15px] font-semibold text-slate-900">{{ m.name }}</p>
              <p class="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                {{ m.slug }}
              </p>
              <p class="mt-1.5 text-[12.5px] text-slate-500">
                {{ cabinetCount(m.slug) }} кабинетов
              </p>
            </div>

            <div class="flex flex-col items-end gap-2">
              <span
                class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
                :class="m.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
              >
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  :class="m.active ? 'bg-emerald-500' : 'bg-slate-400'"
                ></span>
                {{ m.active ? 'Активен' : 'Выкл.' }}
              </span>
              <span
                class="material-symbols-outlined text-[18px] text-slate-300 transition-colors group-hover:text-slate-500"
              >
                edit
              </span>
            </div>
          </button>
        </div>
      </section>

      <section class="panel space-y-4 p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 class="text-[17px] font-semibold tracking-tight text-slate-900">Личные кабинеты</h2>
            <p class="mt-0.5 text-[13px] text-slate-500">Подключённые магазины и API-доступы</p>
          </div>
          <button @click="openCabinetModal()" class="btn-primary h-10 px-4">
            <span class="material-symbols-outlined text-[18px]">add_link</span>
            Подключить магазин
          </button>
        </div>

        <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-[1fr_220px]">
          <div class="relative">
            <span
              class="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
            >
              search
            </span>
            <input
              v-model="cabinetSearch"
              type="search"
              placeholder="Поиск по названию, suffix, Client ID…"
              class="input-field pl-10"
            />
          </div>

          <select v-model="cabinetMarket" class="input-field">
            <option value="">Все площадки</option>
            <option v-for="m in refStore.marketplaces" :key="m.slug" :value="m.slug">
              {{ m.name }}
            </option>
          </select>
        </div>

        <div class="overflow-x-auto rounded-xl border border-slate-200/70">
          <table class="w-full text-left text-[14px]">
            <thead>
              <tr
                class="border-b border-slate-100 bg-slate-50/60 text-[11px] uppercase tracking-wider text-slate-400"
              >
                <th class="px-4 py-3 font-medium">Магазин / Suffix</th>
                <th class="px-4 py-3 font-medium">Площадка</th>
                <th class="px-4 py-3 font-medium">Client ID</th>
                <th class="px-4 py-3 font-medium">Модель</th>
                <th class="px-4 py-3 text-right font-medium">Статус</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr
                v-for="c in filteredCabinets"
                :key="c._id"
                @click="openCabinetModal(c)"
                class="cursor-pointer transition-colors hover:bg-slate-50"
              >
                <td class="px-4 py-3.5">
                  <p class="font-semibold text-slate-800">{{ c.name }}</p>
                  <p class="mt-0.5 font-mono text-[11.5px] text-slate-400">
                    {{ c.suffix || 'no-suffix' }}
                  </p>
                </td>
                <td class="px-4 py-3.5">
                  <span
                    class="inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 text-[12.5px] font-medium"
                    :class="getMarketColor(c.market_slug).chip"
                  >
                    <span
                      class="h-1.5 w-1.5 rounded-full"
                      :style="{ backgroundColor: getMarketColor(c.market_slug).hex }"
                    ></span>
                    {{ marketName(c.market_slug) }}
                  </span>
                </td>
                <td class="px-4 py-3.5 font-mono text-[12.5px] text-slate-500">
                  {{ c.client_id || '—' }}
                </td>
                <td class="px-4 py-3.5">
                  <span
                    class="rounded-md bg-slate-100 px-2 py-0.5 text-[11.5px] font-semibold text-slate-600"
                  >
                    {{ c.model }}
                  </span>
                </td>
                <td class="px-4 py-3.5 text-right">
                  <span
                    class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
                    :class="c.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
                  >
                    <span
                      class="h-1.5 w-1.5 rounded-full"
                      :class="c.active ? 'bg-emerald-500' : 'bg-slate-400'"
                    ></span>
                    {{ c.active ? 'Активен' : 'Выкл.' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>

          <div
            v-if="!filteredCabinets.length"
            class="px-6 py-10 text-center text-sm text-slate-400"
          >
            Кабинеты не найдены
          </div>
        </div>
      </section>
    </template>

    <!-- ═══════════ СТАТУСЫ ═══════════ -->
    <section v-if="activeTab === 'statuses'" class="panel space-y-4 p-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="text-[17px] font-semibold tracking-tight text-slate-900">Статусы товаров</h2>
          <p class="mt-0.5 text-[13px] text-slate-500">
            Перетащите строку или используйте стрелки, чтобы изменить очерёдность
          </p>
        </div>
        <button @click="openStatusModal()" class="btn-primary h-10 px-4">
          <span class="material-symbols-outlined text-[18px]">add</span>
          Новый статус
        </button>
      </div>

      <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-[1fr_auto] sm:items-center">
        <div class="relative">
          <span
            class="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
          >
            search
          </span>
          <input
            v-model="statusSearch"
            type="search"
            placeholder="Поиск по названию или коду…"
            class="input-field pl-10"
          />
        </div>

        <label
          class="inline-flex h-11 cursor-pointer select-none items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3.5 text-[13px] font-medium text-slate-600 transition-colors hover:border-slate-300"
        >
          <span
            class="relative flex h-5 w-9 items-center rounded-full transition-colors"
            :class="statusOnlyActive ? 'bg-slate-900' : 'bg-slate-200'"
          >
            <span
              class="h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
              :class="statusOnlyActive ? 'translate-x-[18px]' : 'translate-x-0.5'"
            ></span>
          </span>
          Только активные
          <input type="checkbox" v-model="statusOnlyActive" class="sr-only" />
        </label>
      </div>

      <div class="space-y-2">
        <div
          v-for="(s, i) in filteredStatuses"
          :key="s._id"
          draggable="true"
          @dragstart="onDragStart(s)"
          @dragenter.prevent="onDragEnter(s)"
          @dragover.prevent
          @dragend="onDragEnd"
          @drop.prevent="onDrop('statuses', s)"
          class="group flex items-center gap-3 rounded-xl border bg-white p-3 transition-all"
          :class="[
            dragId === s._id ? 'border-slate-300 opacity-50' : 'border-slate-200/70 hover:border-slate-300',
            dragOverId === s._id ? 'ring-2 ring-slate-900/10' : '',
          ]"
        >
          <span
            class="material-symbols-outlined cursor-grab text-[20px] text-slate-300 transition-colors group-hover:text-slate-500 active:cursor-grabbing"
            title="Перетащите, чтобы изменить порядок"
          >
            drag_indicator
          </span>

          <span
            class="h-9 w-1.5 shrink-0 rounded-full"
            :style="{ backgroundColor: s.color }"
          ></span>

          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-semibold text-slate-800">{{ s.name }}</p>
            <p class="mt-0.5 truncate font-mono text-[12px] text-slate-400">{{ s.code || '—' }}</p>
          </div>

          <span
            class="hidden shrink-0 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500 sm:inline"
            title="Позиция в списке"
          >
            #{{ s.index }}
          </span>

          <span
            class="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
            :class="s.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
          >
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="s.active ? 'bg-emerald-500' : 'bg-slate-400'"
            ></span>
            {{ s.active ? 'Активен' : 'Выкл.' }}
          </span>

          <div class="flex shrink-0 items-center gap-0.5">
            <button
              @click.stop="moveItem('statuses', s, -1)"
              :disabled="i === 0"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-30"
              title="Выше"
            >
              <span class="material-symbols-outlined text-[18px]">arrow_upward</span>
            </button>
            <button
              @click.stop="moveItem('statuses', s, 1)"
              :disabled="i === filteredStatuses.length - 1"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-30"
              title="Ниже"
            >
              <span class="material-symbols-outlined text-[18px]">arrow_downward</span>
            </button>
            <button
              @click.stop="openStatusModal(s)"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900"
              title="Редактировать"
            >
              <span class="material-symbols-outlined text-[18px]">edit</span>
            </button>
          </div>
        </div>

        <div
          v-if="!filteredStatuses.length"
          class="rounded-xl border border-dashed border-slate-200 px-6 py-12 text-center text-sm text-slate-400"
        >
          Статусы не найдены
        </div>
      </div>
    </section>

    <!-- ═══════════ ПОСТАВЩИКИ ═══════════ -->
    <section v-if="activeTab === 'providers'" class="panel space-y-4 p-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 class="text-[17px] font-semibold tracking-tight text-slate-900">Поставщики</h2>
          <p class="mt-0.5 text-[13px] text-slate-500">
            Очерёдность влияет на порядок в карточках заказа
          </p>
        </div>
        <button @click="openProviderModal()" class="btn-primary h-10 px-4">
          <span class="material-symbols-outlined text-[18px]">add</span>
          Добавить поставщика
        </button>
      </div>

      <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-[1fr_auto] sm:items-center">
        <div class="relative">
          <span
            class="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
          >
            search
          </span>
          <input
            v-model="providerSearch"
            type="search"
            placeholder="Поиск по названию поставщика…"
            class="input-field pl-10"
          />
        </div>

        <label
          class="inline-flex h-11 cursor-pointer select-none items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3.5 text-[13px] font-medium text-slate-600 transition-colors hover:border-slate-300"
        >
          <span
            class="relative flex h-5 w-9 items-center rounded-full transition-colors"
            :class="providerOnlyActive ? 'bg-slate-900' : 'bg-slate-200'"
          >
            <span
              class="h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
              :class="providerOnlyActive ? 'translate-x-[18px]' : 'translate-x-0.5'"
            ></span>
          </span>
          Только активные
          <input type="checkbox" v-model="providerOnlyActive" class="sr-only" />
        </label>
      </div>

      <div class="space-y-2">
        <div
          v-for="(p, i) in filteredProviders"
          :key="p._id"
          draggable="true"
          @dragstart="onDragStart(p)"
          @dragenter.prevent="onDragEnter(p)"
          @dragover.prevent
          @dragend="onDragEnd"
          @drop.prevent="onDrop('providers', p)"
          class="group flex items-center gap-3 rounded-xl border bg-white p-3 transition-all"
          :class="[
            dragId === p._id ? 'border-slate-300 opacity-50' : 'border-slate-200/70 hover:border-slate-300',
            dragOverId === p._id ? 'ring-2 ring-slate-900/10' : '',
          ]"
        >
          <span
            class="material-symbols-outlined cursor-grab text-[20px] text-slate-300 transition-colors group-hover:text-slate-500 active:cursor-grabbing"
            title="Перетащите, чтобы изменить порядок"
          >
            drag_indicator
          </span>

          <span
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[12.5px] font-semibold text-slate-600"
            title="Позиция в списке"
          >
            {{ p.index }}
          </span>

          <p class="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800">
            {{ p.name }}
          </p>

          <span
            class="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
            :class="p.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
          >
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="p.active ? 'bg-emerald-500' : 'bg-slate-400'"
            ></span>
            {{ p.active ? 'Активен' : 'Выкл.' }}
          </span>

          <div class="flex shrink-0 items-center gap-0.5">
            <button
              @click.stop="moveItem('providers', p, -1)"
              :disabled="i === 0"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-30"
              title="Выше"
            >
              <span class="material-symbols-outlined text-[18px]">arrow_upward</span>
            </button>
            <button
              @click.stop="moveItem('providers', p, 1)"
              :disabled="i === filteredProviders.length - 1"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-30"
              title="Ниже"
            >
              <span class="material-symbols-outlined text-[18px]">arrow_downward</span>
            </button>
            <button
              @click.stop="openProviderModal(p)"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900"
              title="Редактировать"
            >
              <span class="material-symbols-outlined text-[18px]">edit</span>
            </button>
          </div>
        </div>

        <div
          v-if="!filteredProviders.length"
          class="rounded-xl border border-dashed border-slate-200 px-6 py-12 text-center text-sm text-slate-400"
        >
          Поставщики не найдены
        </div>
      </div>
    </section>

    <!-- Модалка: маркетплейс -->
    <div
      v-if="isMarketModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
    >
      <div
        class="w-full max-w-md space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_24px_60px_-20px_rgba(15,23,42,0.35)]"
      >
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-lg font-semibold tracking-tight text-slate-900">Площадка</h3>
          <label class="flex cursor-pointer items-center gap-2">
            <span class="text-xs font-medium text-slate-500">Активна</span>
            <span
              class="relative flex h-5 w-9 items-center rounded-full transition-colors"
              :class="marketForm.active ? 'bg-slate-900' : 'bg-slate-200'"
            >
              <span
                class="h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
                :class="marketForm.active ? 'translate-x-[18px]' : 'translate-x-0.5'"
              ></span>
            </span>
            <input type="checkbox" v-model="marketForm.active" class="sr-only" />
          </label>
        </div>

        <div class="space-y-3">
          <div>
            <label class="field-label">Название</label>
            <input v-model="marketForm.name" placeholder="Например, Ozon" class="input-field" />
          </div>
          <div>
            <label class="field-label">Slug</label>
            <input
              v-model="marketForm.slug"
              placeholder="ozon"
              class="input-field"
              :disabled="marketForm._id"
            />
          </div>
          <div>
            <label class="field-label">Цвет маркетплейса</label>
            <div class="flex items-center gap-3">
              <input
                v-model="marketForm.color"
                type="color"
                class="h-11 w-14 cursor-pointer rounded-lg border border-slate-200 bg-white p-1"
              />
              <span class="font-mono text-sm text-slate-500">{{ marketForm.color }}</span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 border-t border-slate-100 pt-4">
          <button
            v-if="marketForm._id"
            @click="confirmDelete('marketplaces', marketForm._id)"
            class="flex h-11 w-11 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600 transition-colors hover:bg-rose-100"
            title="Удалить площадку"
          >
            <span class="material-symbols-outlined text-[20px]">delete</span>
          </button>
          <button @click="isMarketModalOpen = false" class="btn-secondary flex-1">Отмена</button>
          <button @click="saveMarket" class="btn-primary flex-1">Сохранить</button>
        </div>
      </div>
    </div>

    <!-- Модалка: кабинет -->
    <div
      v-if="isCabinetModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
    >
      <div
        class="max-h-[92vh] w-full max-w-lg space-y-5 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_24px_60px_-20px_rgba(15,23,42,0.35)]"
      >
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-lg font-semibold tracking-tight text-slate-900">Настройки кабинета</h3>
          <label class="flex cursor-pointer items-center gap-2">
            <span class="text-xs font-medium text-slate-500">Активен</span>
            <span
              class="relative flex h-5 w-9 items-center rounded-full transition-colors"
              :class="cabinetForm.active ? 'bg-slate-900' : 'bg-slate-200'"
            >
              <span
                class="h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
                :class="cabinetForm.active ? 'translate-x-[18px]' : 'translate-x-0.5'"
              ></span>
            </span>
            <input type="checkbox" v-model="cabinetForm.active" class="sr-only" />
          </label>
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div class="sm:col-span-2">
            <label class="field-label">Имя магазина</label>
            <input v-model="cabinetForm.name" placeholder="Напр. ABMauto Ozon" class="input-field" />
          </div>
          <div class="sm:col-span-2">
            <label class="field-label">Suffix</label>
            <input v-model="cabinetForm.suffix" placeholder="ABM" class="input-field" />
          </div>
          <div>
            <label class="field-label">Площадка</label>
            <select v-model="cabinetForm.market_slug" class="input-field">
              <option v-for="m in refStore.marketplaces" :key="m.slug" :value="m.slug">
                {{ m.name }}
              </option>
            </select>
          </div>
          <div>
            <label class="field-label">Модель работы</label>
            <select v-model="cabinetForm.model" class="input-field">
              <option value="FBS">FBS</option>
              <option value="DBS">DBS</option>
              <option value="FBO">FBO</option>
              <option value="EXPRESS">EXPRESS</option>
            </select>
          </div>
          <div>
            <label class="field-label">Client ID</label>
            <input v-model="cabinetForm.client_id" placeholder="123456" class="input-field" />
          </div>
          <div>
            <label class="field-label">Business ID</label>
            <input v-model="cabinetForm.business_id" placeholder="необязательно" class="input-field" />
          </div>
          <div class="sm:col-span-2">
            <label class="field-label">API Key</label>
            <input
              v-model="cabinetForm.api_key"
              type="text"
              placeholder="Токен доступа"
              class="input-field font-mono"
            />
          </div>
        </div>

        <div class="flex items-center gap-2 border-t border-slate-100 pt-4">
          <button
            v-if="cabinetForm._id"
            @click="confirmDelete('cabinets', cabinetForm._id)"
            class="flex h-11 w-11 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600 transition-colors hover:bg-rose-100"
            title="Удалить кабинет"
          >
            <span class="material-symbols-outlined text-[20px]">delete</span>
          </button>
          <button @click="isCabinetModalOpen = false" class="btn-secondary flex-1">Отмена</button>
          <button @click="saveCabinet" class="btn-primary flex-1">Сохранить</button>
        </div>
      </div>
    </div>

    <!-- Модалка: статус -->
    <div
      v-if="isStatusModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
    >
      <div
        class="w-full max-w-md space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_24px_60px_-20px_rgba(15,23,42,0.35)]"
      >
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-lg font-semibold tracking-tight text-slate-900">Статус</h3>
          <label class="flex cursor-pointer items-center gap-2">
            <span class="text-xs font-medium text-slate-500">Активен</span>
            <span
              class="relative flex h-5 w-9 items-center rounded-full transition-colors"
              :class="statusForm.active ? 'bg-slate-900' : 'bg-slate-200'"
            >
              <span
                class="h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
                :class="statusForm.active ? 'translate-x-[18px]' : 'translate-x-0.5'"
              ></span>
            </span>
            <input type="checkbox" v-model="statusForm.active" class="sr-only" />
          </label>
        </div>

        <div class="space-y-3">
          <div>
            <label class="field-label">Название</label>
            <input v-model="statusForm.name" placeholder="Напр. В наличии" class="input-field" />
          </div>
          <div>
            <label class="field-label">Код</label>
            <input
              v-model="statusForm.code"
              placeholder="ready"
              class="input-field font-mono"
              :disabled="statusForm._id"
            />
          </div>
          <div class="grid grid-cols-[1fr_110px] gap-3">
            <div>
              <label class="field-label">Цвет</label>
              <div class="flex items-center gap-3">
                <input
                  v-model="statusForm.color"
                  type="color"
                  class="h-11 w-14 cursor-pointer rounded-lg border border-slate-200 bg-white p-1"
                />
                <span class="font-mono text-sm text-slate-500">{{ statusForm.color }}</span>
              </div>
            </div>
            <div>
              <label class="field-label">Позиция</label>
              <input v-model="statusForm.index" type="number" class="input-field" />
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 border-t border-slate-100 pt-4">
          <button
            v-if="statusForm._id"
            @click="confirmDelete('statuses', statusForm._id)"
            class="flex h-11 w-11 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600 transition-colors hover:bg-rose-100"
            title="Удалить статус"
          >
            <span class="material-symbols-outlined text-[20px]">delete</span>
          </button>
          <button @click="isStatusModalOpen = false" class="btn-secondary flex-1">Отмена</button>
          <button @click="saveStatus" class="btn-primary flex-1">Сохранить</button>
        </div>
      </div>
    </div>

    <!-- Модалка: поставщик -->
    <div
      v-if="isProviderModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
    >
      <div
        class="w-full max-w-md space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_24px_60px_-20px_rgba(15,23,42,0.35)]"
      >
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-lg font-semibold tracking-tight text-slate-900">Данные поставщика</h3>
          <label class="flex cursor-pointer items-center gap-2">
            <span class="text-xs font-medium text-slate-500">Активен</span>
            <span
              class="relative flex h-5 w-9 items-center rounded-full transition-colors"
              :class="providerForm.active ? 'bg-slate-900' : 'bg-slate-200'"
            >
              <span
                class="h-4 w-4 rounded-full bg-white shadow-sm transition-transform"
                :class="providerForm.active ? 'translate-x-[18px]' : 'translate-x-0.5'"
              ></span>
            </span>
            <input type="checkbox" v-model="providerForm.active" class="sr-only" />
          </label>
        </div>

        <div class="space-y-3">
          <div>
            <label class="field-label">Название организации</label>
            <input v-model="providerForm.name" placeholder="Напр. ООО Вектор" class="input-field" />
          </div>
          <div>
            <label class="field-label">Позиция в списке</label>
            <input v-model="providerForm.index" type="number" class="input-field max-w-[140px]" />
          </div>
        </div>

        <div class="flex items-center gap-2 border-t border-slate-100 pt-4">
          <button
            v-if="providerForm._id"
            @click="confirmDelete('providers', providerForm._id)"
            class="flex h-11 w-11 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-600 transition-colors hover:bg-rose-100"
            title="Удалить поставщика"
          >
            <span class="material-symbols-outlined text-[20px]">delete</span>
          </button>
          <button @click="isProviderModalOpen = false" class="btn-secondary flex-1">Отмена</button>
          <button @click="saveProvider" class="btn-primary flex-1">Сохранить</button>
        </div>
      </div>
    </div>
  </div>
</template>