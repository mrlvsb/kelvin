import { createApp } from 'vue'
//import './style.css'
import App from './App.vue'
//import ClassList from "./ClassList.vue";
//import "vue-router/dist/vue-router"
import router from "./router/index.ts"

// 5. Create and mount the root instance.
const app = createApp(App)
// Make sure to _use_ the router instance to make the
// whole app router-aware.
app.use(router)

//createApp(App).mount('#app')
app.mount('#app')

/*
const classlist = createApp(ClassList)
// Make sure to _use_ the router instance to make the
// whole app router-aware.
classlist.use(router)

//createApp(App).mount('#app')
classlist.mount('#app')
*/
