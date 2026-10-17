import type { RentType } from '@/features/listings/types'

export type ListingStatus = 'draft' | 'published' | 'offline'
export type InquiryStatus = 'new' | 'contacted' | 'closed'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface Estate {
  id: number
  name: string
  city: string
  district: string
  address: string
  lat: number
  lng: number
  listingCount?: number
}

export type EstateInput = Omit<Estate, 'id' | 'listingCount'>

export interface ConsoleListing {
  id: number
  landlordId: number
  landlordName?: string
  estateId: number
  estateName: string
  district: string
  building: string
  unitNo: string
  rentType: RentType
  title: string
  description: string
  bedrooms: number
  halls: number
  baths: number
  area: number
  floor: number | null
  totalFloors: number | null
  orientation: string
  priceMonth: number | null
  priceNight: number | null
  depositMonths: number
  minMonths: number
  minNights: number
  tags: string[]
  coverUrl: string | null
  status: ListingStatus
  recommended: boolean
  availableFrom: string | null
  publishedAt: string | null
  updatedAt: string
  newInquiries?: number
}

export interface ListingImage {
  id: number
  url: string
  sort: number
}

export interface Block {
  id: number
  startDate: string
  endDate: string
  kind: 'lease' | 'booking' | 'block'
  note: string
}

export interface ConsoleListingDetail extends ConsoleListing {
  images: ListingImage[]
  unavailable: Block[]
}

export interface ListingInput {
  estateId: number
  rentType: RentType
  title: string
  description: string
  building: string
  unitNo: string
  bedrooms: number
  halls: number
  baths: number
  area: number
  floor: number | null
  totalFloors: number | null
  orientation: string
  priceMonth: number | null
  priceNight: number | null
  depositMonths: number
  minMonths: number
  minNights: number
  tags: string[]
  availableFrom: string | null
}

export interface Inquiry {
  id: number
  listingId: number
  listingTitle: string
  name: string
  phone: string
  message: string
  moveIn: string | null
  moveOut: string | null
  status: InquiryStatus
  note: string
  createdAt: string
  handledAt: string | null
}

export interface Member {
  userId: number
  username: string
  email: string | null
  phone: string | null
  role: 'owner' | 'staff'
  createdAt: string
}

export interface Overview {
  listings: Record<ListingStatus, number>
  estates: number
  newInquiries: number
  weekInquiries: number
}

export interface AdminLandlord {
  id: number
  name: string
  contactName: string | null
  contactPhone: string | null
  status: 'active' | 'disabled'
  createdAt: string
  listingCount: number
  publishedCount: number
  memberCount: number
  owners: string | null
}
