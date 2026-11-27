import * as RS from '@radix-ui/react-switch'
import { cn } from '@/lib/utils'

export function Switch({ checked, onChange, className, ...rest }: { checked: boolean; onChange: (v: boolean) => void; className?: string; 'aria-label'?: string; id?: string }) {
  return (
    <RS.Root checked={checked} onCheckedChange={onChange} {...rest}
      className={cn('relative h-5 w-9 shrink-0 cursor-pointer rounded-full bg-border transition-colors data-[state=checked]:bg-primary', className)}>
      <RS.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px]" />
    </RS.Root>
  )
}

export function Segmented<T extends string>({ value, onChange, options, className, ...aria }: { value: T; onChange: (v: T) => void; options: { value: T; label: React.ReactNode }[]; className?: string; id?: string; 'aria-label'?: string }) {
  return (
    <div role="group" {...aria} className={cn('inline-flex max-w-full flex-wrap rounded-lg border bg-muted p-0.5', className)}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}
          className={cn('rounded-md px-3 py-1.5 text-sm font-medium transition-all cursor-pointer', value === o.value ? 'bg-card shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
          {o.label}
        </button>
      ))}
    </div>
  )
}
