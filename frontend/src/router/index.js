import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import JupyterPanel from '../views/JupyterPanel.vue'
import FileBrowser from '../views/FileBrowser.vue'
import FileViewer from '../views/FileViewer.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      {
        path: '',
        name: 'jupyter',
        component: JupyterPanel
      },
      {
        path: 'files/:path(.*)',
        name: 'files',
        component: FileBrowser,
        props: true
      },
      {
        path: 'files',
        name: 'files-default',
        redirect: { name: 'files', params: { path: '~' } }
      }
    ]
  },
  // File viewer route - standalone (not inside MainLayout) for new tab experience
  {
    path: '/view/:path(.*)',
    name: 'view',
    component: FileViewer,
    props: true
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
