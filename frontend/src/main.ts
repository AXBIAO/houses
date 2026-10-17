// Modified for Houses (based on AIGCNEWS, AGPL-3.0)
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './fonts.css'
import './style.css'
import './mobile-reading.css'
import './comic-theme.css'
import './motion.css'
import App from './App.vue'
import router from './router'
import i18n, { installI18n } from './i18n'
import { installAppStyle, installAppTheme } from './theme'
import { installPressFeedback } from './motion/press'
import { useAuthStore } from './stores/authStore'
import { installPageHead } from './features/seo/pageHead'

const appStyleReady = installAppStyle()
const app = createApp(App)
installI18n()
installAppTheme()
const pinia = createPinia()

app.use(pinia)
app.use(i18n)
app.use(router)
// 每页的标题、描述与 noindex（所有路径拿到的是同一份 index.html）
installPageHead(router)

void appStyleReady.then(() => {
  app.mount('#app')
  installPressFeedback()
})

// 页面先可用，再异步确认已保存的登录状态。
void useAuthStore(pinia).ensureInitialized()

if (import.meta.env.PROD) {
  void import('./pwa/registerPwa').then(({ registerPwa }) => registerPwa())
}
void import('./pwa/installPrompt').then(({ initializeInstallPrompt }) => initializeInstallPrompt())
