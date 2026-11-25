<template>
  <div class="flex items-center gap-1.5">
    <!-- Переключатель звука -->
    <button
      @click="toggleSound"
      class="w-9 h-9 rounded-full flex items-center justify-center transition-colors cursor-pointer"
      :class="isEnabled ? 'bg-green-100 text-green-600 hover:bg-green-200' : 'bg-gray-100 text-gray-400 hover:bg-gray-200'"
      :title="isEnabled ? 'Звук включён' : 'Звук выключен'"
    >
      <span class="material-symbols-outlined text-xl">
        {{ isEnabled ? 'volume_up' : 'volume_off' }}
      </span>
    </button>

    <!-- Кнопка проверки -->
    <button
      @click="testSound"
      class="hidden w-9 h-9 rounded-full flex items-center justify-center transition-colors bg-blue-50 hover:bg-blue-100 text-blue-500"
      title="Проверить звук"
    >
      <span class="material-symbols-outlined text-lg">play_arrow</span>
    </button>
  </div>
</template>

<script setup>
import { useSound } from '@/composables/useSound'

const { isEnabled, toggleSound, playSound, playSuccessSound, playCashSound, playBeepSound } = useSound()

const testSound = () => {
  playSound()
}
</script>