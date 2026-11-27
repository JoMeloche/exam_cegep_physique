import { useCallback, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'

interface Ask { title: string; description?: string; confirmLabel?: string; danger?: boolean }

/** In-app confirmation (the browser's confirm() is blocked or ugly in the desktop window).
 *  const [confirmDialog, ask] = useConfirm(); …; if (!(await ask({ title: 'Supprimer ?' }))) return */
export function useConfirm(): [React.ReactNode, (a: Ask) => Promise<boolean>] {
  const [ask, setAsk] = useState<Ask | null>(null)
  const resolver = useRef<((v: boolean) => void) | null>(null)
  const done = (v: boolean) => { resolver.current?.(v); resolver.current = null; setAsk(null) }
  const open = useCallback((a: Ask) => new Promise<boolean>((resolve) => { resolver.current = resolve; setAsk(a) }), [])
  const el = (
    <Dialog open={!!ask} onOpenChange={(v) => !v && done(false)} title={ask?.title ?? ''} description={ask?.description}>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => done(false)}>Annuler</Button>
        <Button autoFocus variant={ask?.danger === false ? 'default' : 'danger'} onClick={() => done(true)}>{ask?.confirmLabel ?? 'Supprimer'}</Button>
      </div>
    </Dialog>
  )
  return [el, open]
}
