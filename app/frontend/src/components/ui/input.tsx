import * as React from 'react'
import { cn } from '@/lib/utils'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-9 w-full rounded-lg border bg-card px-3 py-1 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-[70px] w-full rounded-lg border bg-card px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('text-xs font-medium uppercase tracking-wide text-muted-foreground', className)} {...props} />
}

/** A labelled form row. The label is tied to the control (and the hint described by it) when the
 *  child is a single element, so screen readers announce "Professeur, liste" instead of nothing. */
export function Field({ label, children, className, hint }: { label: string; children: React.ReactNode; className?: string; hint?: React.ReactNode }) {
  const id = React.useId()
  const hintId = `${id}-hint`
  const only = React.Children.count(children) === 1 && React.isValidElement(children) ? children as React.ReactElement<Record<string, unknown>> : null
  const control = only && !only.props.id
    ? React.cloneElement(only, { id, ...(hint && !only.props['aria-describedby'] ? { 'aria-describedby': hintId } : {}) })
    : children
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <Label htmlFor={only ? (only.props.id as string | undefined) ?? id : undefined}>{label}</Label>
      {control}
      {hint && <p id={hintId} className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
