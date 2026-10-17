import { describe, expect, it } from 'vitest'
import { emptyListingForm, toListingInput, type ListingForm } from './listingForm'

const filled = (changes: Partial<ListingForm>): ListingForm => ({ ...emptyListingForm(7), title: ' 两居 ', area: 60, priceMonth: 3000, ...changes })

describe('toListingInput', () => {
  it('normalizes blanks to null and trims text', () => {
    const result = toListingInput(filled({ floor: '', totalFloors: '', availableFrom: '' }))
    expect(result).toMatchObject({ input: { estateId: 7, title: '两居', floor: null, totalFloors: null, availableFrom: null } })
  })

  it('requires the price that matches the rental type', () => {
    expect(toListingInput(filled({ rentType: 'short' }))).toEqual({ errorKey: 'console.errors.priceNight' })
    expect(toListingInput(filled({ priceMonth: '' }))).toEqual({ errorKey: 'console.errors.priceMonth' })
    expect('input' in toListingInput(filled({ rentType: 'short', priceNight: 300 }))).toBe(true)
  })

  it('rejects missing estate, title, area and inverted floors', () => {
    expect(toListingInput({ ...filled({}), estateId: 0 })).toEqual({ errorKey: 'console.errors.estate' })
    expect(toListingInput(filled({ title: '  ' }))).toEqual({ errorKey: 'console.errors.title' })
    expect(toListingInput(filled({ area: '' }))).toEqual({ errorKey: 'console.errors.area' })
    expect(toListingInput(filled({ floor: 9, totalFloors: 3 }))).toEqual({ errorKey: 'console.errors.floor' })
  })
})
