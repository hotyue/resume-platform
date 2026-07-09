import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import { 
  ConfigProvider, Tabbar, TabbarItem, NavBar, Grid, GridItem, Image as VanImage, 
  Button, Toast, PullRefresh, Popup,
  Tag, Cell, CellGroup, Field, Dialog, 
  Tab, Tabs, Empty,
  Form, Icon, Loading, ActionSheet,
  Radio, RadioGroup,
} from 'vant'
import 'vant/lib/index.css'

const pinia = createPinia()
const app = createApp(App)
app.use(pinia)
app.use(router)
app.use(ConfigProvider).use(Tabbar).use(TabbarItem).use(NavBar).use(Grid).use(GridItem)
app.use(VanImage).use(Button).use(Toast).use(PullRefresh).use(Popup).use(Tag).use(Cell).use(CellGroup)
app.use(Field).use(Dialog).use(Tab).use(Tabs).use(Empty)
app.use(Form).use(Icon).use(Loading).use(ActionSheet).use(Radio).use(RadioGroup)
app.mount('#app')
