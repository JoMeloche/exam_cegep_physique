import { useState } from 'react'
import * as RS from '@radix-ui/react-select'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Option { value: string; label: React.ReactNode }

export function Select({ value, onChange, options, placeholder, className, footer, ...aria }: {
  value: string | undefined
  onChange: (v: string) => void
  options: Option[]
  placeholder?: string
  className?: string
  footer?: React.ReactNode
  id?: string
  'aria-label'?: string
  'aria-describedby'?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <RS.Root value={value || undefined} onValueChange={onChange} open={open} onOpenChange={setOpen}>
      <RS.Trigger {...aria} className={cn('flex h-9 w-full items-center justify-between gap-2 rounded-lg border bg-card px-3 text-left text-sm [&>span]:truncate focus:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[placeholder]:text-muted-foreground cursor-pointer', className)}>
        <RS.Value placeholder={placeholder} />
        <RS.Icon><ChevronDown className="h-4 w-4 opacity-60" /></RS.Icon>
      </RS.Trigger>
      <RS.Portal>
        <RS.Content position="popper" sideOffset={4} className="z-50 max-h-80 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-lg border bg-card shadow-lg">
          <RS.Viewport className="p-1">
            {options.map((o) => (
              <RS.Item key={o.value} value={o.value} className="relative flex cursor-pointer select-none items-center rounded-md py-1.5 pl-7 pr-3 text-sm outline-none data-[highlighted]:bg-muted">
                <RS.ItemIndicator className="absolute left-2"><Check className="h-3.5 w-3.5" /></RS.ItemIndicator>
                <RS.ItemText>{o.label}</RS.ItemText>
              </RS.Item>
            ))}
          </RS.Viewport>
          {footer && <div className="border-t p-1" onClick={() => setOpen(false)}>{footer}</div>}
        </RS.Content>
      </RS.Portal>
    </RS.Root>
  )
}
