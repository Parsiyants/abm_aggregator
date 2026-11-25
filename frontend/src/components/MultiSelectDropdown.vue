<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  options: { type: Array, required: true, default: () => [] },
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Выберите...' },
  searchable: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])

const isOpen = ref(false)
const searchQuery = ref('')
const dropdownRef = ref(null)

// Используем props.modelValue напрямую как источник правды
const internalValue = ref([...(props.modelValue || [])])

const closeOnClickOutside = (e) => {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', closeOnClickOutside))
onUnmounted(() => document.removeEventListener('click', closeOnClickOutside))

// Фильтрация
const filteredOptions = computed(() => {
  if (!searchQuery.value.trim()) return props.options
  const query = searchQuery.value.toLowerCase()
  return props.options.filter((opt) => opt.label.toLowerCase().includes(query))
})

// Выбранные метки
const selectedLabels = computed(() => {
  return props.options
    .filter((opt) => internalValue.value.includes(opt.value))
    .map((opt) => opt.label)
})

// === Исправленная синхронизация ===
watch(
  () => props.modelValue,
  (newVal) => {
    const normalized = newVal || []
    // Важно: сравниваем содержимое, чтобы избежать лишних обновлений
    if (JSON.stringify(normalized) !== JSON.stringify(internalValue.value)) {
      internalValue.value = [...normalized]
    }
  },
  { immediate: true }
)

// Только при реальном изменении пользователем — эммитим
watch(
  internalValue,
  (newVal) => {
    emit('update:modelValue', [...newVal])
  },
  { deep: true }
)

function toggleOption(value) {
  if (internalValue.value.includes(value)) {
    internalValue.value = internalValue.value.filter((v) => v !== value)
  } else {
    internalValue.value = [...internalValue.value, value]
  }
}

function clearAll() {
  internalValue.value = []
}
</script>

<template>
  <div class="relative" ref="dropdownRef">
    <button
      type="button"
      @click="isOpen = !isOpen"
      class="flex h-11 w-full items-center justify-between gap-2 rounded-xl border bg-white px-3.5 text-left text-sm transition-all duration-200 outline-none"
      :class="
        isOpen
          ? 'border-slate-400 ring-4 ring-slate-900/5'
          : internalValue.length
            ? 'border-slate-300 text-slate-900 hover:border-slate-400'
            : 'border-slate-200 text-slate-500 hover:border-slate-300'
      "
    >
      <span class="truncate">
        {{ internalValue.length ? selectedLabels.join(', ') : placeholder }}
      </span>

      <span class="flex shrink-0 items-center gap-1.5">
        <span
          v-if="internalValue.length"
          class="rounded-md bg-slate-900 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white"
        >
          {{ internalValue.length }}
        </span>
        <span
          class="material-symbols-outlined text-[18px] text-slate-400 transition-transform duration-200"
          :class="{ 'rotate-180': isOpen }"
        >
          expand_more
        </span>
      </span>
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1 scale-[0.98]"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 -translate-y-1 scale-[0.98]"
    >
      <div
        v-if="isOpen"
        class="absolute left-0 right-0 z-50 mt-1.5 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_12px_32px_-8px_rgba(15,23,42,0.18)]"
      >
        <div v-if="searchable" class="border-b border-slate-100 p-2">
          <div class="relative">
            <span
              class="material-symbols-outlined pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-slate-400"
            >
              search
            </span>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Поиск..."
              class="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-2 text-sm text-slate-800 outline-none transition-colors placeholder:text-slate-400 focus:border-slate-300 focus:bg-white"
              @click.stop
            />
          </div>
        </div>

        <div class="max-h-64 overflow-y-auto p-1.5">
          <button
            v-for="option in filteredOptions"
            :key="option.value"
            type="button"
            @click.stop="toggleOption(option.value)"
            class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors"
            :class="
              internalValue.includes(option.value)
                ? 'bg-slate-50 text-slate-900'
                : 'text-slate-600 hover:bg-slate-50'
            "
          >
            <span
              class="flex h-4 w-4 shrink-0 items-center justify-center rounded-[5px] border transition-colors"
              :class="
                internalValue.includes(option.value)
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-300 bg-white'
              "
            >
              <span
                v-if="internalValue.includes(option.value)"
                class="material-symbols-outlined text-[12px] leading-none"
              >
                check
              </span>
            </span>
            <span class="truncate">{{ option.label }}</span>
          </button>

          <div
            v-if="filteredOptions.length === 0"
            class="px-2.5 py-8 text-center text-sm text-slate-400"
          >
            Ничего не найдено
          </div>
        </div>

        <div
          class="flex items-center justify-between gap-2 border-t border-slate-100 bg-slate-50/60 px-2 py-1.5"
        >
          <button
            type="button"
            @click.stop="clearAll"
            class="rounded-lg px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:text-slate-900"
            :disabled="!internalValue.length"
          >
            Сбросить
          </button>
          <button
            type="button"
            @click.stop="isOpen = false"
            class="rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-slate-800"
          >
            Готово
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
