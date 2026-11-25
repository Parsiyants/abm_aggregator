<template>
  <!-- Если страница авторизации — показываем без navbar -->
  <AuthLayout v-if="isAuthPage">
    <router-view />
  </AuthLayout>
  
  <!-- Иначе — с navbar -->
  <DefaultLayout v-else>
    <router-view />
  </DefaultLayout>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'

const route = useRoute()

// Определяем, страница авторизации или нет
const isAuthPage = computed(() => {
  return route.meta?.layout === 'auth'
})
</script>