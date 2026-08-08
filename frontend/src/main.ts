import { createPinia } from 'pinia'
import { createApp } from 'vue'

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router, { loginRedirect } from './router'
import { configureAuthSessionHandlers } from './services/http'
import { useAuthStore } from './stores/auth'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const auth = useAuthStore(pinia)
configureAuthSessionHandlers({
  onSessionRefreshed: (response) => auth.acceptSession(response.access_token, response.user),
  onSessionExpired: () => {
    auth.clearSession()
    if (router.currentRoute.value.name !== 'login') {
      void router.replace(loginRedirect(router.currentRoute.value.fullPath))
    }
  },
})

app.use(router)
app.use(ElementPlus)
app.mount('#app')
