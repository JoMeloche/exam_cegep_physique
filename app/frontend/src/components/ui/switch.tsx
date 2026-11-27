import * as RS from '@radix-ui/react-switch'
import { cn } from '@/lib/utils'

export function Switch({ checked, onChange, className }: { checked: boolean; onChange: (v: boolean) => void; className?: string }) {
  return (
    <RS.Root checked={checked} onCheckedChange={onChange}
      className={cn('relative h-5 w-9 shrink-0 cursor-pointer rounded-full bg-border transition-colors data-[state=checked]:bg-primary', className)}>
      <RS.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px]" />
    </RS.Root>
  )
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode }[] }) {
  return (
    <div className="inline-flex rounded-lg border bg-muted p-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange(o.value)}
          className={cn('rounded-md px-3 py-1.5 text-sm font-medium transition-all cursor-pointer', value === o.value ? 'bg-card shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
          {o.label}
        </button>
      ))}
    </div>
  )
}
