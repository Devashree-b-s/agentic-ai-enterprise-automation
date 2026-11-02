import React from 'react'

export interface CardProps {
  children: React.ReactNode
  title?: string
  subtitle?: string
  action?: React.ReactNode
  className?: string
  headerClassName?: string
  bodyClassName?: string
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  subtitle,
  action,
  className = '',
  headerClassName = '',
  bodyClassName = '',
}) => {
  return (
    <div
      className={`bg-slate-900/60 backdrop-blur-sm border border-slate-800 rounded-xl shadow-lg transition-all duration-200 ${className}`}
    >
      {(title || action) && (
        <div
          className={`px-6 py-4 border-b border-slate-800/80 flex items-center justify-between ${headerClassName}`}
        >
          <div>
            {title && (
              <h3 className="text-base font-semibold text-slate-100">{title}</h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className={`p-6 ${bodyClassName}`}>{children}</div>
    </div>
  )
}

export default Card
