import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../components/Dashboard.vue'
import ServerDetail from '../components/ServerDetail.vue'
import AgentList from '../components/AgentList.vue'
import EventList from '../components/EventList.vue'
import IncidentList from '../components/IncidentList.vue'
import Login from '../components/Login.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: Login,
      meta: { layout: 'blank' }
    },
    {
      path: '/',
      name: 'home',
      component: Dashboard
    },
    {
      path: '/servers',
      name: 'servers',
      component: ServerDetail
    },
    {
      path: '/agents',
      name: 'agents',
      component: AgentList
    },
    {
      path: '/events',
      name: 'events',
      component: EventList
    },
    {
      path: '/incidents',
      name: 'incidents',
      component: IncidentList
    }
  ]
})

// 내비게이션 가드: 로그인되지 않으면 /login으로
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.name !== 'login' && !token) {
    next({ name: 'login' })
  } else {
    next()
  }
})

export default router
