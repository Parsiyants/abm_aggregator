<script setup>
import { computed } from 'vue'

/**
 * Компактный фильтр периода «от — до».
 *
 * Использование:
 *   <DateRange v-model:from="filters.date_from" v-model:to="filters.date_to" />
 *
 * Поведение:
 * - если задана только одна граница — вторая подставляется автоматически;
 * - при наличии значения появляется кнопка очистки.
 */
const props = defineProps({
  from: { type: String, default: '' },
  to: { type: String, default: '' },
})

const emit = defineEmits(['update:from', 'update:to'])

const hasValue = computed(() => Boolean(props.from || props.to))

function onFromChange(event) {
  const value = event.target.value || ''
  emit('update:from', value)

  // «от» задана, а «до» пустая — дублируем
  if (value && !props.to) emit('update:to', value)
}

function onToChange(event) {
  const value = event.target.value || ''
  emit('update:to', value)

  // «до» задана, а «от» пустая — дублируем
  if (value && !props.from) emit('update:from', value)
}

function clear() {
  emit('update:from', '')
  emit('update:to', '')
}

function openPicker(event) {
  const input = event.currentTarget
  if (typeof input.showPicker !== 'function') return
  try {
    input.showPicker()
  } catch {
    /* браузер может запретить — тогда остаётся обычный нативный ввод */
  }
}
</script>

<template>
  <div
    class="date-range flex h-11 w-full items-center gap-1 rounded-xl border bg-white px-2.5 transition-all duration-200"
    :class="
      hasValue
        ? 'border-slate-300 hover:border-slate-400'
        : 'border-slate-200 hover:border-slate-300'
    "
  >
    <input
      type="date"
      class="date-part"
      :class="{ 'date-empty': !from }"
      :value="from"
      :max="to || undefined"
      @change="onFromChange"
      @click="openPicker"
    />

    <span class="shrink-0 select-none text-xs text-slate-300">—</span>

    <input
      type="date"
      class="date-part"
      :class="{ 'date-empty': !to }"
      :value="to"
      :min="from || undefined"
      @change="onToChange"
      @click="openPicker"
    />

    <button
      v-if="hasValue"
      type="button"
      @click="clear"
      class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
      title="Очистить период"
    >
      <span class="material-symbols-outlined text-[15px]">close</span>
    </button>
  </div>
</template>

<style scoped>
.date-part {
  flex: 1 1 0;
  min-width: 0;
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13.5px;
  font-weight: 500;
  color: #1e293b;
  cursor: pointer;
}

/* Пустая дата — серый placeholder, заполненная — контрастная */
.date-part.date-empty {
  color: #94a3b8;
}

.date-part::-webkit-calendar-picker-indicator {
  opacity: 0.45;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.date-part::-webkit-calendar-picker-indicator:hover {
  opacity: 0.9;
}

.date-range:focus-within {
  border-color: #94a3b8;
  box-shadow: 0 0 0 4px rgb(15 23 42 / 0.05);
}
</style>
