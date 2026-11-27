import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Check, Globe, Loader2, Search, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { shareApi, type Person, type Share } from '@/lib/api'
import { cn } from '@/lib/utils'

/** Share one question (target = its id) or the whole bank (target = '*'). */
export function ShareDialog({ target, title, open, onOpenChange, onChanged }: {
  target: string; title: string; open: boolean; onOpenChange: (v: boolean) => void; onChanged?: () => void
}) {
  const [shares, setShares] = useState<Share[] | null>(null)
  const [people, setPeople] = useState<Person[]>([])
  const [audience, setAudience] = useState<'all' | 'users'>('users')
  const [chosen, setChosen] = useState<Set<number>>(new Set())
  const [filter, setFilter] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setShares(null); setFilter('')
    shareApi.list().then((r) => {
      setShares(r.shares); setPeople(r.users)
      const cur = r.shares.find((s) => s.target === target)
      setAudience(cur?.audience ?? 'users')
      setChosen(new Set(cur?.users.map((u) => u.id) ?? []))
    }).catch((e) => toast.error(e.message))
  }, [open, target])

  const current = shares?.find((s) => s.target === target)
  const whole = target !== '*' ? shares?.find((s) => s.target === '*') : undefined
  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase()
    return f ? people.filter((p) => (p.name + ' ' + p.email).toLowerCase().includes(f)) : people
  }, [people, filter])

  async function save() {
    setBusy(true)
    try {
      await shareApi.set(target, audience, [...chosen])
      toast.success(audience === 'all' ? 'Partagé avec tous les utilisateurs' : `Partagé avec ${chosen.size} personne${chosen.size > 1 ? 's' : ''}`)
      onChanged?.(); onOpenChange(false)
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(false) }
  }
  async function stop() {
    if (!current) return
    setBusy(true)
    try { await shareApi.remove(current.id); toast.success('Partage arrêté'); onChanged?.(); onOpenChange(false) }
    catch (e) { toast.error((e as Error).message) } finally { setBusy(false) }
  }
  const toggle = (id: number) => { const s = new Set(chosen); if (s.has(id)) s.delete(id); else s.add(id); setChosen(s) }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={target === '*' ? 'Partager toute ma banque' : `Partager « ${title} »`}
      description="Les personnes choisies voient la question en lecture seule, peuvent la copier dans leur banque et l'utiliser dans leurs examens.">
      {!shares ? <div className="py-10 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" /></div> : (
        <div className="space-y-4">
          {whole && (
            <p className="rounded-lg bg-accent px-3 py-2 text-xs text-primary">
              Toute votre banque est déjà partagée {whole.audience === 'all' ? 'avec tous les utilisateurs' : `avec ${whole.users.map((u) => u.name).join(', ')}`}.
              Ce partage s'ajoute pour cette question.
            </p>
          )}
          <div className="grid grid-cols-2 gap-2">
            {([['users', Users, 'Certaines personnes'], ['all', Globe, 'Tous les utilisateurs']] as const).map(([v, Icon, label]) => (
              <button key={v} type="button" onClick={() => setAudience(v)}
                className={cn('flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm cursor-pointer transition-colors', audience === v ? 'border-primary bg-accent text-primary' : 'hover:bg-muted')}>
                <Icon className="h-4 w-4" />{label}
              </button>
            ))}
          </div>
          {audience === 'users' && (
            <div className="rounded-lg border">
              <div className="relative border-b p-2">
                <Search className="absolute left-4 top-4 h-4 w-4 text-muted-foreground" />
                <Input className="pl-8" placeholder="Rechercher un collègue…" value={filter} onChange={(e) => setFilter(e.target.value)} />
              </div>
              <div className="max-h-60 overflow-auto p-1">
                {!people.length && <p className="p-4 text-center text-sm text-muted-foreground">Aucun autre utilisateur approuvé pour l'instant.</p>}
                {shown.map((p) => (
                  <button key={p.id} type="button" onClick={() => toggle(p.id)}
                    className="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted cursor-pointer">
                    <span className={cn('grid h-4 w-4 place-items-center rounded border', chosen.has(p.id) && 'border-primary bg-primary text-primary-foreground')}>
                      {chosen.has(p.id) && <Check className="h-3 w-3" />}
                    </span>
                    <span className="flex-1 truncate">{p.name}</span>
                    <span className="truncate text-xs text-muted-foreground">{p.email}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center justify-between gap-2 pt-1">
            {current ? <Button variant="ghost" className="text-danger" onClick={stop} disabled={busy}>Arrêter le partage</Button> : <span />}
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => onOpenChange(false)}>Annuler</Button>
              <Button onClick={save} disabled={busy || (audience === 'users' && !chosen.size)}>
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}{current ? 'Mettre à jour' : 'Partager'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Dialog>
  )
}
