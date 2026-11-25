<template>
  <div class="relative">
    <!-- Управление графиком -->
    <div class="flex justify-between items-center mb-6 px-1">
      <div class="flex gap-2">
        <button
          v-for="type in periodTypes"
          :key="type.value"
          @click="emit('update:periodType', type.value)"
          class="px-5 py-2 text-sm font-medium rounded-2xl transition-all cursor-pointer"
          :class="
            periodType === type.value
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
          "
        >
          {{ type.label }}
        </button>
      </div>

      <div class="flex gap-6">
        <button
          v-for="ds in toggleableDatasets"
          :key="ds.key"
          @click="toggleDataset(ds.key)"
          class="flex items-center gap-2 text-sm cursor-pointer"
          :class="visibleDatasets[ds.key] ? 'text-gray-800' : 'line-through text-gray-400'"
        >
          <div class="w-3.5 h-3.5 rounded" :style="{ backgroundColor: ds.color }"></div>
          {{ ds.label }}
        </button>
      </div>
    </div>

    <!-- График -->
    <div :style="{ height: height + 'px' }">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Line } from 'vue-chartjs'
import dayjs from 'dayjs'
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore'

dayjs.extend(isSameOrBefore)

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

const props = defineProps({
  dailyStats: { type: Array, default: () => [] },
  dateFrom: { type: String, required: true },
  dateTo: { type: String, required: true },
  periodType: { type: String, default: 'day' },
  height: { type: Number, default: 420 },
})

const emit = defineEmits(['update:periodType'])

const visibleDatasets = ref({ sales: true, purchase: true })

function toggleDataset(key) {
  visibleDatasets.value[key] = !visibleDatasets.value[key]
}

const periodTypes = [
  { value: 'day', label: 'По дням' },
  { value: 'week', label: 'По неделям' },
  { value: 'month', label: 'По месяцам' },
]

// ==================== ГЕНЕРАЦИЯ ВСЕХ ДАТ ====================
const allDates = computed(() => {
  const dates = []
  let current = dayjs(props.dateFrom)
  const end = dayjs(props.dateTo)

  while (current.isSameOrBefore(end, 'day')) {
    dates.push(current.format('YYYY-MM-DD'))
    current = current.add(1, 'day')
  }
  return dates
})

// Мап данных по дате
const dataMap = computed(() => {
  const map = {}
  props.dailyStats.forEach((item) => {
    if (item && item._id) map[item._id] = item
  })
  return map
})

// ==================== ОБРАБОТКА ДАННЫХ ====================
const chartData = computed(() => {
  let processed = allDates.value.map((date) => {
    const stat = dataMap.value[date]
    return {
      date,
      label: dayjs(date).format('DD MMM'),
      total_price: stat ? stat.total_price || 0 : 0,
      total_purchase: stat ? stat.total_purchase || 0 : 0,
      total_orders: stat ? stat.total_orders || 0 : 0,
      total_items: stat ? stat.total_items || 0 : 0,
    }
  })

  if (props.periodType === 'week') processed = groupByWeek(processed)
  else if (props.periodType === 'month') processed = groupByMonth(processed)

  return {
    labels: processed.map((item) => item.label),
    datasets: [
      {
        label: 'Сумма продаж',
        data: processed.map((item) => item.total_price),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 3,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        hidden: !visibleDatasets.value.sales,
      },
      {
        label: 'Закуп',
        data: processed.map((item) => item.total_purchase),
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderWidth: 3,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        hidden: !visibleDatasets.value.purchase,
      },
    ],
  }
})

// Группировки
function groupByWeek(data) {
  const groups = {}
  data.forEach((item) => {
    const weekKey = dayjs(item.date).startOf('week').format('YYYY-MM-DD')
    if (!groups[weekKey]) {
      groups[weekKey] = {
        label: dayjs(weekKey).format('DD MMM'),
        total_price: 0,
        total_purchase: 0,
        total_orders: 0,
        total_items: 0,
      }
    }
    groups[weekKey].total_price += item.total_price
    groups[weekKey].total_purchase += item.total_purchase
    groups[weekKey].total_orders += item.total_orders
    groups[weekKey].total_items += item.total_items
  })
  return Object.values(groups)
}

function groupByMonth(data) {
  const groups = {}
  data.forEach((item) => {
    const monthKey = dayjs(item.date).format('YYYY-MM')
    if (!groups[monthKey]) {
      groups[monthKey] = {
        label: dayjs(monthKey + '-01').format('MMMM YYYY'),
        total_price: 0,
        total_purchase: 0,
        total_orders: 0,
        total_items: 0,
      }
    }
    groups[monthKey].total_price += item.total_price
    groups[monthKey].total_purchase += item.total_purchase
    groups[monthKey].total_orders += item.total_orders
    groups[monthKey].total_items += item.total_items
  })
  return Object.values(groups)
}

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },

  plugins: {
    legend: { display: false },

    tooltip: {
      mode: 'index',
      intersect: false,
      backgroundColor: '#1f2937',
      titleColor: '#e5e7eb',
      bodyColor: '#e5e7eb',
      padding: 14,
      callbacks: {
        title: (ctx) => dayjs(ctx[0].label, 'DD MMM').format('DD MMMM YYYY'),
        label: (ctx) =>
          `${ctx.dataset.label}: ${new Intl.NumberFormat('ru-RU').format(Math.round(ctx.raw))} ₽`,
        afterBody: (ctx) => {
          const index = ctx[0].dataIndex
          const date = allDates.value[index]
          const stat = dataMap.value[date]
          if (!stat) return []

          return [
            `Заказов: ${new Intl.NumberFormat('ru-RU').format(stat.total_orders || 0)}`,
            `Товаров: ${new Intl.NumberFormat('ru-RU').format(stat.total_items || 0)}`,
          ]
        },
      },
    },
  },

  scales: {
    x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
    y: {
      beginAtZero: true,
      grid: { color: '#f1f5f9' },
      ticks: { color: '#64748b', callback: (v) => new Intl.NumberFormat('ru-RU').format(v) + ' ₽' },
    },
  },
}

const toggleableDatasets = [
  { key: 'sales', label: 'Сумма продаж', color: '#3b82f6' },
  { key: 'purchase', label: 'Закуп', color: '#ef4444' },
]
</script>
