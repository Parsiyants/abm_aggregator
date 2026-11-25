<template>
  <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4">
    <div
      class="w-full max-w-md rounded-2xl border border-slate-200/70 bg-white p-8 shadow-[0_18px_50px_-24px_rgba(15,23,42,0.25)]"
    >
      <div class="mb-8 flex flex-col items-center gap-3">
        <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-sm font-bold text-white">
          AB
        </span>
        <div class="text-center">
          <h1 class="text-xl font-semibold tracking-tight text-slate-900">Вход в ABMauto</h1>
          <p class="mt-1 text-sm text-slate-500">Агрегатор заказов маркетплейсов</p>
        </div>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-5">
        <div>
          <label class="field-label" for="email">Email</label>
          <input
            class="input-field h-11"
            type="email"
            id="email"
            v-model="email"
            placeholder="you@example.com"
            required
          />
        </div>

        <div>
          <label class="field-label" for="password">Пароль</label>
          <input
            class="input-field h-11"
            type="password"
            id="password"
            v-model="password"
            placeholder="••••••••"
            required
          />
        </div>

        <button type="submit" class="btn-primary h-11 w-full" :disabled="isLoading">
          {{ isLoading ? 'Загрузка…' : 'Войти' }}
        </button>

        <p v-if="error" class="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-600">{{ error }}</p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth'; // Наш Pinia Store

const email = ref('');
const password = ref('');
const isLoading = ref(false);
const error = ref(null);

const authStore = useAuthStore();
const router = useRouter();

/**
 * Обрабатывает отправку формы входа.
 */
const handleLogin = async () => {
  isLoading.value = true;
  error.value = null;

  try {
    // Вызываем действие login из Pinia Store
    const success = await authStore.login(email.value, password.value);
    
    if (success) {
      // Перенаправляем на главную страницу после успешного входа
      router.push('/');
    }
  } catch (err) {
    // Обработка ошибок, возвращаемых FastAPI
    const message = err.response?.data?.detail || 'Не удалось войти. Проверьте данные.';
    error.value = message;
    console.error("Login error:", err);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
</style>