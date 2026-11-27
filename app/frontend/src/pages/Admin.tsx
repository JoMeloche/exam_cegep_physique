import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Ban, Check, Copy, KeyRound, Loader2, RotateCcw, Shield, ShieldOff, Trash2, UserCheck, Users, X } from 'lucide-react'
import { PageHeader } from '@/App'
import { useConfirm } from '@/components/ui/confirm'
import { Button } from '@/components/ui/button'
import { Badge, Card } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Field, Textarea } from '@/components/ui/input'
import { Segmented } from '@/components/ui/switch'
import { authApi, type AdminUser, type UserStatus } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const TABS: { value: UserStatus; label: string }[] = [
  { value: 'pending', label: 'En attente' },
  { value: 'approved', label: 'Approuvés' },
  { value: 'rejected', label: 'Refusés' },
  { value: 'disabled', label: 'Désactivés' },
]

const fmt = (iso: string | null) => iso ? new Date(iso).toLocaleString('fr-CA', { dateStyle: 'medium', timeStyle: 'short' }) : '—'

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('') || '?'
}

export default function Admin() {
  const { state, refresh } = useAuth()
  const [tab, setTab] = useState<UserStatus>('pending')
  const [confirmDialog, ask] = useConfirm()
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [counts, setCounts] = useState<Record<UserStatus, number> | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState<AdminUser | null>(null)
  const [note, setNote] = useState('')
  const [temp, setTemp] = useState<{ user: AdminUser; password: string } | null>(null)

  const load = useCallback(() => {
    authApi.users(tab).then((r) => { setUsers(r.users); setCounts(r.counts) }).catch((e) => toast.error(e.message))
  }, [tab])
  useEffect(() => { setUsers(null); load() }, [load])

  async function act(u: AdminUser, action: Parameters<typeof authApi.act>[1], n?: string) {
    setBusy(u.id)
    try {
      const r = await authApi.act(u.id, action, n)
      if (r.temporary_password) setTemp({ user: r.user, password: r.temporary_password })
      const done: Record<string, string> = { approve: 'approuvé', reject: 'refusé', disable: 'désactivé', enable: 'réactivé', 'make-admin': 'nommé administrateur', 'make-user': 'n\'est plus administrateur', 'reset-password': 'a un mot de passe temporaire' }
      toast.success(`${u.name} ${done[action] ?? ''}`)
      load(); refresh()
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(null) }
  }

  async function remove(u: AdminUser) {
    if (!(await ask({ title: `Supprimer le compte de ${u.name} ?`, description: 'La personne ne pourra plus se connecter. Ses questions restent sur le serveur.', confirmLabel: 'Supprimer le compte' }))) return
    try { await authApi.remove(u.id); toast.success('Compte supprimé'); load(); refresh() } catch (e) { toast.error((e as Error).message) }
  }

  const me = state.user?.id
  return (
    <div>
      <PageHeader title="Utilisateurs" subtitle="Approuvez les demandes de compte et gérez les accès."
        actions={<Segmented value={tab} onChange={setTab} options={TABS.map((t) => ({ value: t.value, label: <span className="flex items-center gap-1.5">{t.label}{counts && counts[t.value] > 0 && <span className="rounded-full bg-primary/10 px-1.5 text-xs text-primary">{counts[t.value]}</span>}</span> }))} />} />
      <div className="space-y-3 p-4 sm:p-6 lg:p-8">
        {!users && <div className="py-20 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" /></div>}
        {users && !users.length && (
          <div className="py-20 text-center text-muted-foreground">
            <Users className="mx-auto mb-3 h-8 w-8 opacity-40" />
            {tab === 'pending' ? 'Aucune demande en attente.' : 'Aucun compte dans cette catégorie.'}
          </div>
        )}
        {users?.map((u) => (
          <Card key={u.id} className="flex flex-col gap-4 p-5 md:flex-row md:items-start">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent text-sm font-semibold text-primary">{initials(u.name)}</div>
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{u.name}</span>
                <span className="text-sm text-muted-foreground">{u.email}</span>
                {u.role === 'admin' && <Badge tone="primary"><Shield className="h-3 w-3" />Admin</Badge>}
                {u.id === me && <Badge>Vous</Badge>}
              </div>
              {u.reason && (
                <blockquote className="rounded-lg border-l-2 border-primary/40 bg-muted/60 px-3 py-2 text-sm whitespace-pre-wrap">{u.reason}</blockquote>
              )}
              {u.note && <p className="text-xs text-muted-foreground">Note : {u.note}</p>}
              <p className="text-xs text-muted-foreground">
                Demande : {fmt(u.created_at)}
                {u.decided_at && <> · Décision : {fmt(u.decided_at)}{u.decided_by && ` par ${u.decided_by}`}</>}
                {u.status === 'approved' && <> · Dernière connexion : {fmt(u.last_login)}</>}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2 md:max-w-[340px] md:justify-end">
              {busy === u.id && <Loader2 className="h-4 w-4 animate-spin self-center text-muted-foreground" />}
              {u.status === 'pending' && (<>
                <Button size="sm" onClick={() => act(u, 'approve')} disabled={busy === u.id}><Check className="h-3.5 w-3.5" />Approuver</Button>
                <Button size="sm" variant="outline" onClick={() => { setRejecting(u); setNote('') }} disabled={busy === u.id}><X className="h-3.5 w-3.5" />Refuser</Button>
              </>)}
              {u.status === 'approved' && u.id !== me && (<>
                {u.role === 'admin'
                  ? <Button size="sm" variant="ghost" onClick={() => act(u, 'make-user')}><ShieldOff className="h-3.5 w-3.5" />Retirer admin</Button>
                  : <Button size="sm" variant="ghost" onClick={() => act(u, 'make-admin')}><Shield className="h-3.5 w-3.5" />Nommer admin</Button>}
                <Button size="sm" variant="ghost" onClick={() => act(u, 'reset-password')}><KeyRound className="h-3.5 w-3.5" />Mot de passe</Button>
                <Button size="sm" variant="outline" onClick={() => act(u, 'disable')}><Ban className="h-3.5 w-3.5" />Désactiver</Button>
              </>)}
              {(u.status === 'disabled' || u.status === 'rejected') && (
                <Button size="sm" variant="outline" onClick={() => act(u, u.status === 'rejected' ? 'approve' : 'enable')}>
                  {u.status === 'rejected' ? <UserCheck className="h-3.5 w-3.5" /> : <RotateCcw className="h-3.5 w-3.5" />}{u.status === 'rejected' ? 'Approuver' : 'Réactiver'}
                </Button>
              )}
              {u.id !== me && u.status !== 'approved' && (
                <Button size="sm" variant="ghost" className="text-danger" onClick={() => remove(u)}><Trash2 className="h-3.5 w-3.5" /></Button>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!rejecting} onOpenChange={(v) => !v && setRejecting(null)} title={`Refuser la demande de ${rejecting?.name ?? ''}`}
        description="La personne verra ce motif si elle tente de se connecter.">
        <Field label="Motif (optionnel)"><Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></Field>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRejecting(null)}>Annuler</Button>
          <Button variant="danger" onClick={() => { const u = rejecting!; setRejecting(null); act(u, 'reject', note.trim()) }}>Refuser</Button>
        </div>
      </Dialog>

      <Dialog open={!!temp} onOpenChange={(v) => !v && setTemp(null)} title="Mot de passe temporaire"
        description={`Transmettez-le à ${temp?.user.name ?? ''} de façon privée. Il ne sera plus affiché. Ses sessions ouvertes ont été fermées.`}>
        <div className="flex items-center gap-2 rounded-lg border bg-muted px-3 py-2 font-mono text-sm">
          <span className="flex-1 select-all">{temp?.password}</span>
          <Button size="sm" variant="ghost" aria-label="Copier le mot de passe" title="Copier" onClick={() => { navigator.clipboard?.writeText(temp!.password); toast.success('Copié') }}><Copy className="h-3.5 w-3.5" /></Button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">La personne pourra le changer dans Paramètres → Mon compte.</p>
      </Dialog>
      {confirmDialog}
    </div>
  )
}
