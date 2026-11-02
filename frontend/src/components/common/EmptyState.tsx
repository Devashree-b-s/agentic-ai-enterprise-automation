import React from 'react'
import { FolderOpen } from 'lucide-react'

export interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div
      className={`p-12 flex flex-col items-center justify-center text-center rounded-xl border border-dashed border-slate-800 bg-slate-900/30 ${className}`}
    >
      <div className="w-12 h-12 rounded-2xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center text-slate-400 mb-3.5 shadow-inner">
        {icon || <FolderOpen className="w-6 h-6 text-slate-500" />}
      </div>
      <h3 className="text-sm font-semibold text-slate-200 m-0">{title}</h3>
      {description && (
        <p className="text-xs text-slate-400 max-w-sm mt-1 mb-0 leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export default EmptyState
