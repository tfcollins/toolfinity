// toolfinity fork endpoints (/api/fork). kept apart from lib/api.ts so
// upstream changes there merge cleanly.

const API_URL = process.env.NEXT_PUBLIC_API_URL === ''
  ? ''
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')

export type ReferenceKind = 'top' | 'side' | 'detail'

export interface ReferencePhoto {
  id: string
  kind: ReferenceKind
  note: string
  url: string
}

export interface ReferencePhotoList {
  photos: ReferencePhoto[]
  kinds: ReferenceKind[]
  max_photos: number
}

export interface DepthEstimate {
  polygon_id: string
  label: string
  thickness_mm: number
  depth_mm: number
  confidence: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { credentials: 'include', ...init })
  if (!res.ok) {
    let detail = 'request failed'
    try {
      detail = (await res.json()).detail || detail
    } catch {
      // non-json error body
    }
    throw new Error(detail)
  }
  return res.json()
}

const refsPath = (sessionId: string) => `/api/fork/sessions/${sessionId}/reference-photos`

export function listReferencePhotos(sessionId: string): Promise<ReferencePhotoList> {
  return request(refsPath(sessionId))
}

export function addReferencePhoto(
  sessionId: string,
  file: File,
  kind: ReferenceKind,
  note = '',
): Promise<ReferencePhotoList> {
  const body = new FormData()
  body.append('image', file)
  body.append('kind', kind)
  body.append('note', note)
  return request(refsPath(sessionId), { method: 'POST', body })
}

export function deleteReferencePhoto(sessionId: string, refId: string): Promise<ReferencePhotoList> {
  return request(`${refsPath(sessionId)}/${refId}`, { method: 'DELETE' })
}

export function getDepthEstimates(sessionId: string): Promise<DepthEstimate[]> {
  return request(`/api/fork/sessions/${sessionId}/depth-estimates`)
}

// placement default for a library tool: the estimated pocket depth, or
// undefined so the bin's cutout depth applies. never throws.
export async function depthOverrideFor(toolId: string): Promise<number | undefined> {
  try {
    const estimate = await request<DepthEstimate | null>(`/api/fork/tools/${toolId}/depth-estimate`)
    return estimate?.depth_mm ?? undefined
  } catch {
    return undefined
  }
}
