'use client'

import { DepthEstimates } from './DepthEstimates'
import { ReferencePhotos } from './ReferencePhotos'

export const HAL_ASSIST = 'hal-assist'

// the fork's single mount point on the trace page: reference photos before
// tracing, estimated pocket depths after. reference photos only feed the
// hal-assist tracer, so the upload panel hides when it isn't configured.
export function ForkTracePanel({
  sessionId,
  step,
  polygonIds,
  tracerIds,
}: {
  sessionId: string
  step: 'corners' | 'trace' | 'edit'
  polygonIds: string[]
  tracerIds: string[]
}) {
  if (!tracerIds.includes(HAL_ASSIST)) return null
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
