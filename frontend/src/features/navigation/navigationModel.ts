// Modified for Houses (based on AIGCNEWS, AGPL-3.0)
export interface NavigationItem {
  to: string
  labelKey: `navigation.${string}`
  /** Dock 上的短标题 */
  captionKey: `dock.${string}`
  exact: boolean
  /** 仅房东成员可见 */
  requiresLandlord?: boolean
  /** 仅平台管理员/超级管理员可见 */
  requiresPlatform?: boolean
  /** 主栏常驻；其余项在窄屏收进「更多」 */
  primary?: boolean
  icon: string
}

const svg = (body: string) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`

export const NAV_ITEMS: readonly NavigationItem[] = [
  {
    to: '/', labelKey: 'navigation.home', captionKey: 'dock.home', exact: true, primary: true,
    icon: svg('<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>'),
  },
  {
    to: '/listings', labelKey: 'navigation.listings', captionKey: 'dock.listings', exact: false, primary: true,
    icon: svg('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/><path d="M8 11h6M11 8v6"/>'),
  },
  {
    to: '/map', labelKey: 'navigation.map', captionKey: 'dock.map', exact: false, primary: true,
    icon: svg('<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>'),
  },
  {
    to: '/ai', labelKey: 'navigation.ai', captionKey: 'dock.ai', exact: false, primary: true,
    icon: svg('<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'),
  },
  {
    to: '/subscriptions', labelKey: 'navigation.subscriptions', captionKey: 'dock.subscriptions', exact: false,
    icon: svg('<path d="M6 8a6 6 0 1112 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 003.4 0"/>'),
  },
  {
    to: '/landlord', labelKey: 'navigation.landlord', captionKey: 'dock.landlord', exact: false, requiresLandlord: true,
    icon: svg('<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'),
  },
  {
    to: '/admin', labelKey: 'navigation.admin', captionKey: 'dock.admin', exact: false, requiresPlatform: true,
    icon: svg('<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>'),
  },
]

export interface NavigationAccess {
  isLandlord: boolean
  isPlatformAdmin: boolean
}

export const visibleNavItems = (items: readonly NavigationItem[], access: NavigationAccess): NavigationItem[] =>
  items.filter(item => (!item.requiresLandlord || access.isLandlord) && (!item.requiresPlatform || access.isPlatformAdmin))

export const isNavigationItemActive = (item: Pick<NavigationItem, 'to' | 'exact'>, currentPath: string): boolean =>
  item.exact ? currentPath === item.to : currentPath === item.to || currentPath.startsWith(`${item.to}/`)
