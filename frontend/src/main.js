import { createApp } from 'vue'
import App from './App.vue'
import { 
  ConfigProvider, Tabbar, TabbarItem, NavBar, Grid, GridItem, Image as VanImage, 
  Button, Toast, PullRefresh, Popup,
  Tag, Cell, CellGroup, Field, Dialog, 
  Tab, Tabs, Empty,
  Form, Icon,
} from 'vant'
import 'vant/lib/index.css'

const app = createApp(App)
app.use(ConfigProvider).use(Tabbar).use(TabbarItem).use(NavBar).use(Grid).use(GridItem)
app.use(VanImage).use(Button).use(Toast).use(PullRefresh).use(Popup).use(Tag).use(Cell).use(CellGroup)
app.use(Field).use(Dialog).use(Tab).use(Tabs).use(Empty)
app.use(Form).use(Icon)
app.mount('#app')