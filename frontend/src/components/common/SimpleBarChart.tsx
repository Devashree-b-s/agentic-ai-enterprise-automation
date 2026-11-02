import React from 'react'

export interface BarDataPoint {
  label: string
  value: number
  secondaryValue?: number
  formattedValue?: string
  color?: string
}

export interface SimpleBarChartProps {
  data: BarDataPoint[]
  height?: number
  valuePrefix?: string
  valueSuffix?: string
  emptyMessage?: string
  horizontal?: boolean
}

export const SimpleBarChart: React.FC<SimpleBarChartProps> = ({
  data,
  valuePrefix = '',
  valueSuffix = '',
  emptyMessage = 'No chart data available.',
  horizontal = false,
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-xs text-slate-500">
        {emptyMessage}
      </div>
    )
  }

  const maxValue = Math.max(...data.map((d) => d.value), 1)

  if (horizontal) {
    return (
      <div className="space-y-3">
        {data.map((item, idx) => {
          const pct = Math.min(100, Math.max(4, Math.round((item.value / maxValue) * 100)))
          return (
            <div key={idx} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="font-medium text-slate-300 truncate max-w-[60%]">
                  {item.label}
                </span>
                <span className="text-slate-400 font-mono">
                  {item.formattedValue || `${valuePrefix}${item.value.toLocaleString()}${valueSuffix}`}
                </span>
              </div>
              <div className="h-2.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    item.color || 'bg-indigo-500'
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Vertical Bar Chart
  return (
    <div className="flex flex-col h-56 pt-6">
      <div className="flex-1 flex items-end gap-2 sm:gap-3 px-2 border-b border-slate-800">
        {data.map((item, idx) => {
          const heightPct = Math.min(
            100,
            Math.max(6, Math.round((item.value / maxValue) * 100)),
          )
          return (
            <div
              key={idx}
              className="flex-1 flex flex-col items-center h-full justify-end group relative"
            >
              {/* Tooltip on hover */}
              <div className="absolute -top-8 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 text-slate-200 text-[10px] font-mono py-1 px-2 rounded-md shadow-lg pointer-events-none whitespace-nowrap z-20 border border-slate-700">
                {item.formattedValue || `${valuePrefix}${item.value.toLocaleString()}${valueSuffix}`}
              </div>

              {/* Bar column */}
              <div
                className={`w-full max-w-[36px] rounded-t-md transition-all duration-300 group-hover:brightness-125 ${
                  item.color || 'bg-indigo-600'
                }`}
                style={{ height: `${heightPct}%` }}
              />
            </div>
          )
        })}
      </div>

      {/* X-axis labels */}
      <div className="flex gap-2 sm:gap-3 px-2 pt-2">
        {data.map((item, idx) => (
          <div
            key={idx}
            className="flex-1 text-center text-[10px] text-slate-400 truncate font-mono"
            title={item.label}
          >
            {item.label}
          </div>
        ))}
      </div>
    </div>
  )
}

export default SimpleBarChart
