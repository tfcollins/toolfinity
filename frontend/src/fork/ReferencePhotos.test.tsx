// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ReferencePhotos } from './ReferencePhotos'
import { DepthEstimates } from './DepthEstimates'
import { depthOverrideFor } from './api'

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
}

const sidePhoto = { id: 'r1', kind: 'side', note: '', url: '/storage/default/processed/s1_refs/r1.jpg' }

describe('ReferencePhotos', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('lists existing photos and uploads new ones with the chosen kind', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        const body = init.body as FormData
        expect(body.get('kind')).toBe('detail')
        return jsonResponse({ photos: [sidePhoto, { ...sidePhoto, id: 'r2', kind: 'detail' }], kinds: [], max_photos: 6 })
      }
      return jsonResponse({ photos: [sidePhoto], kinds: ['top', 'side', 'detail'], max_photos: 6 })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ReferencePhotos sessionId="s1" />)
    expect(await screen.findByAltText('Side view')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Reference photo kind'), { target: { value: 'detail' } })
    const file = new File(['x'], 'close.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByTestId('reference-photo-input'), { target: { files: [file] } })

    expect(await screen.findByAltText('Close-up')).toBeTruthy()
    expect(fetchMock.mock.calls[1][0]).toContain('/api/fork/sessions/s1/reference-photos')
  })

  it('hides the add button once the cap is reached', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse({ photos: [sidePhoto], kinds: [], max_photos: 1 })))
    render(<ReferencePhotos sessionId="s1" />)
    await screen.findByAltText('Side view')
    expect(screen.queryByText('Add photo')).toBeNull()
  })
})

describe('DepthEstimates', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows estimates for the current polygons only', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse([
      { polygon_id: 'p1', label: 'hex key', thickness_mm: 6, depth_mm: 7, confidence: 0.9 },
      { polygon_id: 'old', label: 'saw', thickness_mm: 2, depth_mm: 3, confidence: 0.9 },
    ])))
    render(<DepthEstimates sessionId="s1" polygonIds={['p1']} />)
    expect(await screen.findByText('7 mm')).toBeTruthy()
    expect(screen.queryByText('saw')).toBeNull()
  })
})

describe('depthOverrideFor', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns the estimate, or undefined on null and errors', async () => {
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse({ depth_mm: 21 })))
    expect(await depthOverrideFor('t1')).toBe(21)
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse(null)))
    expect(await depthOverrideFor('t1')).toBeUndefined()
    vi.stubGlobal('fetch', vi.fn(() => jsonResponse({ detail: 'nope' }, 500)))
    await waitFor(async () => expect(await depthOverrideFor('t1')).toBeUndefined())
  })
})
