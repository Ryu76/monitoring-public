import { createRouter, createWebHistory } from 'vue-router'

const Dashboard = () => import('../components/Dashboard.vue')
const ServerDetail = () => import('../components/ServerDetail.vue')
const AgentList = () => import('../components/AgentList.vue')
const EventList = () => import('../components/EventList.vue')
const IncidentList = () => import('../components/IncidentList.vue')
const Login = () => import('../components/Login.vue')

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
