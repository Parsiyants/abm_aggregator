<script setup>
import { onMounted, ref, computed, watch } from 'vue'
import { useReferenceStore } from '@/stores/references'
import { useFunction } from '@/composables/function'
import MultiSelectDropdown from '@/components/MultiSelectDropdown.vue'
import DateRange from '@/components/DateRange.vue'

const props = defineProps({
  initialFilters: { type: Object, required: true },
  marketStatusOptions: { type: Array, default: () => [] },
})

const emit = defineEmits(['apply', 'reset'])

const refStore = useReferenceStore()
const { sortByIndex } = useFunction()

// Локальные данные для списков
const providers = ref([])
const statuses = ref([])
const marketplaces = ref([])
const cabinets = ref([])

// Локальные фильтры
const localFilters = ref({
  search: '',
  process_status: ['Process'],
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
})

watch(() => props.initialFilters, (newVal) => {
  if (!newVal) return
  
  localFilters.value = {
    search: newVal.search ?? '',
    process_status: newVal.process_status ?? ['Process'],
    market_type: [...(newVal.market_type ?? [])],
    market_status: [...(newVal.market_status ?? [])],
    cabinet_name: [...(newVal.cabinet_name ?? [])],
    order_date_from: newVal.order_date_from ?? '',
    order_date_to: newVal.order_date_to ?? '',
    send_date_from: newVal.send_date_from ?? '',
    send_date_to: newVal.send_date_to ?? '',
    my_send_date_from: newVal.my_send_date_from ?? '',
    my_send_date_to: newVal.my_send_date_to ?? '',
    item_status: [...(newVal.item_status ?? [])],
    item_provider: [...(newVal.item_provider ?? [])],
  }
}, { 
  immediate: true,
  deep: true 
})

function handleApply() {
  emit('apply', { ...localFilters.value })
}

function handleReset() {
  localFilters.value = {
    search: '',
    process_status: ['Process'],
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
  emit('reset')
}

// Преобразование данных из store в формат { value, label }
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

const statusOptions = computed(() =>
  statuses.value.map((s) => ({
    value: s.name,
    label: s.name,
  })),
)

const providerOptions = computed(() =>
  providers.value.map((p) => ({
    value: p.name,
    label: p.name,
  })),
)

const processOptions = [
  { value: 'Process', label: 'В Процессе' },
  { value: 'Done', label: 'Завершен' },
  { value: 'Cancel', label: 'Отменен' },
  { value: 'New', label: 'Новый' },
]

const handleKeydown = (event) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    handleApply()
  }
}

// ── Расширенные фильтры ────────────────────────────────────
const showAdvanced = ref(false)

const dateRanges = [
  { from: 'order_date_from', to: 'order_date_to', title: 'Дата заказа' },
  { from: 'send_date_from', to: 'send_date_to', title: 'Дата отгрузки' },
  { from: 'my_send_date_from', to: 'my_send_date_to', title: 'Моя дата отгрузки' },
]

const processLabels = Object.fromEntries(processOptions.map((o) => [o.value, o.label]))

function formatShortDate(value) {
  if (!value) return ''
  const d = new Date(value)
  if (isNaN(d.getTime())) return value
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

function labelOf(options, value) {
  return options.find((o) => o.value === value)?.label || value
}

// Активные фильтры в виде «чипов»
const activeFilters = computed(() => {
  const f = localFilters.value
  const chips = []

  if (f.search?.trim()) chips.push({ key: 'search', label: `«${f.search.trim()}»` })

  f.market_type.forEach((v) =>
    chips.push({ key: 'market_type', value: v, label: labelOf(marketplaceOptions.value, v) }),
  )
  f.market_status.forEach((v) =>
    chips.push({ key: 'market_status', value: v, label: labelOf(props.marketStatusOptions, v) }),
  )
  f.cabinet_name.forEach((v) => chips.push({ key: 'cabinet_name', value: v, label: v }))
  f.item_status.forEach((v) => chips.push({ key: 'item_status', value: v, label: v }))
  f.item_provider.forEach((v) => chips.push({ key: 'item_provider', value: v, label: v }))

  ;(f.process_status || [])
    .filter((v) => v !== 'Process')
    .forEach((v) => chips.push({ key: 'process_status', value: v, label: processLabels[v] || v }))

  dateRanges.forEach(({ from, to, title }) => {
    if (f[from] || f[to]) {
      chips.push({
        key: from,
        rangeTo: to,
        label: `${title}: ${formatShortDate(f[from]) || '…'} — ${formatShortDate(f[to]) || '…'}`,
      })
    }
  })

  return chips
})

// Сколько заполнено «расширенных» фильтров
const advancedCount = computed(() => {
  const f = localFilters.value
  const dateKeys = dateRanges.flatMap((r) => [r.from, r.to])

  return (
    f.item_status.length +
    f.item_provider.length +
    (f.process_status || []).filter((v) => v !== 'Process').length +
    dateKeys.filter((k) => f[k]).length
  )
})

function removeFilter(chip) {
  const f = localFilters.value

  if (chip.key === 'search') {
    f.search = ''
  } else if (chip.rangeTo) {
    f[chip.key] = ''
    f[chip.rangeTo] = ''
  } else if (Array.isArray(f[chip.key])) {
    f[chip.key] = f[chip.key].filter((v) => v !== chip.value)
  } else {
    f[chip.key] = ''
  }

  handleApply()
}

onMounted(async () => {
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
  <div class="panel p-3 sm:p-4">
    <!-- Основная строка фильтров -->
    <div class="flex flex-col gap-2.5 xl:flex-row xl:items-center">
      <!-- Поиск -->
      <div class="relative min-w-0 flex-1">
        <span
          class="material-symbols-outlined pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400"
        >
          search
        </span>
        <input
          v-model="localFilters.search"
          @keydown="handleKeydown"
          type="search"
          placeholder="Поиск по номеру заказа, товару, кабинету…"
          class="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-10 text-sm text-slate-800 outline-none transition-all placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400 focus:ring-4 focus:ring-slate-900/5"
        />
        <button
          v-if="localFilters.search"
          type="button"
          @click="localFilters.search = ''"
          class="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
        >
          <span class="material-symbols-outlined text-[16px]">close</span>
        </button>
      </div>

      <!-- Быстрые селекты -->
      <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:w-[560px]">
        <MultiSelectDropdown
          v-model="localFilters.market_type"
          :options="marketplaceOptions"
          placeholder="Маркетплейс"
          searchable
        />
        <MultiSelectDropdown
          v-model="localFilters.market_status"
          :options="props.marketStatusOptions"
          placeholder="Статус МП"
          searchable
        />
        <MultiSelectDropdown
          v-model="localFilters.cabinet_name"
          :options="cabinetOptions"
          placeholder="Кабинет"
          searchable
        />
      </div>

      <!-- Действия -->
      <div class="flex items-center gap-2 xl:ml-auto">
        <button type="button" @click="showAdvanced = !showAdvanced" class="btn-secondary">
          <span class="material-symbols-outlined text-[18px] text-slate-400">tune</span>
          <span>Ещё</span>
          <span
            v-if="advancedCount"
            class="rounded-md bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white"
          >
            {{ advancedCount }}
          </span>
          <span
            class="material-symbols-outlined text-[18px] text-slate-400 transition-transform duration-200"
            :class="{ 'rotate-180': showAdvanced }"
          >
            expand_more
          </span>
        </button>

        <button type="button" @click="handleApply" class="btn-primary flex-1 sm:flex-none">
          <span class="material-symbols-outlined text-[18px]">filter_alt</span>
          Применить
        </button>
      </div>
    </div>

    <!-- Расширенные фильтры -->
    <div v-show="showAdvanced" class="mt-4 space-y-4 border-t border-slate-100 pt-4">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <span class="field-label">Статус обработки</span>
          <MultiSelectDropdown
            v-model="localFilters.process_status"
            :options="processOptions"
            placeholder="Все процессы"
          />
        </div>
        <div>
          <span class="field-label">Статус товара</span>
          <MultiSelectDropdown
            v-model="localFilters.item_status"
            :options="statusOptions"
            placeholder="Все статусы"
            searchable
          />
        </div>
        <div>
          <span class="field-label">Поставщик</span>
          <MultiSelectDropdown
            v-model="localFilters.item_provider"
            :options="providerOptions"
            placeholder="Все поставщики"
            searchable
          />
        </div>
      </div>

      <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div v-for="range in dateRanges" :key="range.from">
          <span class="field-label">{{ range.title }}</span>
          <DateRange
            v-model:from="localFilters[range.from]"
            v-model:to="localFilters[range.to]"
          />
        </div>
      </div>
    </div>

    <!-- Активные фильтры -->
    <div
      v-if="activeFilters.length"
      class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3"
    >
      <span class="mr-1 text-xs font-medium text-slate-400">Активно:</span>

      <button
        v-for="(chip, i) in activeFilters"
        :key="`${chip.key}-${i}`"
        type="button"
        @click="removeFilter(chip)"
        class="chip group"
      >
        <span>{{ chip.label }}</span>
        <span
          class="material-symbols-outlined text-[14px] text-slate-400 transition-colors group-hover:text-slate-700"
        >
          close
        </span>
      </button>

      <button
        type="button"
        @click="handleReset"
        class="ml-1 text-xs font-medium text-slate-500 underline-offset-2 transition-colors hover:text-slate-900 hover:underline"
      >
        Сбросить всё
      </button>
    </div>
  </div>
</template>

<style scoped>
input[type='date'] {
  cursor: pointer;
}
</style>