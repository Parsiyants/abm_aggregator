// composables/useFunction.js
import { useAppStore } from '@/stores/app'
import { useNotificationStore } from '@/stores/notifications'

export function useFunction() {
  const appStore = useAppStore()
  const notify = useNotificationStore()

  // ────────────────────────────────────────────────────────────
  // 1. Базовые функции
  // ────────────────────────────────────────────────────────────

  const copy = (text) => {
    if (!text) return

    const doCopy = () => {
      if (navigator.clipboard?.writeText) {
        return navigator.clipboard.writeText(text)
      }
      return new Promise((resolve, reject) => {
        const input = document.createElement('input')
        input.value = text
        input.style.position = 'fixed'
        input.style.opacity = '0'
        document.body.appendChild(input)
        input.select()
        try {
          const success = document.execCommand('copy')
          document.body.removeChild(input)
          success ? resolve() : reject(new Error('execCommand failed'))
        } catch (err) {
          document.body.removeChild(input)
          reject(err)
        }
      })
    }

    doCopy()
      .then(() => {
        notify.add(`Скопировано: ${text}`, 'success', 2000)
      })
      .catch((err) => {
        console.error('Copy failed:', err)
        notify.add('Не удалось скопировать', 'error')
      })
  }

  const formatDate = (dateStr, onlyDate = false) => {
    if (!dateStr) return '—'
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr

    return d.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: onlyDate ? undefined : '2-digit',
      minute: onlyDate ? undefined : '2-digit',
    })
  }

  const formatPrice = (val) => {
    const num = parseFloat(val)
    if (isNaN(num)) return '0 ₽'
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0,
    }).format(num)
  }

  // ────────────────────────────────────────────────────────────
  // 2. Группировка статусов маркетплейсов с описаниями
  // ────────────────────────────────────────────────────────────

  // ПОЛНЫЙ СПИСОК СТАТУСОВ С ОПИСАНИЯМИ
  // Каждый статус имеет: label (русское название), description (описание из документации)
  const STATUS_GROUPS = {
    new: {
      label: 'Новый',
      value: 'new',
      statuses: [
        { code: 'awaiting_packaging', description: 'Ожидает упаковки' },
        { code: 'waiting', description: 'Сборочное задание в работе' },
        { code: 'PROCESSING', description: 'Находится в обработке' },
        { code: 'PLACING', description: 'Оформляется, подготовка к резервированию' },
        { code: 'RESERVED', description: 'Зарезервирован, но недооформлен (только для LaaS)' },
        { code: 'PENDING', description: 'Ожидает обработки со стороны продавца' },
        { code: 'awaiting_verification', description: 'Создано' },
        { code: 'awaiting_approve', description: 'Ожидает подтверждения' },
        { code: 'awaiting_registration', description: 'Ожидает регистрации' },
      ],
    },
    assembled: {
      label: 'Собран',
      value: 'assembled',
      statuses: [
        { code: 'awaiting_deliver', description: 'Ожидает отгрузки' },
        { code: 'sorted', description: 'Сборочное задание отсортировано' },
        { code: 'PICKUP', description: 'Доставлен в пункт выдачи' },
        { code: 'ready_for_pickup', description: 'Заказ прибыл на пункт выдачи заказов (ПВЗ)' },
        { code: 'driver_pickup', description: 'У водителя' },
        { code: 'acceptance_in_progress', description: 'Идёт приёмка' },
      ],
    },
    in_delivery: {
      label: 'В доставке',
      value: 'in_delivery',
      statuses: [
        { code: 'delivering', description: 'Доставляется' },
        { code: 'accepted_by_carrier', description: 'Продавец передал заказ в службу доставки в своей стране' },
        { code: 'DELIVERY', description: 'Передан в службу доставки' },
        { code: 'sent_to_carrier', description: 'Заказ отправлен на склад службы доставки в стране продавца' },
        { code: 'UNPAID', description: 'Оформлен, но еще не оплачен (если выбрана оплата при оформлении)' },
      ],
    },
    delivered: {
      label: 'Доставлен',
      value: 'delivered',
      statuses: [
        { code: 'delivered', description: 'Доставлен' },
        { code: 'sold', description: 'Заказ получен покупателем' },
        { code: 'DELIVERED', description: 'Получен покупателем' },
      ],
    },
    cancelled: {
      label: 'Отменён',
      value: 'cancelled',
      statuses: [
        { code: 'cancelled', description: 'Отменено' },
        { code: 'canceled', description: 'Отмена сборочного задания' },
        { code: 'CANCELLED', description: 'Отменен' },
        { code: 'canceled_by_client', description: 'Покупатель отменил заказ при получении' },
        { code: 'declined_by_client', description: 'Покупатель отменил заказ. Отмена доступна покупателю в первый час с момента заказа, если заказ не переведён на сборку' },
        { code: 'defect', description: 'Отмена заказа по причине брака' },
        { code: 'canceled_by_carrier', description: 'Заказ отменён перевозчиком. Только для трансграничных поставок' },
        { code: 'cancelled_from_split_pending', description: 'Отменено из-за разделения отправления' },
        { code: 'not_accepted', description: 'Не принято на сортировочном центре' },
        { code: 'arbitration', description: 'Арбитраж' },
        { code: 'client_arbitration', description: 'Клиентский арбитраж доставки' },
        { code: 'UNKNOWN', description: 'Неизвестный статус' },
      ],
    },
    partial_returned: {
      label: 'Частичный возврат',
      value: 'partial_returned',
      statuses: [
        { code: 'PARTIALLY_RETURNED', description: 'Возвращен частично' },
      ],
    },
    returned: {
      label: 'Возврат',
      value: 'returned',
      statuses: [
        { code: 'RETURNED', description: 'Возвращен полностью' },
      ],
    },
  }

  // Обратный словарь: статус МП → группа
  const statusToGroupMap = {}
  const statusDescriptionMap = {}
  
  Object.values(STATUS_GROUPS).forEach((group) => {
    group.statuses.forEach(({ code, description }) => {
      statusToGroupMap[code] = group.value
      statusDescriptionMap[code] = `${code} - ${description}`
    })
  })

  // Цвета для групп
  const GROUP_COLORS = {
    new: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200' },
    assembled: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-200' },
    in_delivery: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200' },
    delivered: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-200' },
    cancelled: { bg: 'bg-rose-100', text: 'text-rose-700', border: 'border-rose-200' },
    partial_returned: { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-200' },
    returned: { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-200' },
  }

  // ────────────────────────────────────────────────────────────
  // 3. Публичные методы для работы со статусами
  // ────────────────────────────────────────────────────────────

  /**
   * Получить русское название статуса
   */
  const getRussianStatus = (marketplaceStatus) => {
    if (!marketplaceStatus) return '—'
    const groupKey = statusToGroupMap[marketplaceStatus]
    return groupKey ? STATUS_GROUPS[groupKey].label : marketplaceStatus
  }

  /**
   * Получить описание статуса (для title)
   */
  const getStatusDescription = (marketplaceStatus) => {
    if (!marketplaceStatus) return '—'
    return statusDescriptionMap[marketplaceStatus] || 'Статус без описания'
  }

  /**
   * Получить полную информацию о статусе (название + описание)
   */
  const getStatusInfo = (marketplaceStatus) => {
    if (!marketplaceStatus) return { label: '—', description: '—', group: null }
    const groupKey = statusToGroupMap[marketplaceStatus]
    return {
      label: groupKey ? STATUS_GROUPS[groupKey].label : marketplaceStatus,
      description: statusDescriptionMap[marketplaceStatus] || 'Статус без описания',
      group: groupKey ? STATUS_GROUPS[groupKey] : null,
    }
  }

  /**
   * Получить группу статуса
   */
  const getStatusGroup = (marketplaceStatus) => {
    if (!marketplaceStatus) return null
    const groupKey = statusToGroupMap[marketplaceStatus]
    return groupKey ? STATUS_GROUPS[groupKey] : null
  }

  /**
   * Получить CSS-классы для бейджа статуса (с учётом описания в title)
   */
  const getStatusBadgeClasses = (marketplaceStatus) => {
    if (!marketplaceStatus) return { bg: 'bg-gray-100', text: 'text-gray-700' }
    const groupKey = statusToGroupMap[marketplaceStatus]
    return groupKey ? GROUP_COLORS[groupKey] : { bg: 'bg-gray-100', text: 'text-gray-700' }
  }

  /**
   * Получить список статусов МП для группы (для фильтрации на бекенде)
   */
  const getStatusesForGroup = (groupValue) => {
    const group = STATUS_GROUPS[groupValue]
    return group ? group.statuses.map((s) => s.code) : []
  }

  /**
   * Получить все группы для фильтров
   */
  const getStatusFilterOptions = () => {
    return Object.values(STATUS_GROUPS).map((group) => ({
      label: group.label,
      value: group.value,
      statuses: group.statuses.map((s) => s.code),
    }))
  }

  /**
   * Проверить, входит ли статус МП в группу
   */
  const isStatusInGroup = (marketplaceStatus, groupValue) => {
    const group = STATUS_GROUPS[groupValue]
    return group ? group.statuses.some((s) => s.code === marketplaceStatus) : false
  }

  // ────────────────────────────────────────────────────────────
  // 3.1 Детализированные статусы (substatus)
  // ────────────────────────────────────────────────────────────

  // Ozon отдаёт substatus в формате posting_* — переводим в читаемый вид
  const SUBSTATUS_LABELS = {
    posting_created: 'Создан',
    posting_awaiting_registration: 'Ожидает регистрации',
    posting_awaiting_passport_data: 'Ожидает паспортных данных',
    posting_awaiting_approve: 'Ожидает подтверждения',
    posting_on_way_to_ozon: 'В пути в Ozon',
    posting_in_process_at_ozon: 'В обработке Ozon',
    posting_received: 'Принят',
    posting_on_way_to_city: 'В пути в город',
    posting_in_customer_city: 'В городе получателя',
    posting_in_pickup_point: 'В пункте выдачи',
    posting_transferring_to_delivery: 'Передаётся в доставку',
    posting_delivering: 'Доставляется',
    posting_conditionally_delivered: 'Условно доставлен',
    posting_delivered: 'Доставлен',
    posting_canceled: 'Отменён',
    posting_returned: 'Возвращён',
  }

  /**
   * Получить читаемое название детализированного статуса
   */
  const getSubstatusLabel = (substatus) => {
    if (!substatus) return ''
    return SUBSTATUS_LABELS[substatus] || substatus
  }

  // ────────────────────────────────────────────────────────────
  // 3.2 Цвета маркетплейсов
  // ────────────────────────────────────────────────────────────

  const MARKET_COLORS = {
    ozon: {
      hex: '#2563eb',
      chip: 'border-blue-200 bg-blue-50 text-blue-700',
      bar: 'bg-blue-500',
    },
    yandex: {
      hex: '#fbbf24',
      chip: 'border-amber-200 bg-amber-50 text-amber-700',
      bar: 'bg-amber-400',
    },
    wb: {
      hex: '#a855f7',
      chip: 'border-purple-200 bg-purple-50 text-purple-700',
      bar: 'bg-purple-500',
    },
    avito: {
      hex: '#22c55e',
      chip: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      bar: 'bg-emerald-500',
    },
  }

  /**
   * Цветовая схема маркетплейса: hex, классы чипа и полосы
   */
  const getMarketColor = (marketType) =>
    MARKET_COLORS[marketType] || {
      hex: '#94a3b8',
      chip: 'border-slate-200 bg-slate-100 text-slate-600',
      bar: 'bg-slate-400',
    }

  /**
   * Сортировка справочников по полю index (статусы, поставщики)
   */
  const sortByIndex = (list) =>
    [...(list || [])].sort((a, b) => (Number(a?.index) || 0) - (Number(b?.index) || 0))

  // ────────────────────────────────────────────────────────────
  // 4. Публичные методы для работы с процессами
  // ────────────────────────────────────────────────────────────
  const getProcessStatus = (status) => {
    const map = {
      New: { color: 'bg-blue-500 text-white', label: 'Новый' },
      Process: { color: 'bg-amber-500 text-white', label: 'В Процессе' },
      Done: { color: 'bg-emerald-500 text-white', label: 'Завершён' },
      Cancel: { color: 'bg-rose-500 text-white', label: 'Отменён' },
    }
    return map[status] || { color: 'bg-gray-500 text-white', label: status || '—' }
  }



  // ────────────────────────────────────────────────────────────
  // 5. PDF
  // ────────────────────────────────────────────────────────────

  function openPDF(orders, selectedDate) {
    if (!orders.length) {
      alert('Нет заказов на эту дату')
      return
    }

    const pdfWindow = window.open('', '_blank')
    if (!pdfWindow) {
      alert('Разрешите всплывающие окна в браузере')
      return
    }

    pdfWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Отгрузки на ${formatDate(selectedDate.value)}</title>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
      <style>
        body { font-family: Arial, sans-serif; margin: 40px; font-size: 14px; }
        h1 { text-align: center; color: #1e40af; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 40px; }
        th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; }
        th { background-color: #f3f4f6; font-weight: 600; }
        .sub-table { margin-left: 30px; }
        .sub-table th { background-color: #f9fafb; }
        .total { font-weight: bold; text-align: right; }
      </style>
    </head>
    <body>
      <h1>Отгрузки на ${formatDate(selectedDate.value)}</h1>
      <p class="text-center mb-8">Всего заказов: ${orders.length}</p>

      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Маркет / Кабинет</th>
            <th>Номер заказа</th>
            <th>Цена / Кол-во</th>
            <th>Дата заказа</th>
            <th>Дата отгрузки</th>
            <th>Моя дата</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          ${orders
            .map(
              (order, index) => `
            <tr>
              <td>${index + 1}</td>
              <td>
                <div>${order.cabinet_info?.name || order.cabinet_name}</div>
                <div class="text-xs text-gray-500">${order.market_type?.toUpperCase()}</div>
              </td>
              <td>${order.order_id}</td>
              <td class="text-right">
                ${formatPrice(order.price)} ₽<br>
                <span class="text-xs text-gray-500">${order.order_count || 1} шт</span>
              </td>
              <td>${formatDate(order.order_date)}</td>
              <td>${formatDate(order.send_date)}</td>
              <td>${order.my_send_date ? formatDate(order.my_send_date) : '—'}</td>
              <td><span title="${getStatusDescription(order.market_status)}">${getRussianStatus(order.market_status)}</span></td>
            </tr>
          `,
            )
            .join('')}
        </tbody>
      </table>

      ${orders
        .map(
          (order, index) => `
        <div class="mt-12">
          <h2 class="text-xl font-bold mb-4">Заказ ${order.order_id} (${order.cabinet_info?.name || order.cabinet_name})</h2>
          <table class="sub-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Артикул</th>
                <th>Цена / Кол-во</th>
                <th>Закуп</th>
                <th>Поставщик</th>
                <th>Статус</th>
                <th>Название</th>
              </tr>
            </thead>
            <tbody>
              ${order.items
                ?.map(
                  (item, i) => `
                <tr>
                  <td>${i + 1}</td>
                  <td class="font-mono">${item.article}</td>
                  <td class="text-right">${formatPrice(item.price)} ₽ × ${item.count || 1}</td>
                  <td class="text-right">${item.purchase ? formatPrice(item.purchase) + ' ₽' : '—'}</td>
                  <td>${item.provider || '—'}</td>
                  <td><span title="${getStatusDescription(item.status)}">${item.status || '—'}</span></td>
                  <td>${item.name}</td>
                </tr>
              `,
                )
                .join('')}
            </tbody>
          </table>
        </div>
      `,
        )
        .join('')}

      <div class="mt-8 text-center">
        <button id="downloadBtn" class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          Скачать PDF
        </button>
      </div>

      <script>
        document.getElementById('downloadBtn').addEventListener('click', () => {
          const element = document.body;
          const opt = {
            margin: 10,
            filename: 'отгрузки_${formatDate(selectedDate.value)}.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
          };
          html2pdf().set(opt).from(element).save();
        });

        window.onload = function() {
          window.print();
        };
      </script>
    </body>
    </html>
  `)

    pdfWindow.document.close()
  }

  // ────────────────────────────────────────────────────────────
  // 6. Экспорт всех функций
  // ────────────────────────────────────────────────────────────

  return {
    // Базовые
    copy,
    formatDate,
    formatPrice,
    openPDF,

    // Статусы
    STATUS_GROUPS,
    getRussianStatus,
    getStatusDescription,
    getStatusInfo,
    getStatusGroup,
    getStatusBadgeClasses,
    getStatusesForGroup,
    getStatusFilterOptions,
    isStatusInGroup,
    getSubstatusLabel,
    getMarketColor,
    sortByIndex,

    getProcessStatus
  }
}