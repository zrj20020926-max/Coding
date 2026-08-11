import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router, { loginRedirect } from './router'
import { configureAuthSessionHandlers } from './services/http'
import { useAuthStore } from './stores/auth'
// Preload styles used by the route-level discussion editor. This keeps Vite from
// invalidating its dependency graph when parallel E2E workers first open the route.
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
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
app.mount('#app')
