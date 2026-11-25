<script setup>
import { RouterLink, RouterView } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import HandleOrderPopup from '@/components/popup/HandleOrderPopup.vue'
import { useAuthStore } from '@/stores/auth'
import { useReferenceStore } from '@/stores/references'
import { onMounted, onUnmounted } from 'vue'
import { useOrdersStore } from '@/stores/orders'
import wsService from '@/services/websocket.service'
import { useAppStore } from '@/stores/app'
import BottomUpdateBar from '@/components/BottomUpdateBar.vue'
import PrintBar from '@/components/PrintBar.vue'
import { useSound } from '@/composables/useSound'

const appStore = useAppStore()
const authStore = useAuthStore()
const ordersStore = useOrdersStore()
const refStore = useReferenceStore()
const { playSound, init } = useSound()

// ── Обработчик нового заказа ──────────────────────────────
const handleNewOrder = (orderData) => {
  // 🔥 addLiveOrder возвращает true, если заказ действительно новый
  const isNew = ordersStore.addLiveOrder(orderData)

  // 🎵 Звук только для НОВЫХ заказов!
  if (isNew) {
    playSound()

    // 📱 Уведомление
    if (window.Notification && Notification.permission === 'granted') {
      new Notification('🆕 Новый заказ!', {
        body: `Заказ #${orderData.order_id} от ${orderData.cabinet_name}`,
        icon: '/favicon.ico'
      })
    }
  }
}

onMounted(async () => {
  init()

  if (window.Notification && Notification.permission === 'default') {
    Notification.requestPermission()
  }

  if (authStore.isLoggedIn) {
    ordersStore.fetchOrders({ page: 1, limit: 100, process_status: 'New' }, 'new')

    refStore.fetchAll('providers')
    refStore.fetchAll('statuses')
    refStore.fetchAll('marketplaces')
    refStore.fetchAll('cabinets')

    wsService.on('new_order', handleNewOrder)
    wsService.on('update_order', ordersStore.updateLiveOrder)
  }
})

onUnmounted(() => {
  wsService.off('new_order', handleNewOrder)
})
</script>

<template>
  <div id="app" class="relative min-h-screen bg-slate-100/70">
    <!-- Мягкая подсветка сверху страницы -->
    <div
      class="pointer-events-none absolute inset-x-0 top-0 h-72 bg-gradient-to-b from-white via-white/60 to-transparent"
    ></div>

    <Navbar />
    <main class="layout-container relative mx-auto px-4 pb-24 pt-7 sm:px-6 lg:px-8">
      <slot />
    </main>
    <ToastContainer />
    <HandleOrderPopup />
    <BottomUpdateBar />
    <PrintBar />
  </div>
</template>
