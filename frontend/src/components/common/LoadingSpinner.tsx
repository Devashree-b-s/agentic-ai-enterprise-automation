import React from 'react'

export interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

const sizeMap = {
  sm: 'w-4 h-4 border-2',
  md: 'w-6 h-6 border-2',
  lg: 'w-10 h-10 border-3',
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  className = '',
  label,
}) => {
  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      <div
        className={`${sizeMap[size]} border-indigo-500/20 border-t-indigo-400 rounded-full animate-spin`}
        role="status"
        aria-label="Loading"
      />
      {label && <span className="text-xs text-slate-400">{label}</span>}
    </div>
  )
}

export default LoadingSpinner
