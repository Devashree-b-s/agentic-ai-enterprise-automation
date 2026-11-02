import React from 'react'
import { Link } from 'react-router-dom'
import { Compass, ArrowLeft } from 'lucide-react'
import Button from '../components/common/Button'
import Badge from '../components/common/Badge'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-6 shadow-xl shadow-indigo-500/10">
        <Compass className="w-8 h-8" />
      </div>

      <Badge variant="neutral" size="md" className="mb-3">
        HTTP 404 Not Found
      </Badge>

      <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight m-0">
        Page Not Found
      </h1>
      <p className="text-sm text-slate-400 max-w-md mt-2 m-0 leading-relaxed">
        The requested path does not exist in the Enterprise Decision Support System.
      </p>

      <div className="mt-8">
        <Link to="/">
          <Button variant="primary" size="md" icon={<ArrowLeft className="w-4 h-4" />}>
            Back to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  )
}

export default NotFoundPage
