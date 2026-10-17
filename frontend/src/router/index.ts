import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import HousesLayout from '@/layouts/HousesLayout.vue'

// meta：titleKey / descriptionKey 供 pageHead 设置标题与描述；noindex 的页面不让搜索引擎收录（父路由的 meta 会合并到子路由）
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: HousesLayout,
    children: [
      { path: '', name: 'home', component: () => import('@/views/HomeView.vue') },
      { path: 'listings', name: 'listings', component: () => import('@/views/ListingsView.vue'), meta: { titleKey: 'navigation.listings', descriptionKey: 'seo.listings' } },
      { path: 'listings/:id', name: 'listing-detail', component: () => import('@/views/ListingDetailView.vue'), meta: { customHead: true } },
      { path: 'map', name: 'map', component: () => import('@/views/MapView.vue'), meta: { titleKey: 'navigation.map', descriptionKey: 'seo.map' } },
      { path: 'ai', name: 'ai', component: () => import('@/views/AiSearchView.vue'), meta: { titleKey: 'navigation.ai', descriptionKey: 'seo.ai' } },
      { path: 'subscriptions', name: 'subscriptions', component: () => import('@/views/SubscriptionsView.vue'), meta: { titleKey: 'navigation.subscriptions', noindex: true } },
      {
        path: 'landlord',
        component: () => import('@/views/landlord/LandlordConsole.vue'),
        meta: { titleKey: 'navigation.landlord', noindex: true },
        children: [
          { path: '', name: 'landlord', component: () => import('@/views/landlord/LandlordOverview.vue') },
          { path: 'listings', name: 'landlord-listings', component: () => import('@/views/landlord/LandlordListings.vue') },
          { path: 'listings/:id', name: 'landlord-listing', component: () => import('@/views/landlord/ListingEditor.vue') },
          { path: 'estates', name: 'landlord-estates', component: () => import('@/views/landlord/LandlordEstates.vue') },
          { path: 'inquiries', name: 'landlord-inquiries', component: () => import('@/views/landlord/LandlordInquiries.vue') },
          { path: 'members', name: 'landlord-members', component: () => import('@/views/landlord/LandlordMembers.vue') },
          { path: 'leases', name: 'landlord-leases', component: () => import('@/views/landlord/LandlordLeases.vue') },
          { path: 'leases/new', name: 'landlord-lease-new', component: () => import('@/views/landlord/LeaseSign.vue') },
          { path: 'leases/:id(\\d+)', name: 'landlord-lease', component: () => import('@/views/landlord/LeaseDetail.vue') },
          { path: 'bills', name: 'landlord-bills', component: () => import('@/views/landlord/LandlordBills.vue') },
          { path: 'settings', name: 'landlord-settings', component: () => import('@/views/landlord/LandlordSettings.vue') },
        ],
      },
      {
        path: 'admin',
        component: () => import('@/views/admin/AdminConsole.vue'),
        meta: { titleKey: 'navigation.admin', noindex: true },
        children: [
          { path: '', name: 'admin', component: () => import('@/views/admin/AdminLandlords.vue') },
          { path: 'listings', name: 'admin-listings', component: () => import('@/views/admin/AdminListings.vue') },
          { path: 'settings', name: 'admin-settings', component: () => import('@/views/admin/AdminSettings.vue') },
        ],
      },
      { path: 'about', name: 'about', component: () => import('@/views/AboutView.vue'), meta: { titleKey: 'footer.about', descriptionKey: 'seo.about' } },
      { path: 'privacy', name: 'privacy', component: () => import('@/views/PrivacyView.vue'), meta: { titleKey: 'footer.privacy' } },
      { path: ':pathMatch(.*)*', name: 'not-found', component: () => import('@/views/PlaceholderView.vue'), meta: { titleKey: 'pages.notFound', noindex: true } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

export default router
