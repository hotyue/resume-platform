import { createApp } from 'vue'
import App from './App.vue'
import { ConfigProvider, Tabbar, TabbarItem, NavBar, Grid, GridItem, Image as VanImage, Button, Toast } from 'vant'
import 'vant/lib/index.css'

const app = createApp(App)

// 注册需要的 Vant 组件
app.use(ConfigProvider)
app.use(Tabbar).use(TabbarItem)
app.use(NavBar)
app.use(Grid).use(GridItem)
app.use(VanImage)
app.use(Button)
app.use(Toast)

app.mount('#app')
