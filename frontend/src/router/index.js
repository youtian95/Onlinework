import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import ProblemList from '../views/ProblemList.vue'
import ProblemDetail from '../views/ProblemDetail.vue'
import Ranking from '../views/Ranking.vue'
import Admin from '../views/Admin.vue'
import Documentation from '../views/Documentation.vue'

const routes = [
  { path: '/', component: Login },
  { path: '/docs', component: Documentation },
  { path: '/admin', component: Admin },
  { path: '/problems', component: ProblemList },
  { path: '/ranking', component: Ranking },
  { path: '/problems/:id', component: ProblemDetail }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
