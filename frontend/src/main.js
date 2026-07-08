import { createApp } from 'vue'
import App from './App.vue'
// 引入缺少的 PullRefresh 和 Popup 组件
import { 
  ConfigProvider, Tabbar, TabbarItem, NavBar, 
  Grid, GridItem, Image as VanImage, Button, 
  Toast, PullRefresh, Popup 
} from 'vant'
import 'vant/lib/index.css'

const app = createApp(App)

app.use(ConfigProvider)
app.use(Tabbar).use(TabbarItem)
app.use(NavBar)
app.use(Grid).use(GridItem)
app.use(VanImage)
app.use(Button)
app.use(Toast)
// 注册缺少的组件
app.use(PullRefresh)
app.use(Popup)

app.mount('#app')
