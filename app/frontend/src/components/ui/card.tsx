import * as React from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border bg-card shadow-sm', className)} {...props} />
}
export function CardHeader({ className, title, description, action }: { className?: string; title: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className={cn('flex items-start justify-between gap-4 border-b px-5 py-4', className)}>
      <div>
        <h3 className="font-semibold">{title}</h3>
        {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  )
}
export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...props} />
}

export function Badge({ className, tone = 'default', ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: 'default' | 'primary' | 'success' | 'warning' | 'danger' }) {
  const tones = {
    default: 'bg-muted text-muted-foreground',
    primary: 'bg-accent text-primary',
    success: 'bg-success/10 text-success',
    warning: 'bg-warning/10 text-warning',
    danger: 'bg-danger/10 text-danger',
  }
  return <span className={cn('inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium', tones[tone], className)} {...props} />
}

export function Difficulty({ value }: { value: number }) {
  return (
    <span className="inline-flex gap-0.5" title={`Difficulté ${value}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={cn('h-1.5 w-3 rounded-full', i <= value ? 'bg-primary' : 'bg-border')} />
      ))}
    </span>
  )
}
