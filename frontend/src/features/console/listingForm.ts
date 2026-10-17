import type { ConsoleListingDetail, ListingInput } from './types'

/** 编辑表单的数值字段允许暂时为空字符串（输入框被清空），提交前统一规整。 */
export type ListingForm = { [K in keyof ListingInput]: ListingInput[K] extends number | null ? number | null | '' : ListingInput[K] }

export function emptyListingForm(estateId: number | null): ListingForm {
  return {
    estateId: estateId ?? 0, rentType: 'long', title: '', description: '', building: '', unitNo: '',
    bedrooms: 1, halls: 1, baths: 1, area: '', floor: '', totalFloors: '', orientation: '',
    priceMonth: '', priceNight: '', depositMonths: 1, minMonths: 1, minNights: 1, tags: [], availableFrom: '',
  } as ListingForm
}

export function formFromDetail(d: ConsoleListingDetail): ListingForm {
  return {
    estateId: d.estateId, rentType: d.rentType, title: d.title, description: d.description, building: d.building,
    unitNo: d.unitNo, bedrooms: d.bedrooms, halls: d.halls, baths: d.baths, area: d.area, floor: d.floor ?? '',
    totalFloors: d.totalFloors ?? '', orientation: d.orientation, priceMonth: d.priceMonth ?? '', priceNight: d.priceNight ?? '',
    depositMonths: d.depositMonths, minMonths: d.minMonths, minNights: d.minNights, tags: [...d.tags],
    availableFrom: d.availableFrom ?? '',
  } as ListingForm
}

const num = (v: number | null | ''): number | null => (v === '' || v === null || Number.isNaN(Number(v)) ? null : Number(v))

/** 返回提交体；缺少必填项时返回错误文案的 i18n key。 */
export function toListingInput(form: ListingForm): { input: ListingInput } | { errorKey: string } {
  const isShort = form.rentType === 'short'
  const input: ListingInput = {
    ...form,
    estateId: num(form.estateId) ?? 0,
    title: form.title.trim(),
    description: form.description.trim(),
    bedrooms: num(form.bedrooms) ?? 0,
    halls: num(form.halls) ?? 0,
    baths: num(form.baths) ?? 0,
    area: num(form.area) ?? 0,
    floor: num(form.floor),
    totalFloors: num(form.totalFloors),
    priceMonth: num(form.priceMonth),
    priceNight: num(form.priceNight),
    depositMonths: num(form.depositMonths) ?? 0,
    minMonths: num(form.minMonths) ?? 1,
    minNights: num(form.minNights) ?? 1,
    availableFrom: form.availableFrom || null,
  }
  if (!input.estateId) return { errorKey: 'console.errors.estate' }
  if (!input.title) return { errorKey: 'console.errors.title' }
  if (input.area <= 0) return { errorKey: 'console.errors.area' }
  if (isShort ? !input.priceNight : !input.priceMonth) return { errorKey: isShort ? 'console.errors.priceNight' : 'console.errors.priceMonth' }
  if (input.floor !== null && input.totalFloors !== null && input.floor > input.totalFloors) return { errorKey: 'console.errors.floor' }
  return { input }
}
