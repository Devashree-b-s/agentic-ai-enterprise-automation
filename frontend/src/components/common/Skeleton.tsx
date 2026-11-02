import React from 'react'

export interface SkeletonProps {
  className?: string
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = 'h-4 w-full' }) => {
  return (
    <div
      className={`bg-slate-800/80 animate-pulse rounded-md ${className}`}
      aria-hidden="true"
    />
  )
}

export const SkeletonCard: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div
      className={`p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm space-y-3 ${className}`}
      aria-hidden="true"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-28 bg-slate-800" />
        <Skeleton className="h-7 w-7 rounded-lg bg-slate-800" />
      </div>
      <Skeleton className="h-8 w-24 bg-slate-800" />
      <Skeleton className="h-3 w-36 bg-slate-800/60" />
    </div>
  )
}

export const SkeletonTable: React.FC<{ rows?: number; columns?: number }> = ({
  rows = 5,
  columns = 5,
}) => {
  return (
    <div className="w-full space-y-3 p-4" aria-hidden="true">
      {/* Table header skeleton */}
      <div className="flex items-center gap-4 py-2 border-b border-slate-800">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={`h-${i}`} className="h-4 flex-1 bg-slate-800" />
        ))}
      </div>
      {/* Table rows skeleton */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={`r-${r}`} className="flex items-center gap-4 py-3 border-b border-slate-800/40">
          {Array.from({ length: columns }).map((_, c) => (
            <Skeleton
              key={`c-${r}-${c}`}
              className={`h-4 flex-1 ${c === 0 ? 'bg-slate-800' : 'bg-slate-800/60'}`}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export default Skeleton
