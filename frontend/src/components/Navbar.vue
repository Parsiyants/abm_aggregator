<script setup>
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import api from '@/services/api'
import { useFunction } from '@/composables/function'
import SoundToggle from './SoundToggle.vue'

const authStore = useAuthStore()
const router = useRouter()
const { formatPrice, copy, formatDate, getRussianStatus, getStatusDescription, getStatusBadgeClasses, getProcessStatus } = useFunction()

// ── Табы ────────────────────────────────────────────────────
const tabs = [
  { name: 'New', label: 'Новые', icon: 'order_approve', to: '/' },
  { name: 'Send', label: 'Отгрузки', icon: 'orders', to: '/send' },
  { name: 'Orders', label: 'Заказы', icon: 'shopping_bag', to: '/orders' },
  { name: 'Analytics', label: 'Аналитика', icon: 'bar_chart', to: '/analytics' },
  { name: 'Settings', label: 'Настройки', icon: 'settings', to: '/settings' },
  { name: 'Logs', label: 'Логи', icon: 'list_alt', to: '/logs' },
]

// ── Поиск ──────────────────────────────────────────────────
const isSearchOpen = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)
const searchInputRef = ref(null)
let searchTimeout = null
let abortController = null

const handleLogout = () => {
  if (confirm('Уверены что хотите уйти?')) {
    authStore.logout()
    router.push('/login')
  }
}

// ── Открыть/закрыть поиск ──────────────────────────────────
const toggleSearch = () => {
  isSearchOpen.value = !isSearchOpen.value
  if (isSearchOpen.value) {
    setTimeout(() => {
      searchInputRef.value?.focus()
    }, 200)
  } else {
    searchQuery.value = ''
    searchResults.value = []
  }
}

// ── Поиск с debounce ──────────────────────────────────────
const performSearch = async (query) => {
  if (!query || query.trim().length < 2) {
    searchResults.value = []
    return
  }

  isSearching.value = true

  if (abortController) {
    abortController.abort()
  }

  abortController = new AbortController()

  try {
    const response = await api.get('/orders/', {
      params: { search: query.trim(), limit: 10 },
      signal: abortController.signal,
    })

    searchResults.value = response.data.items || []
  } catch (error) {
    if (error.name === 'AbortError') {
      console.log('Search aborted')
    } else {
      console.error('Search error:', error)
      searchResults.value = []
    }
  } finally {
    isSearching.value = false
  }
}

// ── Debounce ────────────────────────────────────────────────
watch(searchQuery, (newQuery) => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    performSearch(newQuery)
  }, 400)
})

// ── Выбор результата ──────────────────────────────────────
const closeSearch = () => {
  searchQuery.value = ''
  searchResults.value = []
  isSearchOpen.value = false
}

// ── Клик вне поиска ────────────────────────────────────────
const handleClickOutside = (event) => {
  const searchContainer = document.querySelector('.search-container')
  if (searchContainer && !searchContainer.contains(event.target)) {
    isSearchOpen.value = false
    searchQuery.value = ''
    searchResults.value = []
  }
}


// ── Цвет маркета ────────────────────────────────────────────
const getMarketColor = (marketType) => {
  const colors = {
    ozon: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200' },
    yandex: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200' },
    wb: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-200' },
    avito: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-200' },
  }
  return (
    colors[marketType] || { bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-200' }
  )
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  clearTimeout(searchTimeout)
  if (abortController) {
    abortController.abort()
  }
})
</script>

<template>
  <nav class="sticky top-0 z-40 border-b border-slate-200/70 bg-white/80 backdrop-blur-xl">
    <div class="layout-container mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex h-16 items-center justify-between gap-6">
        <!-- Левая часть: Логотип + Табы -->
        <div class="flex items-center gap-6">
          <router-link to="/" class="group flex shrink-0 items-center gap-1">
            <span
              class="flex h-11 w-11 items-center justify-center rounded-[10px] bg-slate-900 text-[15px] font-bold text-white transition-transform duration-200 group-hover:scale-105"
            >
              ABM
            </span>
            <span class="text-[15px] font-semibold tracking-[-0.01em] text-slate-900">
              auto
            </span>
          </router-link>

          <div class="hidden items-center gap-0.5 rounded-xl bg-slate-100/80 p-1 md:flex">
            <router-link
              v-for="tab in tabs"
              :key="tab.name"
              :to="tab.to"
              class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
              :class="
                $route.path === tab.to
                  ? 'bg-white text-slate-900 shadow-[0_1px_2px_rgba(15,23,42,0.08)]'
                  : 'text-slate-500 hover:text-slate-900'
              "
            >
              <span class="material-symbols-outlined text-[18px] leading-none">{{ tab.icon }}</span>
              <span>{{ tab.label }}</span>
            </router-link>
          </div>
        </div>

        <!-- Правая часть -->
        <div class="flex items-center gap-3">
          <!-- Статус WebSocket -->
          <div class="flex items-center gap-2 rounded-full border border-slate-200/70 bg-white px-2.5 py-1">
            <span
              class="h-1.5 w-1.5 rounded-full"
              :class="authStore.wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'"
            ></span>
            <span class="text-[11px] font-medium uppercase tracking-wide text-slate-500">
              {{ authStore.wsConnected ? 'Live' : 'Offline' }}
            </span>
          </div>

          <!-- Поиск -->
          <div class="search-container relative flex items-center">
            <!-- Обёртка: кнопка + строка поиска -->
            <div
              class="flex items-center rounded-full transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] overflow-hidden"
              :class="[
                isSearchOpen
                  ? 'bg-white shadow-lg ring-1 ring-slate-200 w-72 sm:w-96'
                  : 'bg-transparent w-10',
              ]"
            >
              <!-- Кнопка поиска -->
              <button
                @click="toggleSearch"
                class="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 shrink-0 z-10 cursor-pointer"
                :class="[
                  isSearchOpen
                    ? 'bg-white text-slate-500 hover:text-slate-900'
                    : 'bg-slate-900 text-white hover:bg-slate-800 shadow-sm',
                ]"
                title="Поиск заказов"
              >
                <span class="material-symbols-outlined text-xl">
                  {{ isSearchOpen ? 'arrow_back' : 'search' }}
                </span>
              </button>

              <!-- Строка поиска (абсолютная) -->
              <Transition
                enter-active-class="transition-all duration-400 ease-[cubic-bezier(0.34,1.56,0.64,1)]"
                enter-from-class="w-0 opacity-0"
                enter-to-class="w-full opacity-100"
                leave-active-class="transition-all duration-300 ease-in"
                leave-from-class="w-full opacity-100"
                leave-to-class="w-0 opacity-0"
              >
                <div v-if="isSearchOpen" class="flex-1 overflow-hidden">
                  <input
                    ref="searchInputRef"
                    v-model="searchQuery"
                    type="text"
                    placeholder="Поиск по ID, артикулу, товару..."
                    class="w-full h-10 outline-none text-sm bg-transparent text-gray-700 placeholder-gray-400 pr-3"
                  />
                </div>
              </Transition>
            </div>

            <!-- Результаты поиска -->
            <Transition
              enter-active-class="transition-all duration-300 ease-out"
              enter-from-class="opacity-0 -translate-y-3 scale-95"
              enter-to-class="opacity-100 translate-y-0 scale-100"
              leave-active-class="transition-all duration-200 ease-in"
              leave-from-class="opacity-100 translate-y-0 scale-100"
              leave-to-class="opacity-0 -translate-y-3 scale-95"
            >
              <div
                v-if="isSearchOpen && searchQuery.trim().length >= 2"
                class="absolute right-0 top-full mt-5 min-w-[500px] max-w-[900px] bg-white rounded-2xl shadow-2xl border border-gray-200/80 overflow-hidden"
              >
                <!-- Загрузка -->
                <div v-if="isSearching" class="px-4 py-6 text-center text-gray-400 text-sm">
                  <div class="flex items-center justify-center gap-3">
                    <span
                      class="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
                    ></span>
                    <span>Поиск...</span>
                  </div>
                </div>

                <!-- Результаты -->
                <div
                  v-else-if="searchResults.length > 0"
                  class="max-h-[480px] overflow-y-auto divide-y divide-gray-100"
                >
                  <router-link
                    v-for="order in searchResults"
                    :to="`/orders/${order._id}`"
                    :key="order._id"
                    @click="closeSearch()"
                    class="block px-4 py-4 hover:bg-blue-50/70 cursor-pointer transition-all duration-150 group"
                  >
                    <div class="flex items-center gap-3">
                      <!-- Иконка -->
                      <!-- <div
                        class="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center shrink-0 mt-0.5 group-hover:bg-blue-100 transition-colors"
                      >
                        <span class="material-symbols-outlined text-blue-500 text-lg"
                          >shopping_bag</span
                        >
                      </div> -->

                      <!-- Информация -->
                      <div class="flex-1 min-w-0">
                        <!-- Верхняя строка: ID + кабинет + статусы -->
                        <div class="flex items-center gap-2 flex-wrap">
                          <span
                            class="text-sm font-bold text-gray-800 group-hover:text-blue-700 transition-colors"
                            :title="`Номер заказа: ${order.order_id}`"
                          >
                            {{ order.order_id }}
                          </span>
                          <span
                            class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                            :class="`${getMarketColor(order.market_type).bg} ${getMarketColor(order.market_type).text}`"
                            :title="`Кабинет: ${order.cabinet_name}`"
                          >
                            {{ order.cabinet_name }}
                          </span>
                          <span
                            v-if="order.market_status"
                            class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                            :class="`${getStatusBadgeClasses(order.market_status).bg} ${getStatusBadgeClasses(order.market_status).text}`"
                            :title="`Статус МП: ${getStatusDescription(order.market_status)}`"
                          >
                            {{ getRussianStatus(order.market_status) }}
                          </span>
                          <span
                            v-if="order.process_status"
                            class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                            :class="getProcessStatus(order.process_status).color"
                            :title="`Статус обработки: ${getProcessStatus(order.process_status).label}`"
                          >
                            {{ getProcessStatus(order.process_status).label }}
                          </span>
                        </div>

                        <!-- Товары (все) -->
                        <div class="mt-3 space-y-3">
                          <div
                            v-for="(item, idx) in order.items"
                            :key="item._id"
                            class="text-xs border-l-2 border-gray-200 pl-2.5"
                            :class="idx < order.items.length - 1 ? 'border-gray-200' : ''"
                          >
                            <div class="flex items-center gap-2 mb-1.5">
                              <span
                                class="font-semibold text-gray-700"
                                :title="`Артикул: ${item.article}`"
                              >
                                {{ item.article }}
                              </span>
                              <span class="text-gray-300">·</span>
                              <span class="text-gray-500" :title="`Количество: ${item.count} шт`">
                                {{ item.count }} шт
                              </span>
                              <span class="text-gray-300">·</span>
                              <span
                                class="text-gray-500"
                                :title="`Цена: ${new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(item.price)}`"
                              >
                                {{
                                  new Intl.NumberFormat('ru-RU', {
                                    style: 'currency',
                                    currency: 'RUB',
                                    maximumFractionDigits: 0,
                                  }).format(item.price)
                                }}
                              </span>
                              <span class="text-gray-300">·</span>
                              <span
                                class="text-gray-500"
                                :title="`Коментарий: ${order?.comment}`"
                              >
                                {{
                                  order?.comment
                                }}
                              </span>
                            </div>

                            <span
                              class="text-gray-500"
                              :title="`Название: ${item.name}`"
                            >
                              {{ item.name }}
                            </span>
                          </div>
                        </div>

                        <!-- Даты + цена -->
                        <div class="flex items-center gap-3 mt-3 text-xs text-gray-400">
                          <span
                            class="flex items-center gap-1"
                            :title="`Дата создания: ${formatDate(order.order_date)}`"
                          >
                            <span class="material-symbols-outlined text-[14px]"
                              >calendar_today</span
                            >
                            {{ formatDate(order.order_date) }}
                          </span>
                          <span class="text-gray-300">|</span>
                          <span
                            class="flex items-center gap-1"
                            :title="`Дата отгрузки: ${formatDate(order.send_date)}`"
                          >
                            <span class="material-symbols-outlined text-[14px]"
                              >local_shipping</span
                            >
                            {{ formatDate(order.send_date) }}
                          </span>
                          <span class="text-gray-300">|</span>
                          <span
                            class="font-semibold text-gray-700"
                            :title="`Общая сумма: ${new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(order.price)}`"
                          >
                            {{
                              new Intl.NumberFormat('ru-RU', {
                                style: 'currency',
                                currency: 'RUB',
                                maximumFractionDigits: 0,
                              }).format(order.price)
                            }}
                          </span>
                        </div>
                      </div>

                      <!-- Стрелка -->
                      <span
                        class="material-symbols-outlined text-gray-300 group-hover:text-blue-500 transition-colors text-base shrink-0 mt-1"
                      >
                        chevron_right
                      </span>
                    </div>
                  </router-link>

                  <!-- Футер -->
                  <div
                    class="px-4 py-2 bg-gray-50/80 text-xs text-gray-400 text-center border-t border-gray-100"
                  >
                    Найдено {{ searchResults.length }} заказов
                  </div>
                </div>

                <!-- Пусто -->
                <div v-else class="px-4 py-10 text-center text-gray-400 text-sm">
                  <span class="material-symbols-outlined text-4xl block mb-2 text-gray-300"
                    >search_off</span
                  >
                  <p class="font-medium">Ничего не найдено</p>
                  <p class="text-xs mt-0.5">Попробуйте изменить запрос</p>
                </div>
              </div>
            </Transition>
          </div>

            <sound-toggle />

          <!-- Выход -->
          <button
            @click="handleLogout"
            class="w-9 h-9 hover:bg-gray-100 text-gray-600 hover:text-red-600 rounded-full flex items-center justify-center transition-all cursor-pointer"
            title="Выйти"
          >
            <span class="material-symbols-outlined text-2xl">logout</span>
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
/* Кастомный скролл */
.max-h-\[440px\]::-webkit-scrollbar {
  width: 4px;
}

.max-h-\[440px\]::-webkit-scrollbar-track {
  background: transparent;
}

.max-h-\[440px\]::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 9999px;
}

.max-h-\[440px\]::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

/* Анимация с упругим эффектом */
.duration-500 {
  transition-duration: 500ms;
}

.ease-\[cubic-bezier\(0\.34\,1\.56\,0\.64\,1\)\] {
  transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1);
}
</style>
