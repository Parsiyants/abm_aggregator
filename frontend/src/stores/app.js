// src/stores/app.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // ── State ────────────────────────────────────────────────
  const theme = ref(localStorage.getItem('appTheme') || 'light')
  // const marketMap2 = {
  //   ozon: {
  //     hex: '#005bff',
  //     bg: 'bg-blue-600',
  //     bg_5: 'bg-blue-600/5',
  //     badge: 'bg-blue-50 text-blue-700',
  //     border: 'border-blue-400',
  //     hoverBorder: 'hover:border-blue-400',
  //     btnShadow: 'shadow-blue-100',
  //   },
  //   yandex: {
  //     hex: '#ffcc00',
  //     bg: 'bg-yellow-400',
  //     bg_5: 'bg-yellow-400/5',
  //     badge: 'bg-yellow-50 text-yellow-800',
  //     border: 'border-yellow-400',
  //     hoverBorder: 'hover:border-yellow-400',
  //     btnShadow: 'shadow-yellow-100',
  //   },
  //   wildberries: {
  //     hex: '#cb11ab',
  //     bg: 'bg-purple-500',
  //     bg_5: 'bg-purple-500/5',
  //     badge: 'bg-purple-50 text-purple-700',
  //     border: 'border-purple-400',
  //     hoverBorder: 'hover:border-purple-400',
  //     btnShadow: 'shadow-purple-100',
  //   },
  //   avito: {
  //     hex: '#8ec448',
  //     bg: 'bg-green-500',
  //     bg_5: 'bg-green-500/5',
  //     badge: 'bg-green-50 text-green-700',
  //     border: 'border-green-400',
  //     hoverBorder: 'hover:border-green-400',
  //     btnShadow: 'shadow-green-100',
  //   },
  // }
  const marketMap = {
    ozon: 'blue',
    yandex: 'yellow',
    wb: 'purple',
    avito: 'green',
  }
  const handleOrderPopup = ref(false)
  const selectedOrder = ref(null) // _id заказа из MongoDB

  const updatesItemsList = ref(new Map()) // Список обновлений для отображения в BottomUpdateBar
  const BottomUpdateBarVisible = ref(false) // Видимость компонента BottomUpdateBar
  const hasChanges = computed(() => updatesItemsList.value.size > 0)

  function openHandleOrderModal(order) {
    selectedOrder.value = order
    handleOrderPopup.value = true
  }

  function closeHandleOrderModal() {
    handleOrderPopup.value = false
    selectedOrder.value = null
  }

  // ── Getters ──────────────────────────────────────────────
  const isDarkMode = computed(() => theme.value === 'dark')
  // ── Actions ──────────────────────────────────────────────
  function toggleTheme() {
    theme.value = isDarkMode.value ? 'light' : 'dark'
    localStorage.setItem('appTheme', theme.value)
  }
  return {
    theme,
    isDarkMode,
    toggleTheme,
    marketMap,
    handleOrderPopup,
    selectedOrder,
    updatesItemsList,
    BottomUpdateBarVisible,
    hasChanges,
    openHandleOrderModal,
    closeHandleOrderModal,
  }
})
