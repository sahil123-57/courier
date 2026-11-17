import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory('/courier'),
  routes: [
    { path: '/', component: () => import('./pages/MyParcels.vue') },
    { path: '/book', component: () => import('./pages/Book.vue') },
    { path: '/track/:name', component: () => import('./pages/Track.vue'), props: true },
    { path: '/label/:name', component: () => import('./pages/Label.vue'), props: true },
  ],
})
