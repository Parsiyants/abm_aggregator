// composables/useSound.js
import { ref } from 'vue'

export function useSound() {
  const isEnabled = ref(true)
  let audioContext = null

  // ── Громкий и звучный звук для нового заказа ────────────
  const playSound = () => {
    if (!isEnabled.value) return

    try {
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)()
      }

      if (audioContext.state === 'suspended') {
        audioContext.resume()
      }

      const now = audioContext.currentTime

      // ── Основной звук ──
      // 1. Низкий тон (база)
      const osc1 = audioContext.createOscillator()
      const gain1 = audioContext.createGain()
      osc1.connect(gain1)
      gain1.connect(audioContext.destination)
      osc1.frequency.value = 523 // До
      osc1.type = 'sine'
      gain1.gain.setValueAtTime(0.4, now)
      gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.6)

      // 2. Средний тон (гармония)
      const osc2 = audioContext.createOscillator()
      const gain2 = audioContext.createGain()
      osc2.connect(gain2)
      gain2.connect(audioContext.destination)
      osc2.frequency.value = 659 // Ми
      osc2.type = 'sine'
      gain2.gain.setValueAtTime(0.35, now + 0.05)
      gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.55)

      // 3. Высокий тон (звон)
      const osc3 = audioContext.createOscillator()
      const gain3 = audioContext.createGain()
      osc3.connect(gain3)
      gain3.connect(audioContext.destination)
      osc3.frequency.value = 880 // Ля
      osc3.type = 'sine'
      gain3.gain.setValueAtTime(0.3, now + 0.1)
      gain3.gain.exponentialRampToValueAtTime(0.01, now + 0.5)

      osc1.start(now)
      osc1.stop(now + 0.6)
      osc2.start(now + 0.05)
      osc2.stop(now + 0.55)
      osc3.start(now + 0.1)
      osc3.stop(now + 0.5)

      // ── Второй аккорд (через 0.3 сек) ──
      const osc4 = audioContext.createOscillator()
      const gain4 = audioContext.createGain()
      osc4.connect(gain4)
      gain4.connect(audioContext.destination)
      osc4.frequency.value = 784 // Соль
      osc4.type = 'sine'
      gain4.gain.setValueAtTime(0.35, now + 0.35)
      gain4.gain.exponentialRampToValueAtTime(0.01, now + 0.9)

      const osc5 = audioContext.createOscillator()
      const gain5 = audioContext.createGain()
      osc5.connect(gain5)
      gain5.connect(audioContext.destination)
      osc5.frequency.value = 988 // Си
      osc5.type = 'sine'
      gain5.gain.setValueAtTime(0.3, now + 0.4)
      gain5.gain.exponentialRampToValueAtTime(0.01, now + 0.85)

      osc4.start(now + 0.35)
      osc4.stop(now + 0.9)
      osc5.start(now + 0.4)
      osc5.stop(now + 0.85)

    } catch (error) {
      console.warn('❌ Не удалось воспроизвести звук:', error)
    }
  }

  // ── Альтернативный звук (для разных событий) ─────────────
  const playSuccessSound = () => {
    if (!isEnabled.value) return

    try {
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)()
      }

      if (audioContext.state === 'suspended') {
        audioContext.resume()
      }

      const osc = audioContext.createOscillator()
      const gain = audioContext.createGain()

      osc.connect(gain)
      gain.connect(audioContext.destination)

      osc.frequency.value = 660
      osc.type = 'sine'

      gain.gain.setValueAtTime(0.2, audioContext.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.4)

      osc.start(audioContext.currentTime)
      osc.stop(audioContext.currentTime + 0.4)
    } catch (error) {
      console.warn('❌ Не удалось воспроизвести звук:', error)
    }
  }

  // Двойной "динь" (как в кассе)
  const playCashSound = () => {
    if (!isEnabled.value) return

    try {
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)()
      }

      const frequencies = [523, 659, 784] // До, Ми, Соль
      frequencies.forEach((freq, index) => {
        const osc = audioContext.createOscillator()
        const gain = audioContext.createGain()

        osc.connect(gain)
        gain.connect(audioContext.destination)

        osc.frequency.value = freq
        osc.type = 'sine'

        const startTime = audioContext.currentTime + index * 0.12
        gain.gain.setValueAtTime(0.2, startTime)
        gain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.15)

        osc.start(startTime)
        osc.stop(startTime + 0.15)
      })
    } catch (error) {
      console.warn('❌ Не удалось воспроизвести звук:', error)
    }
  }

  //Короткий "бип" (для уведомлений)
  const playBeepSound = () => {
    if (!isEnabled.value) return

    try {
      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)()
      }

      const osc = audioContext.createOscillator()
      const gain = audioContext.createGain()

      osc.connect(gain)
      gain.connect(audioContext.destination)

      osc.frequency.value = 600
      osc.type = 'square'

      gain.gain.setValueAtTime(0.15, audioContext.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.08)

      osc.start(audioContext.currentTime)
      osc.stop(audioContext.currentTime + 0.08)
    } catch (error) {
      console.warn('❌ Не удалось воспроизвести звук:', error)
    }
  }

  // ── Включить/выключить звук ──────────────────────────────
  const toggleSound = () => {
    isEnabled.value = !isEnabled.value
  }

  // ── Инициализация ──────────────────────────────────────────
  const init = () => {
    // Создаём контекст при инициализации (для авто-политики)
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)()
    } catch (e) {
      console.warn('❌ AudioContext не поддерживается:', e)
    }
  }

  return {
    isEnabled,
    playSound,
    playSuccessSound,
    playCashSound,
    playBeepSound,
    toggleSound,
    init,
  }
}
