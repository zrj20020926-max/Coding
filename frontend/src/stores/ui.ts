import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

type Theme = 'light' | 'dark'
const THEME_KEY = 'codearena.theme'

function initialTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useUiStore = defineStore('ui', () => {
  const theme = ref<Theme>(initialTheme())
  function toggleTheme(): void { theme.value = theme.value === 'light' ? 'dark' : 'light' }
  watch(theme, (value) => {
    localStorage.setItem(THEME_KEY, value)
    document.documentElement.dataset['theme'] = value
    document.documentElement.classList.toggle('dark', value === 'dark')
  }, { immediate: true })
  return { theme, toggleTheme }
})
