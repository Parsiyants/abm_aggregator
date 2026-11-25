export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  safelist: [
    // Цвета для карточек
    'hover:border-blue-600',
    'hover:border-yellow-400',
    'hover:border-purple-600',
    'hover:border-green-600',

    'border-blue-400',
    'border-yellow-400',
    'border-purple-400',
    'border-green-400',

    // Текстовые цвета
    'text-blue-800',
    'text-yellow-800',
    'text-purple-800',
    'text-green-800',

    // Фоновые цвета
    'bg-blue-100',
    'bg-yellow-100',
    'bg-purple-100',
    'bg-green-100',

    'bg-blue-200',
    'bg-yellow-200',
    'bg-purple-200',
    'bg-green-200',

    'bg-blue-600',
    'bg-yellow-400',
    'bg-purple-600',
    'bg-green-600',

    'hover:bg-blue-600',
    'hover:bg-yellow-400',
    'hover:bg-purple-600',
    'hover:bg-green-600',

    'bg-blue-100/50',
    'bg-yellow-100/50',
    'bg-purple-100/50',
    'bg-green-100/50',

    // Если нужны другие оттенки
    'border-l-blue-600',
    'border-l-yellow-400',
    'border-l-purple-600',
    'border-l-green-600',
  ],
  theme: { extend: {} },
  plugins: [],
}
