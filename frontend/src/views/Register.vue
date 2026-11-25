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
        {{ isLoading ? 'Регистрация...' : 'Зарегистрироваться' }}
      </button>

      <p v-if="error" class="error-message">{{ error }}</p>
      
      <p class="link-text">
        Уже есть аккаунт? <router-link to="/login">Войти</router-link>
      </p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const email = ref('');
const password = ref('');
const isLoading = ref(false);
const error = ref(null);

const authStore = useAuthStore();
const router = useRouter();

const handleRegister = async () => {
  isLoading.value = true;
  error.value = null;

  try {
    await authStore.register(email.value, password.value);
    router.push('/');
  } catch (err) {
    const message = err.response?.data?.detail || 'Не удалось зарегистрироваться.';
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
.link-text {
  margin-top: 15px;
  text-align: center;
}
</style>