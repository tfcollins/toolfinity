'use client'

import { DepthEstimates } from './DepthEstimates'
import { ReferencePhotos } from './ReferencePhotos'

// the fork's single mount point on the trace page: reference photos before
// tracing, estimated pocket depths after.
export function ForkTracePanel({
  sessionId,
  step,
  polygonIds,
}: {
  sessionId: string
  step: 'corners' | 'trace' | 'edit'
  polygonIds: string[]
}) {
  if (step === 'edit') {
    if (polygonIds.length === 0) return null
    return <DepthEstimates sessionId={sessionId} polygonIds={polygonIds} />
  }
  return (
    <div className="glass rounded-[10px] px-3 py-3">
      <ReferencePhotos sessionId={sessionId} />
    </div>
  )
}
