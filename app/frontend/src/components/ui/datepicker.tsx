import * as RP from '@radix-ui/react-popover'
import { DayPicker } from 'react-day-picker'
import { fr } from 'date-fns/locale'
import { format } from 'date-fns'
import { CalendarDays } from 'lucide-react'
import { useState } from 'react'
import 'react-day-picker/style.css'

export function DatePicker({ value, onChange, ...aria }: { value: Date; onChange: (d: Date) => void; id?: string; 'aria-describedby'?: string }) {
  const [open, setOpen] = useState(false)
  return (
    <RP.Root open={open} onOpenChange={setOpen}>
      <RP.Trigger {...aria} className="flex h-9 w-full items-center gap-2 rounded-lg border bg-card px-3 text-left text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer">
        <CalendarDays className="h-4 w-4 text-muted-foreground" />
        {format(value, 'EEEE d MMMM yyyy', { locale: fr })}
      </RP.Trigger>
      <RP.Portal>
        <RP.Content sideOffset={4} align="start" className="z-50 rounded-xl border bg-card p-3 shadow-lg">
          <DayPicker mode="single" locale={fr} selected={value} defaultMonth={value} weekStartsOn={0}
            onSelect={(d) => { if (d) { onChange(d); setOpen(false) } }} />
        </RP.Content>
      </RP.Portal>
    </RP.Root>
  )
}
