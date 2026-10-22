export const RENT_TYPES = ['long', 'short', 'shared'] as const
export type RentType = typeof RENT_TYPES[number]

export const SORT_KEYS = ['latest', 'price_asc', 'price_desc', 'distance'] as const
export type SortKey = typeof SORT_KEYS[number]

/** 与后端 routes_listings.summary 对应 */
export interface ListingSummary {
  id: number
  title: string
  rentType: RentType
  /** 卡片展示价：短租按晚，其余按月 */
  price: number
  priceMonth: number | null
  priceNight: number | null
  bedrooms: number
  halls: number
  baths: number
  area: number
  floor: number | null
  tags: string[]
  coverUrl: string | null
  recommended: boolean
  availableFrom: string | null
  publishedAt: string
  estateId: number
  community: string
  city: string
  district: string
  lat: number
  lng: number
  distanceKm?: number
  isToday?: boolean
}

export interface ListingDetail extends ListingSummary {
  description: string
  building: string
  totalFloors: number | null
  orientation: string
  depositMonths: number
  minMonths: number
  minNights: number
  address: string
  landlordName: string
  images: string[]
  unavailable: { start: string; end: string }[]
}

export interface ListingPage {
  items: ListingSummary[]
  total: number
  page: number
  pageSize: number
}

export interface HomeFeed {
  today: ListingSummary[]
  recommended: ListingSummary[]
  todayCount: number
}

export interface FacetValue {
  value: string
  count: number
}

export interface CityFacet extends FacetValue {
  /** 该城市房源坐标的平均值，地图切换城市时作为中心 */
  lat: number
  lng: number
}

export interface Facets {
  cities?: CityFacet[]
  districts: FacetValue[]
  tags: FacetValue[]
}

export const LEASE_MONTH_OPTIONS = [1, 3, 6, 12] as const
