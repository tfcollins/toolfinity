'use client'

import { useEffect, useState } from 'react'
import { getDepthEstimates, type DepthEstimate } from './api'

// shows the pocket depths the Claude/Codex tracer estimated from side views.
// they become each tool's default depth when it is placed in a bin.
export function DepthEstimates({ sessionId, polygonIds }: { sessionId: string; polygonIds: string[] }) {
  const [estimates, setEstimates] = useState<DepthEstimate[]>([])
  const key = polygonIds.join(',')

  useEffect(() => {
    getDepthEstimates(sessionId).then(setEstimates).catch(() => setEstimates([]))
  }, [sessionId, key])

  const current = estimates.filter(e => polygonIds.includes(e.polygon_id))
  if (current.length === 0) return null

  return (
    <div className="text-xs space-y-0.5">
      <span className="text-text-primary tracking-[0.3px]">Estimated pocket depth</span>
      {current.map(e => (
        <div key={e.polygon_id} className="flex justify-between text-text-muted px-2">
          <span>{e.label}</span>
          <span title={`thickness ${e.thickness_mm} mm, confidence ${Math.round(e.confidence * 100)}%`}>
            {e.depth_mm} mm
          </span>
        </div>
      ))}
    </div>
  )
}
