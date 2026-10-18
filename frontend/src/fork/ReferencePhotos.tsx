'use client'

import { useEffect, useRef, useState } from 'react'
import { ImagePlus, Loader2, X } from 'lucide-react'
import { getImageUrl } from '@/lib/api'
import {
  addReferencePhoto,
  deleteReferencePhoto,
  listReferencePhotos,
  type ReferenceKind,
  type ReferencePhoto,
} from './api'

const KIND_LABELS: Record<ReferenceKind, string> = {
  side: 'Side view',
  top: 'Another angle',
  detail: 'Close-up',
}

// extra photos the Claude/Codex tracer looks at alongside the paper photo.
// side views let it estimate how deep each pocket should be.
export function ReferencePhotos({ sessionId }: { sessionId: string }) {
  const [photos, setPhotos] = useState<ReferencePhoto[]>([])
  const [maxPhotos, setMaxPhotos] = useState(6)
  const [kind, setKind] = useState<ReferenceKind>('side')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listReferencePhotos(sessionId)
      .then(r => { setPhotos(r.photos); setMaxPhotos(r.max_photos) })
      .catch(() => {})
  }, [sessionId])

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return
    setBusy(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        const r = await addReferencePhoto(sessionId, file, kind)
        setPhotos(r.photos)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'upload failed')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  async function handleDelete(id: string) {
    try {
      setPhotos((await deleteReferencePhoto(sessionId, id)).photos)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'delete failed')
    }
  }

  const full = photos.length >= maxPhotos

  return (
    <div className="space-y-1.5">
      <span className="text-xs text-text-primary tracking-[0.3px]">Reference photos</span>
      <p className="text-xs text-text-muted">
        Optional. Used by the Claude/Codex tracer to separate and name tools; side views also estimate pocket depth.
      </p>
      {photos.length > 0 && (
        <div className="grid grid-cols-3 gap-1.5">
          {photos.map(p => (
            <div key={p.id} className="relative group rounded-md overflow-hidden border border-border">
              <img src={getImageUrl(p.url)} alt={KIND_LABELS[p.kind]} className="w-full h-16 object-cover" />
              <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-[10px] text-white px-1">
                {KIND_LABELS[p.kind]}
              </span>
              <button
                onClick={() => handleDelete(p.id)}
                aria-label={`Remove ${KIND_LABELS[p.kind]}`}
                className="absolute top-0.5 right-0.5 p-0.5 rounded bg-black/60 text-white cursor-pointer"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      {!full && (
        <div className="flex gap-1.5">
          <select
            value={kind}
            onChange={e => setKind(e.target.value as ReferenceKind)}
            aria-label="Reference photo kind"
            className="px-2 py-1.5 rounded-[10px] glass text-xs text-text-primary cursor-pointer"
          >
            {(Object.keys(KIND_LABELS) as ReferenceKind[]).map(k => (
              <option key={k} value={k}>{KIND_LABELS[k]}</option>
            ))}
          </select>
          <button
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            className="flex-1 px-3 py-1.5 rounded-[10px] glass text-xs font-medium text-text-primary flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <ImagePlus className="w-3 h-3" />}
            Add photo
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            data-testid="reference-photo-input"
            onChange={e => handleFiles(e.target.files)}
          />
        </div>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
