<script setup>
import { useAppStore } from '@/stores/app'
import { useFunction } from '@/composables/function'
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useReferenceStore } from '@/stores/references'
import { useOrdersStore } from '@/stores/orders'
import { RouterLink } from 'vue-router'

const props = defineProps({
  order: { type: Object, required: true },
})
const { formatPrice, copy, formatDate, getRussianStatus, getStatusDescription, getStatusBadgeClasses, getProcessStatus, getSubstatusLabel, sortByIndex } = useFunction()
const app = useAppStore()
const ordersStore = useOrdersStore()
const refStore = useReferenceStore()

const statuses = computed(() => sortByIndex(refStore.statuses))
const showStatusDropdown = ref({})
const showAnalytics = ref(false)

const order = ref(props.order)

// Следим за изменениями в сторе
watch(
  () => ordersStore.orders.items.find(o => o._id === props.order._id),
  (updatedOrder) => {
    if (updatedOrder) {
      order.value = updatedOrder
    }
  },
  { deep: true }
)

// Computed для статуса товара
const getItemStatus = (item) =>
  computed(() => {
    return app.updatesItemsList.get(item._id) ?? item.status
  })

const getItemColor = (status) =>
  computed(() => {
    if (!status?.value) return '#6b7280'
    const statusObj = statuses.value.find((s) => s.code === status.value || s.name === status.value)
    return statusObj?.color || '#6b7280'
  })

const isItemStatusChanged = (item) =>
  computed(
    () => app.updatesItemsList.has(item._id) && app.updatesItemsList.get(item._id) !== item.status,
  )

const toggleItemStatus = (item, new_status, index) => {
  item.status === new_status
    ? app.updatesItemsList.delete(item._id)
    : app.updatesItemsList.set(item._id, new_status)
  showStatusDropdown.value[index] = false
}

// Computed для чекбокса
const isSelected = computed(() => {
  return ordersStore.isOrderSelected(order.value.order_id)
})

const toggleSelection = () => {
  ordersStore.toggleOrderSelection({
    cabinet_id: order.value.cabinet_info?._id || order.value.cabinet_id,
    order_id: order.value.order_id,
    market_type: order.value.market_type,
    status: order.value.market_status,
  })
}

// ── Можно ли печатать этикетку ─────────────────────────────
const canPrint = computed(() => {
  if (!order.value) return false
  const printableStatuses = ['awaiting_deliver', 'awaiting_packaging']
  

  if (order.value.market_type === 'wb') return false
  else if (order.value.market_type === 'yandex') return true
  else return printableStatuses.includes(order.value.market_status)
})

// Форматирование для аналитики
const formatAnalytics = (value) => {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(value)
}

// Чистая прибыль = profit - закуп
const totalPurchase = computed(() => {
  return order.items?.reduce((sum, item) => sum + (item.purchase || 0) * (item.count || 1), 0) || 0
})

const netProfit = computed(() => {
  return (order.analytics?.profit || 0) - totalPurchase.value
})

// Текст для title у цены
const getPriceTitle = (item) => {
  if (item.count > 1) {
    const perOne = item.price / item.count
    return `Цена за все: ${formatPrice(item.price)}\nЦена за 1 шт: ${formatPrice(perOne)}`
  }
  return `Цена: ${formatPrice(item.price)}`
}

const getPurchaseTitle = (item) => {
  if (!item.purchase) return 'Закуп не указан'
  if (item.count > 1) {
    const perOne = item.purchase / item.count
    return `Закуп за все: ${formatPrice(item.purchase)}\nЗакуп за 1 шт: ${formatPrice(perOne)}`
  }
  return `Закуп: ${formatPrice(item.purchase)}`
}

const toggleDropdown = (index) => {
  showStatusDropdown.value[index] = !showStatusDropdown.value[index]
}

// Цветовые схемы маркетплейсов (статичные классы — чтобы Tailwind их собрал)
const MARKET_THEME = {
  ozon: {
    bar: 'bg-blue-500',
    dot: 'bg-blue-500',
    chip: 'border-blue-200 bg-blue-50 text-blue-700',
  },
  yandex: {
    bar: 'bg-amber-400',
    dot: 'bg-amber-400',
    chip: 'border-amber-200 bg-amber-50 text-amber-700',
  },
  wb: {
    bar: 'bg-purple-500',
    dot: 'bg-purple-500',
    chip: 'border-purple-200 bg-purple-50 text-purple-700',
  },
  avito: {
    bar: 'bg-emerald-500',
    dot: 'bg-emerald-500',
    chip: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
}

const FALLBACK_THEME = {
  bar: 'bg-slate-400',
  dot: 'bg-slate-400',
  chip: 'border-slate-200 bg-slate-100 text-slate-600',
}

// Тема текущего маркетплейса
const marketTheme = computed(() => MARKET_THEME[order.value.market_type] || FALLBACK_THEME)

onMounted(() => {
  if (!refStore.statuses.length) refStore.fetchAll('statuses')

  window.addEventListener('click', (e) => {
    if (!e.target.closest('.status-dropdown') && !e.target.closest('.status-button')) {
      showStatusDropdown.value = {}
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('click', () => {})
})
</script>

<template>
  <div
    class="panel group relative p-0 transition-all duration-200 hover:shadow-[0_10px_30px_-16px_rgba(15,23,42,0.22)]"
  >
    <!-- Цветная полоса маркетплейса -->
    <span
      class="absolute bottom-4 left-3 top-4 w-0.75 rounded-full"
      :class="marketTheme.bar"
    ></span>

    <div class="pl-7 sm:pl-8">
      <!-- Верхняя строка: ID + статусы + даты -->
      <div
        class="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-slate-100 py-4 pr-5 sm:pr-6"
      >
        <!-- Левая часть: Чекбокс + ID + статусы -->
        <div class="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-2">
          <!-- Чекбокс -->
          <input
            v-if="canPrint"
            type="checkbox"
            :checked="isSelected"
            @change="toggleSelection"
            class="h-[18px] w-[18px] shrink-0 cursor-pointer rounded border-slate-300 accent-slate-900"
            title="Выбрать для печати этикетки"
          />

          <!-- Копирование ID -->
          <div class="flex items-center gap-1">
            <button
              @click="copy(order.order_id)"
              class="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              title="Копировать номер заказа"
            >
              <span class="material-symbols-outlined text-[19px]">content_copy</span>
            </button>

            <span class="text-[17px] font-semibold tracking-tight text-slate-900" title="Номер заказа">{{
              order.order_id
            }}</span>
          </div>

          <!-- Кабинет -->
          <span
            class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[13px] font-medium"
            :class="marketTheme.chip"
            :title="`Кабинет: ${order.cabinet_name}`"
          >
            <span class="h-2 w-2 rounded-full" :class="marketTheme.dot"></span>
            {{ order.cabinet_name }}
          </span>

          <!-- Модель -->
          <span
            v-if="order.cabinet_info?.model"
            class="rounded-lg bg-slate-100 px-2.5 py-1 text-[13px] font-medium text-slate-600"
            :title="`Модель: ${order.cabinet_info.model}`"
          >
            {{ order.cabinet_info.model }}
          </span>

          <!-- Статус МП -->
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

          <!-- Детализированный статус МП (Ozon substatus) -->
          <span
            v-if="order.substatus"
            class="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[13px] font-medium text-slate-600"
            :title="`Детализированный статус: ${order.substatus}`"
          >
            {{ getSubstatusLabel(order.substatus) }}
          </span>

          <!-- Process Status -->
          <span
            class="rounded-lg px-2.5 py-1 text-[13px] font-semibold"
            :class="getProcessStatus(order.process_status).color"
            :title="`Статус обработки: ${getProcessStatus(order.process_status).label}`"
          >
            {{ getProcessStatus(order.process_status).label }}
          </span>

          <!-- Отмена -->
          <span
            v-if="order.cancellation_type"
            class="inline-flex items-center gap-1 rounded-lg bg-rose-50 px-2.5 py-1 text-[13px] font-semibold text-rose-600"
            :title="`Инициатор отмены: ${order.cancellation_type === 'seller' ? 'Продавец' : 'Клиент'}`"
          >
            <span class="material-symbols-outlined text-[16px]">block</span>
            {{ order.cancellation_type === 'seller' ? 'Отмена (мы)' : 'Отмена (клиент)' }}
          </span>
        </div>

        <!-- Правая часть: Даты -->
        <div
          class="flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1.5 text-[13px] text-slate-500"
        >
          <span class="flex items-center gap-1.5" title="Дата создания заказа">
            <span class="material-symbols-outlined text-[17px] text-slate-400">calendar_today</span>
            <span class="font-medium text-slate-700">{{ formatDate(order.order_date) }}</span>
          </span>
          <span class="flex items-center gap-1.5" title="Дата отгрузки">
            <span class="material-symbols-outlined text-[17px] text-slate-400">local_shipping</span>
            <span class="font-medium text-slate-700">{{ formatDate(order.send_date, true) }}</span>
          </span>
          <span class="flex items-center gap-1.5" title="Наша дата отгрузки">
            <span class="material-symbols-outlined text-[17px] text-slate-400">event_note</span>
            <span class="font-medium text-slate-700">{{ formatDate(order.my_send_date, true) }}</span>
          </span>
        </div>
      </div>

      <!-- Товары -->
      <div class="space-y-3 py-4 pr-5 sm:pr-6">
        <div
          v-for="(item, index) in order.items"
          :key="item._id || index"
          class="rounded-xl border border-slate-200/70 bg-slate-50/60 p-3.5"
        >
          <!-- Артикул + Название -->
          <div class="flex items-start gap-2">
            <button
              @click="copy(item.article)"
              class="mt-0.5 flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-white hover:text-slate-700"
              title="Копировать артикул"
            >
              <span class="material-symbols-outlined text-[17px]">content_copy</span>
            </button>

            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-mono text-[15px] font-semibold text-slate-800" title="Артикул товара">
                  {{ item.article }}
                </span>

                <!-- Поставщик -->
                <span
                  class="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[12.5px] font-medium"
                  :class="
                    item.provider
                      ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                      : 'border-slate-200 bg-white text-slate-500'
                  "
                  :title="`Поставщик: ${item.provider}`"
                >
                  <span class="material-symbols-outlined text-[14px]">business</span>
                  {{ item.provider || 'без поставщика' }}
                </span>
              </div>

              <p
                class="mt-1 break-words text-sm leading-snug text-slate-600"
                title="Название товара"
              >
                {{ item.name }}
              </p>
            </div>
          </div>

          <!-- Информация о товаре -->
          <div class="mt-3 flex flex-wrap items-center gap-2.5">
            <!-- Количество, Цена, Закуп -->
            <div
              class="flex items-center divide-x divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white text-[13px]"
            >
              <span class="px-3 py-1.5 text-slate-500" title="Количество">
                Кол-во <b class="font-semibold text-slate-800">{{ item.count }}</b>
              </span>
              <span class="px-3 py-1.5 text-slate-500" :title="getPriceTitle(item)">
                Цена <b class="font-semibold text-slate-800">{{ formatPrice(item.price) }}</b>
              </span>
              <span class="px-3 py-1.5 text-slate-500" :title="getPurchaseTitle(item)">
                Закуп
                <b :class="item.purchase ? 'text-emerald-600' : 'text-slate-400'">
                  {{ item.purchase ? formatPrice(item.purchase) : '—' }}
                </b>
              </span>
            </div>

            <!-- Статус товара -->
            <div class="relative flex items-center rounded-lg border border-slate-200 bg-white">
              <span
                :style="{ backgroundColor: getItemColor(getItemStatus(item)).value }"
                class="flex h-8 items-center rounded-l-[7px] px-3 text-[13px] font-medium text-white"
                :title="`Текущий статус товара: ${getItemStatus(item) || '—'}`"
              >
                {{ getItemStatus(item) || '—' }}
              </span>
              <button
                @click.stop="toggleDropdown(index)"
                :style="{ backgroundColor: getItemColor(getItemStatus(item)).value }"
                class="status-button flex h-8 w-7 cursor-pointer items-center justify-center rounded-r-[7px] text-white"
                title="Изменить статус товара"
              >
                <span class="material-symbols-outlined text-[18px]">keyboard_arrow_down</span>
              </button>

              <!-- Выпадашка статусов -->
              <Transition name="slide-up">
                <div
                  v-if="showStatusDropdown[index]"
                  class="status-dropdown absolute right-0 top-full z-30 mt-1.5 min-w-[170px] rounded-xl border border-slate-200 bg-white py-1.5 shadow-[0_16px_40px_-12px_rgba(15,23,42,0.28)]"
                >
                  <button
                    v-for="status in statuses"
                    :key="status._id"
                    @click.stop="toggleItemStatus(item, status.name, index)"
                    class="flex w-full items-center gap-2.5 whitespace-nowrap px-3.5 py-2 text-sm transition-colors hover:bg-slate-50"
                    :title="`Установить статус: ${status.name}`"
                  >
                    <div
                      class="h-3.5 w-3.5 shrink-0 rounded"
                      :style="{ backgroundColor: status?.color || '#6b7280' }"
                    ></div>
                    <span class="text-slate-700">{{ status?.name }}</span>
                  </button>
                </div>
              </Transition>
            </div>

            <!-- Кнопка отмены изменения статуса -->
            <button
              v-if="isItemStatusChanged(item).value"
              @click="toggleItemStatus(item, item.status, index)"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-rose-500 transition-colors hover:bg-rose-50 hover:text-rose-600"
              title="Отменить изменение статуса"
            >
              <span class="material-symbols-outlined text-[18px]">undo</span>
            </button>
          </div>
        </div>

        <!-- Комментарий к заказу -->
        <div
          v-if="order.comment"
          class="flex items-start gap-2.5 rounded-xl border border-amber-200/70 bg-amber-50/60 px-3.5 py-2.5 text-[13px]"
        >
          <span class="material-symbols-outlined mt-0.5 text-[17px] text-amber-500">comment</span>
          <span class="break-words font-medium text-amber-900" title="Комментарий к заказу">
            {{ order.comment }}
          </span>
        </div>
      </div>

      <!-- Нижняя часть: цена + кнопки -->
      <div
        class="flex flex-col gap-3 border-t border-slate-100 py-4 pr-5 sm:flex-row sm:items-center sm:justify-between sm:pr-6"
      >
        <div class="flex items-baseline gap-2.5">
          <span class="text-sm text-slate-400">Сумма</span>
          <span
            class="text-2xl font-semibold tracking-tight text-slate-900"
            title="Общая сумма заказа"
          >
            {{ formatPrice(order.price) }}
          </span>
          <span class="text-[13px] font-medium text-slate-400" title="Количество позиций в заказе">
            · {{ order.order_count || 0 }} поз.
          </span>
        </div>

        <div class="flex items-center gap-2 self-end sm:self-auto">
          <!-- Редактировать -->
          <button
            @click="app.openHandleOrderModal(order)"
            class="inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3.5 text-[13px] font-medium text-indigo-700 transition-all hover:bg-indigo-100 active:scale-95"
            title="Редактировать заказ"
          >
            <span class="material-symbols-outlined text-[18px]">edit_note</span>
            <span class="hidden sm:inline">Редактировать</span>
          </button>

          <!-- Просмотр -->
          <RouterLink
            :to="`/orders/${order._id}`"
            target="_blank"
            class="flex h-10 w-10 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900"
            title="Подробная информация о заказе"
          >
            <span class="material-symbols-outlined text-[21px]">visibility</span>
          </RouterLink>

          <!-- Аналитика -->
          <button
            @click="showAnalytics = !showAnalytics"
            class="flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg transition-colors"
            :class="
              showAnalytics
                ? 'bg-emerald-50 text-emerald-600'
                : 'text-slate-400 hover:bg-emerald-50 hover:text-emerald-600'
            "
            :title="showAnalytics ? 'Скрыть аналитику' : 'Показать аналитику'"
          >
            <span class="material-symbols-outlined text-[21px]">bar_chart</span>
          </button>
        </div>
      </div>

      <!-- Аналитика -->
      <div
        v-if="showAnalytics"
        class="mb-4 mr-5 rounded-xl border border-slate-200/70 bg-slate-50/60 p-4 sm:mr-6"
      >
        <div
          class="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400"
        >
          <span class="material-symbols-outlined text-[15px]">receipt_long</span>
          Расходы по заказу
        </div>
        <div class="grid grid-cols-2 gap-2 text-[13px] sm:grid-cols-3 sm:text-sm">
          <div
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5"
          >
            <span class="text-slate-500">Комиссия МП</span>
            <span class="font-semibold text-gray-800">{{
              formatAnalytics(order.analytics?.commission_market_total)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5"
          >
            <span class="text-slate-500">Комиссия оплаты</span>
            <span class="font-semibold text-gray-800">{{
              formatAnalytics(order.analytics?.commission_payment_total)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5"
          >
            <span class="text-slate-500">Последняя миля</span>
            <span class="font-semibold text-gray-800">{{
              formatAnalytics(order.analytics?.last_mile_total)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5"
          >
            <span class="text-slate-500">Логистика</span>
            <span class="font-semibold text-gray-800">{{
              formatAnalytics(order.analytics?.logistics_total)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5"
          >
            <span class="text-slate-500">Обработка</span>
            <span class="font-semibold text-gray-800">{{
              formatAnalytics(order.analytics?.processing_fixed)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white px-2.5 py-1.5"
          >
            <span class="text-slate-500">Штраф</span>
            <span class="font-semibold text-rose-600">{{
              formatAnalytics(order.analytics?.penalty)
            }}</span>
          </div>
        </div>

        <!-- Итоги -->
        <div
          class="mt-3 grid grid-cols-1 gap-2 border-t border-slate-200/70 pt-3 sm:grid-cols-3 sm:gap-3"
        >
          <div
            class="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2.5"
          >
            <span class="text-[13px] font-semibold text-slate-600 sm:text-sm">Итого расходов</span>
            <span class="text-base font-bold text-rose-600 sm:text-lg">{{
              formatAnalytics(order.analytics?.total_expenses)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5"
          >
            <span class="text-[13px] font-semibold text-slate-600 sm:text-sm">Прибыль</span>
            <span class="text-base font-bold text-emerald-600 sm:text-lg">{{
              formatAnalytics(order.analytics?.profit)
            }}</span>
          </div>
          <div
            class="flex items-center justify-between rounded-lg border border-violet-200 bg-violet-50 px-3.5 py-2.5"
          >
            <span class="text-[13px] font-semibold text-slate-600 sm:text-sm">Чистая прибыль</span>
            <span
              class="text-base font-bold sm:text-lg"
              :class="netProfit >= 0 ? 'text-violet-600' : 'text-rose-600'"
            >
              {{ formatAnalytics(netProfit) }}
            </span>
          </div>
        </div>
        <div
          class="mt-2.5 text-center text-[11px] text-slate-400 sm:text-xs"
          title="Прибыль минус закупка товаров"
        >
          * чистая прибыль = прибыль − закупка товаров
        </div>
      </div>
    </div>
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

input[type='checkbox'] {
  border-radius: 4px;
}

/* Адаптация для мобильных */
@media (max-width: 480px) {
  .status-badge {
    font-size: 10px !important;
    padding: 2px 6px !important;
  }
}
</style>
