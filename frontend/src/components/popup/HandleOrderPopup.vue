<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useOrdersStore } from '@/stores/orders'
import { useReferenceStore } from '@/stores/references'
import { useNotificationStore } from '@/stores/notifications'
import { useFunction } from '@/composables/function'

const app = useAppStore()
const ordersStore = useOrdersStore()
const refStore = useReferenceStore()
const notification = useNotificationStore()

const { formatPrice, copy, formatDate, getRussianStatus, getStatusDescription, getStatusBadgeClasses, getProcessStatus, getMarketColor, sortByIndex } = useFunction()

const loading = ref(false)
const saving = ref(false)
const error = ref(null)

// Справочники
const statuses = ref([])
const providers = ref([])

// Форма
const form = ref({
  my_send_date: null,
  comment: null,
  items: [],
})

const validationErrors = ref({})


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

// ── Заполнение формы при открытии ─────────────────────────
watch(
  () => app.selectedOrder,
  (order) => {
    if (!order) {
      form.value = { my_send_date: null, comment: null, items: [] }
      error.value = null
      return
    }

    loading.value = true
    error.value = null

    try {
      form.value.my_send_date = order.my_send_date
        ? new Date(order.my_send_date).toISOString().split('T')[0]
        : null

      form.value.comment = order.comment || ''

      form.value.items = (order.items || []).map((item) => ({
        item_id: item._id,
        article: item.article || '',
        price: item.price || 0,
        name: item.name || 'Товар',
        count: item.count || 1,
        purchase: item.purchase || null,
        provider: item.provider || '',
        status: item.status || '',
      }))
    } catch (err) {
      error.value = 'Ошибка загрузки данных заказа'
      console.error(err)
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

// ── Валидация ──────────────────────────────────────────────
const isFormValid = computed(() => {
  validationErrors.value = {}
  let valid = true

  if (!form.value.my_send_date?.trim()) {
    validationErrors.value['my_send_date'] = 'Укажите дату отгрузки'
    valid = false
  }

  form.value.items.forEach((item, i) => {
    if (!item.purchase || item.purchase <= 0) {
      validationErrors.value[`items.${i}.purchase`] = 'Укажите цену закупки > 0'
      valid = false
    }
    if (!item.provider?.trim()) {
      validationErrors.value[`items.${i}.provider`] = 'Выберите поставщика'
      valid = false
    }
    if (!item.status?.trim()) {
      validationErrors.value[`items.${i}.status`] = 'Выберите статус'
      valid = false
    }
  })

  return valid
})

// ── Действия ──────────────────────────────────────────────
function close() {
  app.closeHandleOrderModal()
}

async function save() {
  if (!isFormValid.value) return

  saving.value = true
  error.value = null

  const payload = {
    my_send_date: form.value.my_send_date
      ? new Date(form.value.my_send_date).toISOString()
      : null,
    comment: form.value.comment?.trim() || null,
    items: form.value.items.map((item) => ({
      item_id: item.item_id,
      purchase: item.purchase,
      provider: item.provider.trim(),
      status: item.status.trim(),
    })),
  }

  try {
    const result = await ordersStore.handleOrder(
      app.selectedOrder._id || app.selectedOrder.id,
      payload,
      app.selectedOrder.order_id
    )

    if (result.success) {
      close()
    } else {
      error.value = result.message || 'Ошибка при обработке'
      notification.add(error.value, 'error')
    }
  } catch (err) {
    error.value = 'Не удалось сохранить изменения'
    notification.add(error.value, 'error')
  } finally {
    saving.value = false
  }
}

// ── Загрузка справочников ─────────────────────────────────
onMounted(async () => {
  if (!refStore.statuses.length) await refStore.fetchAll('statuses')
  if (!refStore.providers.length) await refStore.fetchAll('providers')

  statuses.value = sortByIndex(refStore.statuses)
  providers.value = sortByIndex(refStore.providers)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-250"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="app.handleOrderPopup"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
        @click.self="close"
      >
        <Transition
          enter-active-class="transition-all duration-350 ease-out"
          enter-from-class="translate-y-12 scale-[0.90] opacity-0"
          enter-to-class="translate-y-0 scale-100 opacity-100"
          leave-active-class="transition-all duration-250 ease-in"
          leave-from-class="translate-y-0 scale-100 opacity-100"
          leave-to-class="translate-y-8 scale-[0.95] opacity-0"
        >
          <div
            v-if="app.handleOrderPopup"
            class="relative flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_32px_80px_-24px_rgba(15,23,42,0.45)]"
          >
            <!-- Header -->
            <div class="flex items-center justify-between gap-4 border-b border-slate-100 px-6 py-4">
              <div class="min-w-0">
                <h2 class="text-[19px] font-semibold tracking-tight text-slate-900">
                  {{ app.selectedOrder?.my_send_date ? 'Редактирование заказа' : 'Обработка заказа' }}
                </h2>
                <p class="mt-0.5 text-[13px] text-slate-500">
                  Укажите закуп, поставщика и статус по каждой позиции
                </p>
              </div>
              <button
                @click="close"
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              >
                <span class="material-symbols-outlined text-[21px]">close</span>
              </button>
            </div>

            <!-- Body -->
            <div class="flex-1 space-y-5 overflow-y-auto px-6 py-5">
              <!-- Состояние загрузки -->
              <div v-if="loading" class="flex flex-col items-center justify-center gap-3 py-16">
                <span
                  class="h-9 w-9 animate-spin rounded-full border-[3px] border-slate-200 border-t-slate-900"
                ></span>
                <span class="text-sm text-slate-500">Загрузка данных…</span>
              </div>

              <!-- Ошибка -->
              <div
                v-else-if="error"
                class="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
              >
                <span class="material-symbols-outlined text-[18px]">error</span>
                {{ error }}
              </div>

              <!-- Контент -->
              <template v-else-if="app.selectedOrder">
                <!-- Информация о заказе -->
                <div class="relative overflow-hidden rounded-xl border border-slate-200/70 bg-slate-50/60 p-4 pl-6">
                  <span
                    class="absolute bottom-4 left-2.5 top-4 w-1 rounded-full"
                    :style="{ backgroundColor: getMarketColor(app.selectedOrder.market_type).hex }"
                  ></span>

                  <div class="mb-3 flex flex-wrap items-center gap-2.5">
                    <div class="flex items-center gap-1">
                      <button
                        @click="copy(app.selectedOrder.order_id)"
                        class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white hover:text-slate-700"
                        title="Копировать номер"
                      >
                        <span class="material-symbols-outlined text-[19px]">content_copy</span>
                      </button>
                      <span class="text-[17px] font-semibold tracking-tight text-slate-900" title="Номер заказа">
                        {{ app.selectedOrder.order_id }}
                      </span>
                    </div>

                    <span
                      class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[13px] font-medium"
                      :title="`Кабинет: ${app.selectedOrder.cabinet_name}`"
                      :class="getMarketColor(app.selectedOrder.market_type).chip"
                    >
                      <span
                        class="h-2 w-2 rounded-full"
                        :style="{ backgroundColor: getMarketColor(app.selectedOrder.market_type).hex }"
                      ></span>
                      {{ app.selectedOrder.cabinet_name }}
                    </span>

                    <span
                      v-if="app.selectedOrder.cabinet_info?.model"
                      class="rounded-lg bg-slate-200/60 px-2.5 py-1 text-[13px] font-medium text-slate-600"
                      :title="`Модель: ${app.selectedOrder.cabinet_info.model}`"
                    >
                      {{ app.selectedOrder.cabinet_info.model }}
                    </span>

                    <span
                      class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[13px] font-semibold"
                      :class="[
                        getStatusBadgeClasses(app.selectedOrder.market_status).bg,
                        getStatusBadgeClasses(app.selectedOrder.market_status).text,
                        getStatusBadgeClasses(app.selectedOrder.market_status).border || 'border-transparent',
                      ]"
                      :title="`Статус МП: ${getStatusDescription(app.selectedOrder.market_status)}`"
                    >
                      <span class="material-symbols-outlined text-[15px]">storefront</span>
                      {{ getRussianStatus(app.selectedOrder.market_status) }}
                    </span>

                    <span
                      v-if="app.selectedOrder.process_status"
                      class="rounded-lg px-2.5 py-1 text-[13px] font-semibold"
                      :class="getProcessStatus(app.selectedOrder.process_status).color"
                      :title="`Статус обработки: ${getProcessStatus(app.selectedOrder.process_status).label}`"
                    >
                      {{ getProcessStatus(app.selectedOrder.process_status).label }}
                    </span>
                  </div>

                  <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div>
                      <span class="text-[12.5px] text-slate-500">Создан</span>
                      <p class="mt-0.5 text-[15px] font-semibold text-slate-800">
                        {{ formatDate(app.selectedOrder.order_date) }}
                      </p>
                    </div>
                    <div>
                      <span class="text-[12.5px] text-slate-500">Отгрузка</span>
                      <p class="mt-0.5 text-[15px] font-semibold text-slate-800">
                        {{ formatDate(app.selectedOrder.send_date, true) }}
                      </p>
                    </div>
                    <div>
                      <span class="text-[12.5px] text-slate-500">Цена</span>
                      <p class="mt-0.5 text-[15px] font-semibold text-slate-800">
                        {{ formatPrice(app.selectedOrder.price) }}
                      </p>
                    </div>
                    <div>
                      <span class="text-[12.5px] text-slate-500">Товаров</span>
                      <p class="mt-0.5 text-[15px] font-semibold text-slate-800">
                        {{ app.selectedOrder.order_count || 0 }}
                      </p>
                    </div>
                  </div>
                </div>

                <!-- Поля заказа -->
                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label class="field-label">
                      Моя дата отгрузки <span class="text-rose-500">*</span>
                    </label>
                    <input
                      v-model="form.my_send_date"
                      type="date"
                      class="input-field"
                      :class="
                        validationErrors['my_send_date']
                          ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-100'
                          : ''
                      "
                    />
                    <p v-if="validationErrors['my_send_date']" class="mt-1 text-[12.5px] text-rose-600">
                      {{ validationErrors['my_send_date'] }}
                    </p>
                  </div>

                  <div>
                    <label class="field-label">Комментарий</label>
                    <textarea
                      v-model="form.comment"
                      rows="2"
                      class="input-field h-auto resize-none py-2.5"
                      placeholder="Дополнительная информация"
                    ></textarea>
                  </div>
                </div>

                <!-- Товары -->
                <div>
                  <h3 class="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                    <span class="material-symbols-outlined text-[15px]">inventory_2</span>
                    Товары
                  </h3>
                  <div class="space-y-3">
                    <div
                      v-for="(item, index) in form.items"
                      :key="item.item_id"
                      class="relative overflow-hidden rounded-xl border border-slate-200/70 bg-slate-50/60 p-4 pl-6"
                    >
                      <span
                        class="absolute bottom-4 left-2.5 top-4 w-1 rounded-full"
                        :style="{ backgroundColor: getMarketColor(app.selectedOrder.market_type).hex }"
                      ></span>

                      <div class="mb-3 flex flex-wrap items-center gap-2.5">
                        <div class="flex items-center gap-1">
                          <button
                            @click="copy(item.article)"
                            class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-white hover:text-slate-700"
                            title="Копировать артикул"
                          >
                            <span class="material-symbols-outlined text-[19px]">content_copy</span>
                          </button>
                          <span class="font-mono text-[15px] font-semibold text-slate-800" title="Артикул товара">
                            {{ item.article }}
                          </span>
                        </div>

                        <span class="flex items-center divide-x divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white text-[13px]">
                          <span class="px-3 py-1.5 text-slate-500" :title="getPriceTitle(item)">
                            Цена <b class="font-semibold text-slate-800">{{ formatPrice(item.price) }}</b>
                          </span>
                          <span
                            class="px-3 py-1.5"
                            :class="item.count > 1 ? 'font-semibold text-rose-600' : 'text-slate-500'"
                            title="Количество"
                          >
                            {{ item.count }} шт.
                          </span>
                        </span>
                      </div>

                      <p class="mb-3 text-sm leading-snug text-slate-600" title="Название товара">
                        {{ item.name }}
                      </p>

                      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        <div>
                          <label class="field-label" :title="getPurchaseTitle(item)">
                            Цена закупки <span class="text-rose-500">*</span>
                          </label>
                          <input
                            v-model.number="item.purchase"
                            type="number"
                            step="0.01"
                            min="0"
                            placeholder="0.00"
                            class="input-field bg-white"
                            :class="
                              validationErrors[`items.${index}.purchase`]
                                ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-100'
                                : ''
                            "
                          />
                          <p
                            v-if="validationErrors[`items.${index}.purchase`]"
                            class="mt-1 text-[12.5px] text-rose-600"
                          >
                            {{ validationErrors[`items.${index}.purchase`] }}
                          </p>
                        </div>

                        <div>
                          <label class="field-label">
                            Поставщик <span class="text-rose-500">*</span>
                          </label>
                          <select
                            v-model="item.provider"
                            class="input-field bg-white"
                            :class="
                              validationErrors[`items.${index}.provider`]
                                ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-100'
                                : ''
                            "
                          >
                            <option value="">Выберите</option>
                            <option v-for="p in providers" :key="p._id" :value="p.name">
                              {{ p.name }}
                            </option>
                          </select>
                          <p
                            v-if="validationErrors[`items.${index}.provider`]"
                            class="mt-1 text-[12.5px] text-rose-600"
                          >
                            {{ validationErrors[`items.${index}.provider`] }}
                          </p>
                        </div>

                        <div>
                          <label class="field-label">
                            Статус <span class="text-rose-500">*</span>
                          </label>
                          <select
                            v-model="item.status"
                            class="input-field bg-white"
                            :class="
                              validationErrors[`items.${index}.status`]
                                ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-100'
                                : ''
                            "
                          >
                            <option value="">Выберите</option>
                            <option v-for="s in statuses" :key="s._id" :value="s.name">
                              {{ s.name }}
                            </option>
                          </select>
                          <p
                            v-if="validationErrors[`items.${index}.status`]"
                            class="mt-1 text-[12.5px] text-rose-600"
                          >
                            {{ validationErrors[`items.${index}.status`] }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-2 border-t border-slate-100 bg-white px-6 py-4">
              <button @click="close" class="btn-secondary">
                Отмена
              </button>
              <button
                @click="save"
                :disabled="saving || !isFormValid || loading"
                class="btn-primary min-w-[150px]"
              >
                <span
                  v-if="saving"
                  class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                ></span>
                {{ saving ? 'Сохранение…' : 'Сохранить' }}
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>