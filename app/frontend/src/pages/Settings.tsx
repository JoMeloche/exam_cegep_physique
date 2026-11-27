import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { CheckCircle2, KeyRound, Loader2, Plus, Save, Trash2, XCircle } from 'lucide-react'
import { PageHeader } from '@/App'
import { LatexEditor } from '@/components/LatexEditor'
import { CoursesEditor, LogoEditor, ProfessorsEditor, bankFoldersOf } from '@/components/ConfigEditors'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Field, Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { api, authApi, type Config } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { PasswordInput, passwordHint } from '@/pages/Auth'
import { fileBaseName, sessionCode } from '@/lib/utils'

const MONTHS = ['jan', 'fév', 'mar', 'avr', 'mai', 'juin', 'juil', 'août', 'sep', 'oct', 'nov', 'déc']

export default function Settings() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [health, setHealth] = useState<{ root: string; latex: string | null; version: string; desktop: boolean; latex_locked?: boolean } | null>(null)
  const [saved, setSaved] = useState('')
  const { state: auth } = useAuth()
  const [folders, setFolders] = useState<string[]>([])
  useEffect(() => {
    api.config().then((c) => { setCfg(c); setSaved(JSON.stringify(c)) }); api.health().then(setHealth)
    api.courses().then((cs) => setFolders(cs.filter((c) => c.topics.length).map((c) => c.code)))
  }, [])
  const dirty = !!cfg && saved !== '' && JSON.stringify(cfg) !== saved
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  if (!cfg) return null
  const set = (patch: Partial<Config>) => setCfg({ ...cfg, ...patch })
  const today = new Date()
  const firstCourse = Object.keys(cfg.courses)[0] ?? '203-NYA-05'
  const preview = fileBaseName(cfg.naming.file_pattern, { course: firstCourse, exam: 1, session: sessionCode(today, cfg.sessions), version: 1, date: today })

  async function save() {
    try { const c = await api.saveConfig({ ...cfg!, professors: cfg!.professors.filter((p) => p.trim()) }); setCfg(c); setSaved(JSON.stringify(c)); setHealth(await api.health()); toast.success('Paramètres enregistrés') } catch (e) { toast.error((e as Error).message) }
  }

  function monthOwner(m: number) { return Object.entries(cfg!.sessions).find(([, ms]) => ms.includes(m))?.[0] ?? '' }
  function setMonth(m: number, letter: string) {
    const s: Record<string, number[]> = {}
    for (const [k, ms] of Object.entries(cfg!.sessions)) s[k] = ms.filter((x) => x !== m)
    if (letter) s[letter] = [...(s[letter] ?? []), m].sort((a, b) => a - b)
    set({ sessions: s })
  }
  const letters = Object.keys(cfg.sessions)

  return (
    <div>
      <PageHeader title="Paramètres"
        subtitle={health?.desktop ? <span className="break-all font-mono text-xs">Bibliothèque : {health.root}</span> : 'Établissement, cours, noms des fichiers et page couverture.'}
        actions={<>
          {dirty && <span className="text-sm text-warning" role="status">Modifications non enregistrées</span>}
          <Button onClick={save} disabled={!dirty}><Save className="h-4 w-4" />Enregistrer</Button>
        </>} />
      <div className="grid grid-cols-1 gap-6 p-4 sm:p-6 lg:p-8 xl:grid-cols-2">
        <Card>
          <CardHeader title="Établissement et professeurs" />
          <CardBody className="space-y-4">
            <Field label="Établissement"><Input value={cfg.school} onChange={(e) => set({ school: e.target.value })} /></Field>
            <Field label="Logo (page couverture)"><LogoEditor value={cfg.logo} onChange={(logo) => set({ logo })} /></Field>
            <Field label="Professeurs"><ProfessorsEditor value={cfg.professors} onChange={(professors) => set({ professors })} /></Field>
            <Field label="Professeur par défaut">
              <Select value={cfg.default_professor} onChange={(v) => set({ default_professor: v })} options={cfg.professors.filter(Boolean).map((p) => ({ value: p, label: p }))} />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Noms des fichiers et sessions" />
          <CardBody className="space-y-4">
            <Field label="Modèle de nom de fichier" hint={<>Variables : {'{course} {exam} {session} {version} {date} {year}'}</>}>
              <Input className="font-mono text-sm" value={cfg.naming.file_pattern} onChange={(e) => set({ naming: { ...cfg.naming, file_pattern: e.target.value } })} />
            </Field>
            <div className="rounded-lg bg-muted px-3 py-2 font-mono text-xs">{preview}.pdf · {preview}{cfg.naming.solution_suffix}.pdf</div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Suffixe solution"><Input value={cfg.naming.solution_suffix} onChange={(e) => set({ naming: { ...cfg.naming, solution_suffix: e.target.value } })} /></Field>
              <Field label="Mot « Examen »"><Input value={cfg.naming.exam_label} onChange={(e) => set({ naming: { ...cfg.naming, exam_label: e.target.value } })} /></Field>
              <Field label="Mot « Version »"><Input value={cfg.naming.version_label} onChange={(e) => set({ naming: { ...cfg.naming, version_label: e.target.value } })} /></Field>
            </div>
            <Field label="Lettre de session par mois" hint="Ex. A = automne, H = hiver, E = été. Ajoutez une lettre si votre cégep en utilise d'autres.">
              <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
                {MONTHS.map((mn, i) => (
                  <div key={mn} className="flex flex-col items-center gap-1 rounded-lg border p-1.5">
                    <span className="text-[11px] text-muted-foreground">{mn}</span>
                    <select aria-label={`Lettre de session pour ${mn}`} className="w-full cursor-pointer rounded-md bg-muted text-center text-sm" value={monthOwner(i + 1)} onChange={(e) => setMonth(i + 1, e.target.value)}>
                      <option value="">–</option>
                      {letters.map((l) => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            </Field>
            <div className="flex flex-wrap items-center gap-2">
              {letters.map((l) => (
                <span key={l} className="flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs">{l}
                  <button className="cursor-pointer" title={`Retirer la lettre ${l}`} aria-label={`Retirer la lettre ${l}`} onClick={() => { const s = { ...cfg.sessions }; delete s[l]; set({ sessions: s }) }}><Trash2 className="h-3 w-3" /></button>
                </span>
              ))}
              <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); const v = (new FormData(e.currentTarget).get('l') as string || '').trim().toUpperCase(); if (v && !cfg.sessions[v]) set({ sessions: { ...cfg.sessions, [v]: [] } }); e.currentTarget.reset() }}>
                <Input name="l" aria-label="Nouvelle lettre de session" className="h-7 w-14 px-2 text-xs" placeholder="P" maxLength={3} />
                <Button size="sm" variant="ghost" type="submit"><Plus className="h-3.5 w-3.5" />Lettre</Button>
              </form>
            </div>
          </CardBody>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader title="Cours" description="Le code apparaît dans le nom des fichiers ; la discipline, le nom et le groupe sur la page couverture." />
          <CardBody><CoursesEditor value={cfg.courses} onChange={(courses) => set({ courses })} bankFolders={bankFoldersOf(cfg, folders)} /></CardBody>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader title="Page couverture" description="Texte LaTeX imprimé sous l'en-tête de chaque examen." />
          <CardBody className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 md:w-1/2">
              <Field label="Mot « Professeur »"><Input value={cfg.cover.professor_label} onChange={(e) => set({ cover: { ...cfg.cover, professor_label: e.target.value } })} /></Field>
              <Field label="Mot « NOM »"><Input value={cfg.cover.name_label} onChange={(e) => set({ cover: { ...cfg.cover, name_label: e.target.value } })} /></Field>
            </div>
            <Field label="Consignes"><LatexEditor value={cfg.cover.instructions} onChange={(v) => set({ cover: { ...cfg.cover, instructions: v } })} minHeight="180px" /></Field>
            <Field label="Note en gras (sous le résumé)"><LatexEditor value={cfg.cover.note} onChange={(v) => set({ cover: { ...cfg.cover, note: v } })} minHeight="60px" /></Field>
          </CardBody>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader title="LaTeX et génération" />
          <CardBody className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              <div className="flex items-center gap-2 rounded-lg bg-muted p-3 text-sm">
                {health?.latex ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-danger" />}
                <span className="truncate font-mono text-xs">{health?.latex ?? 'Aucune installation LaTeX trouvée'}</span>
              </div>
              {health?.latex_locked
                ? <p className="text-xs text-muted-foreground">Le serveur fournit LaTeX ; ce réglage n'est pas modifiable dans l'application web.</p>
                : <Field label="Chemin de LaTeX (optionnel)" hint="Laisser vide pour utiliser le LaTeX inclus ou celui du système.">
                    <Input value={cfg.latex.path} onChange={(e) => set({ latex: { ...cfg.latex, path: e.target.value } })} placeholder="C:\…\bin\windows" />
                  </Field>}
            </div>
            <div className="grid grid-cols-2 gap-3 self-start">
              <Field label="Marge de temps" hint="Temps visé = durée × (1 − marge)">
                <Input type="number" step="0.05" min="0" max="0.6" value={cfg.time_margin} onChange={(e) => set({ time_margin: Number(e.target.value) })} />
              </Field>
              <Field label="Versions par défaut"><Input type="number" min="1" max="8" value={cfg.default_versions} onChange={(e) => set({ default_versions: Number(e.target.value) })} /></Field>
            </div>
          </CardBody>
        </Card>
        {auth.user && <AccountCard />}
      </div>
    </div>
  )
}

function AccountCard() {
  const { state } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const hint = passwordHint(next)
  async function change(e: React.FormEvent) {
    e.preventDefault()
    if (next !== confirm) { toast.error('Les deux nouveaux mots de passe ne correspondent pas'); return }
    setBusy(true)
    try {
      await authApi.changePassword(current, next)
      setCurrent(''); setNext(''); setConfirm('')
      toast.success('Mot de passe changé. Vos autres sessions ont été fermées.')
    } catch (err) { toast.error((err as Error).message) } finally { setBusy(false) }
  }
  return (
    <Card className="xl:col-span-2">
      <CardHeader title="Mon compte" description={`${state.user!.name} · ${state.user!.email}${state.user!.role === 'admin' ? ' · administrateur' : ''}`} />
      <CardBody>
        <form onSubmit={change} className="grid gap-4 md:grid-cols-4 md:items-end">
          <Field label="Mot de passe actuel"><PasswordInput autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
          <Field label="Nouveau mot de passe" hint={hint.text}><PasswordInput autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></Field>
          <Field label="Confirmer" hint={confirm && confirm !== next ? 'Ne correspond pas' : ' '}><PasswordInput autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
          <Button type="submit" className="md:mb-5" disabled={busy || !current || !hint.ok || next !== confirm}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}Changer le mot de passe
          </Button>
        </form>
      </CardBody>
    </Card>
  )
}
