<script setup>
import { ref } from 'vue'
import { useFunction } from '@/composables/function'

const props = defineProps({
  orders: { type: Array, default: () => [] },
  selectedDateFrom: { type: [String, Date], default: () => new Date() },
  selectedDateTo: { type: [String, Date], default: () => new Date() },
})

const { getRussianStatus, getSubstatusLabel } = useFunction()

const loading = ref(false)


/* ── форматирование ──────────────────────────────────────── */

const esc = (value) =>
  String(value ?? '').replace(/[&<>"']/g, (c) => {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  })

function num(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(Math.round(n))
}

function shortDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function periodLabel() {
  const from = shortDate(props.selectedDateFrom)
  const to = shortDate(props.selectedDateTo)
  if (from === '—' && to === '—') return 'за всё время'
  if (from === to) return from
  return `${from} — ${to}`
}

const orderItems = (order) => (Array.isArray(order.items) ? order.items : [])

function unitsCount(order) {
  const items = orderItems(order)
  if (items.length) return items.reduce((sum, i) => sum + (Number(i.count) || 1), 0)
  return Number(order.order_count) || 1
}

function orderSum(order) {
  const total = Number(order.price) || 0
  if (total > 0) return total
  return orderItems(order).reduce((acc, i) => acc + (Number(i.price) || 0) * (Number(i.count) || 1), 0)
}

function buildTotals() {
  let positions = 0
  let units = 0
  let sum = 0
  for (const order of props.orders) {
    positions += orderItems(order).length || 1
    units += unitsCount(order)
    sum += orderSum(order)
  }
  return { positions, units, sum }
}

/* ── построение строк таблицы ────────────────────────────── */

function buildTableRows() {
  return props.orders
    .map((order, idx) => {
      const items = orderItems(order)
      const market = String(order.market_type || '—').toUpperCase()
      const cabinet = order.cabinet_info?.name || order.cabinet_name || 'Без имени'
      const orderNo = order.order_number || order.order_id || '—'
      const status = getRussianStatus(order.market_status)
      const substatus = order.substatus ? getSubstatusLabel(order.substatus) : ''
      const statusText = substatus && substatus !== '—' ? `${status} · ${substatus}` : status

      const headRow = `
        <tr class="ord">
          <td colspan="7">
            <div class="oline">
              <span class="oi-n">${idx + 1}</span>
              <span class="oi-mk">${esc(market)}</span>
              <span class="oi-cab">${esc(cabinet)}</span>
              <span class="oi-no">№ ${esc(orderNo)}</span>
              <span class="oi-d">созд. ${shortDate(order.order_date)} → отгр. ${shortDate(order.send_date)}${
                order.my_send_date ? ` · моя ${shortDate(order.my_send_date)}` : ''
              }</span>
              <span class="oi-sum">${num(orderSum(order))} ₽ · ${num(unitsCount(order))} шт</span>
              <span class="oi-st">${esc(statusText)}</span>
            </div>
          </td>
        </tr>`

      const itemRows = (items.length ? items : [null])
        .map((item) => {
          const cells = item
            ? `<td class="c-art">${esc(item.article || '—')}</td>
               <td class="c-name">${esc(item.name || '—')}</td>
               <td class="c-qty">${num(item.count || 1)}</td>
               <td class="c-money">${num(item.price)}</td>
               <td class="c-money">${item.purchase ? num(item.purchase) : '—'}</td>
               <td class="c-prov">${esc(item.provider || '—')}</td>
               <td class="c-status">${esc(item.status || '—')}</td>`
            : `<td class="c-art muted">—</td>
               <td class="c-name muted">Позиции не указаны</td>
               <td class="c-qty">${num(unitsCount(order))}</td>
               <td class="c-money">—</td>
               <td class="c-money">—</td>
               <td class="c-prov">—</td>
               <td class="c-status">—</td>`

          return `<tr class="item">${cells}</tr>`
        })
        .join('')

      return headRow + itemRows
    })
    .join('')
}

/* ── сборка документа печати ─────────────────────────────── */

function buildDocument() {
  const { positions, units, sum } = buildTotals()

  return `<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<title>Отгрузки ${esc(periodLabel())}</title>
<style>
  @page { size: A4 portrait; margin: 6mm 6mm; }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 7pt; line-height: 1.12; color: #000;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }

  /* превью на экране */
  @media screen {
    body { background: #f1f5f9; padding: 8mm 4mm; }
    .page { max-width: 210mm; margin: 0 auto; background: #fff; padding: 7mm; box-shadow: 0 8px 30px -12px rgba(15,23,42,.35); }
  }

  /* шапка */
  .head { display: flex; align-items: flex-end; justify-content: space-between; gap: 8mm;
          border-bottom: 1.2pt solid #000; padding-bottom: .8mm; margin-bottom: 1.2mm; }
  .head h1 { margin: 0; font-size: 10.5pt; letter-spacing: -.2pt; }
  .head .per { margin-top: .4mm; font-size: 7pt; color: #333; }
  .stats { display: flex; gap: 4.5mm; }
  .stat { text-align: right; }
  .stat b { display: block; font-size: 9.2pt; line-height: 1.05; }
  .stat span { display: block; margin-top: .2mm; font-size: 5.8pt; letter-spacing: .4pt;
               text-transform: uppercase; color: #444; }

  /* таблица */
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  thead { display: table-header-group; }
  th { padding: .55mm 1mm; font-size: 5.6pt; font-weight: 700; letter-spacing: .3pt;
       text-transform: uppercase; color: #000; text-align: left;
       background: #e4e4e7; border-bottom: .7pt solid #000; }
  th.r { text-align: right; }
  th.c { text-align: center; }
  td { padding: .2mm 1mm; vertical-align: middle; border-bottom: .3pt solid #d4d4d8; }
  tr.item { break-inside: avoid; page-break-inside: avoid; }

  /* строка заказа — одна линия */
  tr.ord > td { padding: .35mm 1mm; background: #efefef;
                border-top: .7pt solid #000; border-bottom: .5pt solid #8a8a8a; }
  tr.ord { break-after: avoid; page-break-after: avoid; break-inside: avoid; }
  .oline { display: flex; align-items: baseline; gap: 1.6mm; white-space: nowrap;
           font-size: 7pt; line-height: 1.2; }
  .oi-n { width: 4.5mm; flex: none; font-weight: 700; }
  .oi-mk { flex: none; padding: 0 1mm; border: .5pt solid #000; border-radius: .6mm;
           font-size: 5.8pt; font-weight: 700; letter-spacing: .4pt; }
  .oi-cab { flex: 0 1 auto; max-width: 44mm; overflow: hidden; text-overflow: ellipsis; font-weight: 700; }
  .oi-no { flex: none; font-variant-numeric: tabular-nums; }
  .oi-d { flex: none; color: #333; font-variant-numeric: tabular-nums; }
  .oi-st { flex: 0 1 auto; max-width: 40mm; overflow: hidden; text-overflow: ellipsis; color: #222; }
  .oi-sum { flex: none; margin-left: auto; font-weight: 700; font-variant-numeric: tabular-nums; }

  /* колонки товара */
  .c-art { font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
           font-size: 6.4pt; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .c-name { font-size: 7pt; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .c-qty { text-align: center; font-weight: 600; }
  .c-money { text-align: right; font-variant-numeric: tabular-nums; }
  .c-prov, .c-status { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 6.6pt; }
  .muted { color: #777; font-style: italic; }

  /* подвал */
  .foot { display: flex; justify-content: space-between; gap: 5mm;
          margin-top: .8mm; padding-top: .5mm; border-top: .5pt solid #8a8a8a;
          font-size: 6pt; color: #333; }
</style>
</head>
<body>
<div class="page">
  <div class="head">
    <div>
      <h1>Список отгрузок</h1>
      <div class="per">Период отгрузки: ${esc(periodLabel())}</div>
    </div>
    <div class="stats">
      <div class="stat"><b>${num(props.orders.length)}</b><span>заказов</span></div>
      <div class="stat"><b>${num(positions)}</b><span>позиций</span></div>
      <div class="stat"><b>${num(units)}</b><span>штук</span></div>
      <div class="stat"><b>${num(sum)} ₽</b><span>сумма</span></div>
    </div>
  </div>

  <table>
    <colgroup>
      <col style="width:26mm" />
      <col />
      <col style="width:9mm" />
      <col style="width:15mm" />
      <col style="width:15mm" />
      <col style="width:22mm" />
      <col style="width:20mm" />
    </colgroup>
    <thead>
      <tr>
        <th>Артикул</th>
        <th>Наименование</th>
        <th class="c">Кол</th>
        <th class="r">Цена ₽</th>
        <th class="r">Закуп ₽</th>
        <th>Поставщик</th>
        <th>Статус</th>
      </tr>
    </thead>
    <tbody>${buildTableRows()}</tbody>
  </table>

  <div class="foot">
    <span>Сформировано: ${esc(new Date().toLocaleString('ru-RU'))}</span>
    <span>Заказов: ${num(props.orders.length)} · Позиций: ${num(positions)} · Сумма: ${num(sum)} ₽</span>
  </div>
</div>
</body>
</html>`
}

/* ── печать ──────────────────────────────────────────────── */

function printShipments() {
  if (!props.orders.length || loading.value) return

  loading.value = true

  // Окно создаём синхронно в обработчике клика — иначе браузер заблокирует попап
  const printWindow = window.open('', '_blank', 'width=1100,height=850')

  if (!printWindow) {
    loading.value = false
    return
  }

  printWindow.document.open()
  printWindow.document.write(buildDocument())
  printWindow.document.close()

  // Печатаем после отрисовки. Окно НЕ закрываем: если вызвать close() сразу после
  // print(), браузер (Chrome) закрывает вкладку раньше, чем покажет диалог печати.
  setTimeout(() => {
    try {
      printWindow.focus()
      printWindow.print()
    } catch (err) {
      console.error('Не удалось открыть диалог печати:', err)
    }
    loading.value = false
  }, 300)
}
</script>

<template>
  <button
    type="button"
    @click="printShipments"
    :disabled="loading || !orders.length"
    class="btn-icon disabled:cursor-not-allowed disabled:opacity-40"
    title="Печать списка отгрузок"
  >
    <span v-if="!loading" class="material-symbols-outlined text-[19px]">print</span>
    <span v-else class="material-symbols-outlined animate-spin text-[19px]">progress_activity</span>
  </button>
</template>

