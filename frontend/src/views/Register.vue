<template>
  <div class="auth-container">
    <h2>Регистрация</h2>
    
    <form @submit.prevent="handleRegister">
      
      <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" v-model="email" required>
      </div>
      
      <div class="form-group">
        <label for="password">Пароль</label>
        <input type="password" id="password" v-model="password" required>
      </div>
      
      <button type="submit" :disabled="isLoading">
        {{ isLoading ? 'Создание...' : 'Создать пользователя' }}
      </button>

      <p v-if="error" class="error-message">{{ error }}</p>
      <p v-if="success" class="success-message">{{ success }}</p>

      <p class="link-text">
        <router-link to="/">На главную</router-link>
        ·
        <router-link to="/login">Выйти</router-link>
      </p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';

const email = ref('');
const password = ref('');
const isLoading = ref(false);
const error = ref(null);
const success = ref(null);

const authStore = useAuthStore();

const handleRegister = async () => {
  isLoading.value = true;
  error.value = null;
  success.value = null;

  try {
    // Регистрация требует токена: доступна только авторизованным
    await authStore.register(email.value, password.value);
    success.value = `Пользователь ${email.value} создан`;
    email.value = '';
    password.value = '';
  } catch (err) {
    const message = err.response?.data?.detail || 'Не удалось создать пользователя.';
    error.value = message;
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
/* Стили из Login.vue */
.auth-container {
  max-width: 400px;
  margin: 50px auto;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  background-color: #f9f9f9;
}
.form-group {
  margin-bottom: 20px;
}
label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
}
input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
button {
  width: 100%;
  padding: 12px;
  background-color: #42b983; /* Vue Green */
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
button:disabled {
  background-color: #7bd4a3;
  cursor: not-allowed;
}
.error-message {
  color: red;
  margin-top: 15px;
}
.success-message {
  color: #2f855a;
  margin-top: 15px;
}
.link-text {
  margin-top: 15px;
  text-align: center;
}
</style>