import * as RD from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Dialog({ open, onOpenChange, title, description, children, className }: {
  open: boolean; onOpenChange: (v: boolean) => void; title: React.ReactNode; description?: React.ReactNode; children: React.ReactNode; className?: string
}) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <RD.Content className={cn('fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl border bg-card p-6 shadow-2xl', className)}>
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <RD.Title className="text-lg font-semibold">{title}</RD.Title>
              {description && <RD.Description className="mt-1 text-sm text-muted-foreground">{description}</RD.Description>}
            </div>
            <RD.Close className="rounded-md p-1 hover:bg-muted cursor-pointer"><X className="h-4 w-4" /></RD.Close>
          </div>
          {children}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  )
}
