<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useReferenceStore } from '@/stores/references'

const refStore = useReferenceStore()
const isModalOpen = ref(false)

const form = reactive({
  _id: null,
  name: '',
  index: 10,
  active: true,
})

// Сортировка по индексу на лету
const sortedProviders = computed(() => {
  return [...refStore.providers].sort((a, b) => a.index - b.index)
})

onMounted(() => {
  refStore.fetchAll('providers')
})

const openModal = (item = null) => {
  if (item) {
    Object.assign(form, item)
  } else {
    Object.assign(form, {
      _id: null,
      name: '',
      index: 10,
      active: true,
    })
  }
  isModalOpen.value = true
}

const save = async () => {
  const success = await refStore.upsertItem('providers', { ...form })
  if (success) isModalOpen.value = false
}

const confirmDelete = async (type, id) => {
  if (confirm('Удалить поставщика?')) {
    await refStore.deleteItem(type, id)
    isModalOpen.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-5 pb-20">
    <!-- Заголовок -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Поставщики</h1>
        <p class="mt-1 text-sm text-slate-500">Управление очередностью и списком поставщиков</p>
      </div>
      <button @click="openModal()" class="btn-primary">
        <span class="material-symbols-outlined text-[18px]">add</span>
        Добавить
      </button>
    </div>

    <section class="panel overflow-hidden">
      <table class="w-full text-left">
        <thead>
          <tr class="border-b border-slate-100 text-[11px] font-medium uppercase tracking-wider text-slate-400">
            <th class="w-24 px-4 py-3 text-center">Индекс</th>
            <th class="px-4 py-3">Название</th>
            <th class="px-4 py-3 text-right">Статус</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr
            v-for="p in sortedProviders"
            :key="p._id"
            @click="openModal(p)"
            class="group cursor-pointer transition-colors hover:bg-slate-50"
          >
            <td class="px-4 py-3.5 text-center font-mono text-xs text-slate-400">
              {{ p.index }}
            </td>
            <td class="px-4 py-3.5 text-sm font-medium text-slate-800">
              {{ p.name }}
            </td>
            <td class="px-4 py-3.5 text-right">
              <span
                class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
                :class="p.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
              >
                <span
                  class="h-1.5 w-1.5 rounded-full"
                  :class="p.active ? 'bg-emerald-500' : 'bg-slate-400'"
                ></span>
                {{ p.active ? 'Активен' : 'Выключен' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="!sortedProviders.length" class="px-6 py-14 text-center text-sm text-slate-400">
        Поставщиков пока нет
      </div>
    </section>

    <div
      v-if="isModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
    >
      <div
        class="w-full max-w-md space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_24px_60px_-20px_rgba(15,23,42,0.35)]"
      >
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold tracking-tight text-slate-900">Данные поставщика</h3>
          <label class="flex cursor-pointer items-center gap-2">
            <span class="text-xs font-medium text-slate-500">Активен</span>
            <input
              type="checkbox"
              v-model="form.active"
              class="relative h-5 w-10 cursor-pointer appearance-none rounded-full bg-slate-200 transition-colors before:absolute before:left-0.5 before:top-0.5 before:h-4 before:w-4 before:rounded-full before:bg-white before:transition-transform before:content-[''] checked:bg-slate-900 checked:before:translate-x-5"
            />
          </label>
        </div>

        <div class="space-y-4">
          <div>
            <label class="field-label">Название организации</label>
            <input v-model="form.name" placeholder="Напр: ООО Вектор" class="input-field" />
          </div>
          <div>
            <label class="field-label">Индекс сортировки</label>
            <input v-model="form.index" type="number" class="input-field" />
          </div>
        </div>

        <div class="flex gap-2 pt-2">
          <button
            v-if="form._id"
            @click="confirmDelete('providers', form._id)"
            class="p-3 bg-red-50 text-red-500 rounded-2xl hover:bg-red-100 transition-colors"
          >
            <span class="material-symbols-outlined">delete</span>
          </button>
          <button @click="isModalOpen = false" class="btn-secondary flex-1">Отмена</button>
          <button @click="save" class="btn-primary flex-1">Сохранить</button>
        </div>
      </div>
    </div>
  </div>
</template>
