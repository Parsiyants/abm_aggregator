// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/Login.vue'),
      meta: { 
        requiresAuth: false,
        layout: 'auth'  // ← маркер для страниц авторизации
      }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/Register.vue'),
      meta: { 
        requiresAuth: false,
        layout: 'auth'
      }
    },
    {
      path: '/',
      name: 'new',
      component: () => import('../views/NewOrdersList.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/send',
      name: 'send',
      component: () => import('../views/SendOrderList.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/orders',
      name: 'orders',
      component: () => import('../views/OrdersView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/orders/:id',
      name: 'order-details',
      component: () => import('../views/OrderDetailsView.vue'),
      props: true,
      meta: { requiresAuth: true }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('../views/AnalyticsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('../views/LogsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/'
    }
  ],
})

// ============================================================
// ГВАРД: проверка авторизации
// ============================================================
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // Проверяем, требует ли маршрут авторизации
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  
  // Если маршрут требует авторизации, но пользователь не авторизован
  if (requiresAuth && !authStore.isLoggedIn) {
    // Запоминаем путь, куда хотел попасть пользователь
    authStore.redirectPath = to.fullPath
    next('/login')
  } 
  // Если пользователь авторизован и пытается зайти на логин/регистрацию
  else if ((to.name === 'login' || to.name === 'register') && authStore.isLoggedIn) {
    next('/')
  } 
  else {
    next()
  }
})

export default router