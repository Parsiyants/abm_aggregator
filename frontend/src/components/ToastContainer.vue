<template>
  <div class="fixed top-5 right-5 z-[100] space-y-3 w-full max-w-xs">
    <TransitionGroup
      enter-active-class="transform ease-out duration-300 transition"
      enter-from-class="translate-y-2 opacity-0 sm:translate-y-0 sm:translate-x-2"
      enter-to-class="translate-y-0 opacity-100 sm:translate-x-0"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-for="n in store.notifications"
        :key="n.id"
        class="flex gap-1.5 items-center p-3 rounded-xl shadow-lg"
        :class="typeClasses[n.type] || typeClasses.info"
      >
        <span class="material-symbols-outlined">{{ icons[n.type] }}</span>
        <p class="flex-1 text-sm font-medium">{{ n.message }}</p>
        <button
          @click="store.remove(n.id)"
          class="ml-1 text-white/90 hover:text-white cursor-pointer"
        >
          <span class="material-symbols-outlined"> close </span>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useNotificationStore } from '@/stores/notifications'

const store = useNotificationStore()

const typeClasses = {
  success: 'bg-green-600 text-white',
  error: 'bg-red-600 text-white',
  info: 'bg-blue-600 text-white',
  warning: 'bg-yellow-600 text-white',
}

const icons = {
  success: 'check_circle',
  error: 'warning',
  info: 'info',
  warning: 'warning',
}
</script>
