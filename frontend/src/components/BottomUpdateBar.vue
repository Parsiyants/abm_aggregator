<script setup>
import { useAppStore } from '@/stores/app'
import { useNotificationStore } from '@/stores/notifications'
import { useOrdersStore } from '@/stores/orders'

const app = useAppStore()
const notify = useNotificationStore()
const order = useOrdersStore()

// const saveUpdatesItemsList = (newItem) => {
//   app.updatesItemsList.unshift(newItem) // Добавляем новое обновление в начало списка
//   if (app.updatesItemsList.length > 5) {
//     app.updatesItemsList.pop() // Удаляем старые обновления, если их больше 5
//   }
//   app.BottomUpdateBarVisible = true // Показываем BottomUpdateBar при добавлении нового обновления
// }

const saveUpdatesItemsList = () => {
  if (app.updatesItemsList.length <= 0) {
    notify.add({
      type: 'info',
      message: 'Нет новых обновлений',
    })
    return
  }

  if (order.bulkUpdateItemStatuses(app.updatesItemsList)) {
    app.updatesItemsList = new Map() // Очищаем список обновлений
    app.BottomUpdateBarVisible = false // Скрываем BottomUpdateBar
    app.hasChanges = false
  }
}

const clearUpdatesItemsList = () => {
  app.updatesItemsList = new Map() // Очищаем список обновлений
  app.BottomUpdateBarVisible = false // Скрываем BottomUpdateBar
}
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="app.hasChanges"
      class="fixed bottom-5 left-1/2 z-50 flex min-w-[380px] -translate-x-1/2 items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-2.5 shadow-[0_16px_40px_-12px_rgba(15,23,42,0.24)] backdrop-blur-xl"
    >
      <span class="text-sm text-slate-600">
        Обновить <b class="font-semibold text-slate-900">{{ app.updatesItemsList.size }}</b> поз.
      </span>

      <div class="ml-auto flex items-center gap-2">
        <button @click="clearUpdatesItemsList" class="btn-secondary h-9">
          Очистить
        </button>
        <button @click="saveUpdatesItemsList" class="btn-primary h-9">
          Сохранить
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.45s cubic-bezier(0.34, 1.56, 0.64, 1); /* overshoot для приятного эффекта */
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(80%) scale(0.94);
  opacity: 0;
}

.slide-up-enter-to,
.slide-up-leave-from {
  transform: translateY(0) scale(1);
  opacity: 1;
}
</style>
