<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, required: true },
  totalPages: { type: Number, required: true },
  totalItems: { type: Number, default: 0 },
})

const emit = defineEmits(['changePage'])

function changePage(p) {
  if (p < 1 || p > props.totalPages || p === props.page) return
  emit('changePage', p)
}

const pages = computed(() => {
  const total = props.totalPages
  const current = props.page
  const delta = 2

  if (total <= 1) return [1]

  const range = []
  const start = Math.max(2, current - delta)
  const end = Math.min(total - 1, current + delta)

  range.push(1)

  if (start > 2) range.push('...')

  for (let i = start; i <= end; i++) {
    range.push(i)
  }

  if (end < total - 1) range.push('...')

  if (total > 1) range.push(total)

  return range
})
</script>

<template>
  <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
    <p class="text-xs text-slate-500">
      <template v-if="totalItems">
        Всего <span class="font-semibold text-slate-700">{{ totalItems }}</span> записей
      </template>
    </p>

    <div class="ml-auto flex items-center gap-1">
      <!-- prev -->
      <button
        @click="changePage(page - 1)"
        :disabled="page <= 1"
        class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-40"
      >
        <span class="material-symbols-outlined text-[20px]">chevron_left</span>
      </button>

      <!-- pages -->
      <template v-for="(p, i) in pages" :key="i">
        <span v-if="p === '...'" class="px-1.5 text-sm text-slate-400 select-none">…</span>
        <button
          v-else
          @click="changePage(p)"
          class="h-9 min-w-9 rounded-lg px-2 text-sm font-medium transition-all"
          :class="
            p === page
              ? 'bg-slate-900 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          "
        >
          {{ p }}
        </button>
      </template>

      <!-- next -->
      <button
        @click="changePage(page + 1)"
        :disabled="page >= totalPages"
        class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-40"
      >
        <span class="material-symbols-outlined text-[20px]">chevron_right</span>
      </button>
    </div>
  </div>
</template>