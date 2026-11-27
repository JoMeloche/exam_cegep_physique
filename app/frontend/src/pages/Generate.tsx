import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import {
  AlertTriangle, ArrowLeftRight, Clock, Download, FileCheck2, FolderOpen, Loader2, Lock, Minus, Plus,
  RefreshCw, Sparkles, Trash2, Unlock, UserPlus, Wand2,
} from 'lucide-react'
import { PageHeader } from '@/App'
import { Button } from '@/components/ui/button'
import { Badge, Card, CardBody, CardHeader, Difficulty } from '@/components/ui/card'
import { DatePicker } from '@/components/ui/datepicker'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Segmented, Switch } from '@/components/ui/switch'
import {
  api, type Config, type Course, type ExamDef, type ExamRequest, type ExportResult, type Placed, type Plan,
  type QuestionSummary,
} from '@/lib/api'
import { cn, durationText, isoDate, sessionCode } from '@/lib/utils'

const DURATIONS = [60, 75, 90, 105, 120, 135, 150, 165, 180, 210, 240]

function nextExamDate() {
  const d = new Date(); d.setDate(d.getDate() + 7); return d
}

export default function Generate() {
  const [config, setConfig] = useState<Config | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [professor, setProfessor] = useState('')
  const [course, setCourse] = useState('')
  const [examNumber, setExamNumber] = useState(1)
  const [date, setDate] = useState<Date>(nextExamDate)
  const [duration, setDuration] = useState(120)
  const [nVersions, setNVersions] = useState(3)
  const [mode, setMode] = useState<'same' | 'different'>('same')
  const [shuffle, setShuffle] = useState(true)
  const [examDef, setExamDef] = useState<ExamDef | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [lastReq, setLastReq] = useState<ExamRequest | null>(null)
  const [locked, setLocked] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState<'plan' | 'export' | null>(null)
  const [result, setResult] = useState<ExportResult | null>(null)
  const [activeVersion, setActiveVersion] = useState(1)
  const [swapSlot, setSwapSlot] = useState<{ key: string; version: number; current: string } | null>(null)
  const [addProfOpen, setAddProfOpen] = useState(false)
  const [desktop, setDesktop] = useState(false)

  useEffect(() => {
    Promise.all([api.config(), api.courses(), api.health()]).then(([cfg, cs, h]) => {
      setConfig(cfg); setCourses(cs); setDesktop(h.desktop)
      setProfessor(cfg.default_professor || cfg.professors[0] || '')
      setNVersions(cfg.default_versions || 3)
      const withQ = cs.find((c) => c.topics.length) ?? cs[0]
      if (withQ) setCourse(withQ.code)
    }).catch((e) => toast.error(e.message))
  }, [])

  useEffect(() => {
    if (!course) return
    api.examDef(course, examNumber).then((d) => { setExamDef(d); setDuration(d.duration_min || 120) })
    setPlan(null); setResult(null); setLocked(new Set())
  }, [course, examNumber])

  const courseObj = courses.find((c) => c.code === course)
  const topicLabel = (t: string) => courseObj?.topics.find((x) => x.name === t)?.label ?? t.replace(/_/g, ' ')
  const session = sessionCode(date)
  const fileName = `${course}_Examen_${examNumber}_${session}_v1.pdf`

  function buildRequest(extra: Partial<ExamRequest> = {}): ExamRequest {
    return {
      course, exam_number: examNumber, date: isoDate(date), professor, duration_min: duration, n_versions: nVersions,
      mode, shuffle_conceptual: shuffle, shuffle_choices: shuffle, exam_def: examDef ? { ...examDef, duration_min: duration } : undefined,
      ...extra,
    }
  }

  function lockKey(version: number, slot: string) { return mode === 'different' ? `${version}:${slot}` : slot }

  function currentLocks(p: Plan | null, onlyLocked: boolean): Record<string, string> {
    const out: Record<string, string> = {}
    if (!p) return out
    for (const v of p.versions) {
      if (mode === 'same' && v.number > 1) break
      for (const q of v.placed) {
        const k = lockKey(v.number, q.slot)
        if (!onlyLocked || locked.has(k)) out[k] = q.question_id
      }
    }
    return out
  }

  async function runPlan(r: ExamRequest) {
    setBusy('plan'); setResult(null)
    try {
      const p = await api.plan(r)
      setPlan(p); setLastReq({ ...r, seed: p.seed }); setActiveVersion(1)
      p.warnings.forEach((w) => toast.warning(w))
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(null) }
  }

  const generate = () => runPlan(buildRequest({ locks: currentLocks(plan, true) }))

  async function doExport() {
    if (!lastReq) return
    setBusy('export')
    try {
      const r = await api.exportExam(lastReq)
      setResult(r)
      toast.success(`${r.files.length} PDF créés`)
      r.warnings.forEach((w) => toast.warning(w))
    } catch (e) { toast.error((e as Error).message, { duration: 12000 }) } finally { setBusy(null) }
  }

  async function applySwap(newId: string) {
    if (!swapSlot || !lastReq) return
    const locks = currentLocks(plan, false)
    const k = lockKey(swapSlot.version, swapSlot.key)
    locks[k] = newId
    setLocked((s) => new Set(s).add(k))
    setSwapSlot(null)
    await runPlan({ ...lastReq, locks })
  }

  async function saveStructure() {
    if (!examDef) return
    try { await api.saveExamDef({ ...examDef, duration_min: duration }); toast.success(`Structure de l'examen ${examNumber} enregistrée`) }
    catch (e) { toast.error((e as Error).message) }
  }

  async function addProfessor(name: string) {
    if (!config || !name.trim()) return
    const professors = Array.from(new Set([...config.professors, name.trim()]))
    const cfg = await api.saveConfig({ professors })
    setConfig(cfg); setProfessor(name.trim()); setAddProfOpen(false)
  }

  const version = plan?.versions.find((v) => v.number === activeVersion) ?? plan?.versions[0]
  const stats = useMemo(() => {
    if (!version) return null
    const time = version.placed.reduce((a, p) => a + (p.time_min ?? 0), 0)
    const pts = version.placed.reduce((a, p) => a + p.points, 0)
    const diff = version.placed.reduce((a, p) => a + (p.difficulty ?? 0), 0) / Math.max(1, version.placed.length)
    return { time, pts, diff }
  }, [version])

  const examOptions = useMemo(() => {
    const nums = new Set([...(courseObj?.exams ?? []), 1, 2, 3, examNumber])
    return [...nums].sort((a, b) => a - b).map((n) => ({ value: String(n), label: `Examen ${n}` }))
  }, [courseObj, examNumber])

  return (
    <div>
      <PageHeader title="Générer un examen" subtitle="Choisissez les paramètres, vérifiez la sélection, puis exportez les PDF."
        actions={plan && (
          <Button size="lg" onClick={doExport} disabled={!!busy}>
            {busy === 'export' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Exporter les PDF
          </Button>
        )} />

      <div className="grid gap-6 p-8 xl:grid-cols-[400px_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Paramètres" description="Ce qui apparaît sur la page couverture" />
            <CardBody className="space-y-4">
              <Field label="Professeur">
                <Select value={professor} onChange={setProfessor}
                  options={(config?.professors ?? []).map((p) => ({ value: p, label: p }))}
                  footer={<button className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-primary hover:bg-muted cursor-pointer" onClick={() => setAddProfOpen(true)}><UserPlus className="h-4 w-4" />Ajouter un professeur</button>} />
              </Field>
              <Field label="Cours">
                <Select value={course} onChange={setCourse}
                  options={courses.map((c) => ({ value: c.code, label: <span>{c.code} <span className="text-muted-foreground">· {c.full_title ?? c.title}</span></span> }))} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Examen">
                  <Select value={String(examNumber)} onChange={(v) => setExamNumber(Number(v))} options={examOptions} />
                </Field>
                <Field label="Durée">
                  <Select value={String(duration)} onChange={(v) => setDuration(Number(v))}
                    options={DURATIONS.map((d) => ({ value: String(d), label: durationText(d) }))} />
                </Field>
              </div>
              <Field label="Date de l'examen" hint={<>Session <b>{session}</b> déduite de la date</>}>
                <DatePicker value={date} onChange={setDate} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Versions">
                  <div className="flex h-9 items-center justify-between rounded-lg border bg-card px-1">
                    <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setNVersions(Math.max(1, nVersions - 1))}><Minus className="h-3.5 w-3.5" /></Button>
                    <span className="font-semibold tabular-nums">{nVersions}</span>
                    <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setNVersions(Math.min(8, nVersions + 1))}><Plus className="h-3.5 w-3.5" /></Button>
                  </div>
                </Field>
                <Field label="Mélanger">
                  <div className="flex h-9 items-center gap-2 text-sm"><Switch checked={shuffle} onChange={setShuffle} /> conceptuelles</div>
                </Field>
              </div>
              <Field label="Versions différentes par">
                <Segmented value={mode} onChange={setMode} options={[
                  { value: 'same', label: 'Valeurs seulement' },
                  { value: 'different', label: 'Questions différentes' },
                ]} />
              </Field>
              <div className="rounded-lg bg-muted px-3 py-2 font-mono text-xs text-muted-foreground">{fileName}</div>
            </CardBody>
          </Card>

          {examDef && courseObj && (
            <StructureEditor def={examDef} onChange={setExamDef} topics={courseObj.topics.map((t) => ({ value: t.name, label: t.label }))}
              onSave={saveStructure} />
          )}

          <Button size="lg" className="w-full" onClick={generate} disabled={!!busy || !course}>
            {busy === 'plan' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {plan ? 'Régénérer' : "Générer l'examen"}
          </Button>
        </div>

        <div className="space-y-6">
          {!plan && (
            <Card className="grid min-h-[420px] place-items-center border-dashed">
              <div className="max-w-sm text-center">
                <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-accent text-primary"><Wand2 className="h-7 w-7" /></div>
                <h3 className="text-lg font-semibold">Prêt à générer</h3>
                <p className="mt-2 text-sm text-muted-foreground">L'application choisit des questions qui respectent la structure et la durée, tire de nouvelles valeurs pour chaque version et calcule les solutions.</p>
              </div>
            </Card>
          )}

          {plan && version && stats && (
            <Card>
              <CardHeader
                title={<span className="flex items-center gap-3">Aperçu <Badge tone="primary">{plan.session}</Badge></span>}
                description={<span className="font-mono text-xs">{version.basename}.pdf</span>}
                action={<Button variant="outline" size="sm" onClick={generate} disabled={!!busy}><RefreshCw className="h-3.5 w-3.5" />Nouvelles valeurs</Button>} />
              <CardBody className="space-y-5">
                {plan.versions.length > 1 && (
                  <div className="flex flex-wrap gap-2">
                    {plan.versions.map((v) => (
                      <button key={v.number} onClick={() => setActiveVersion(v.number)}
                        className={cn('rounded-lg border px-3 py-1.5 text-sm font-medium cursor-pointer', v.number === version.number ? 'border-primary bg-accent text-primary' : 'hover:bg-muted')}>
                        Version {v.number}
                      </button>
                    ))}
                  </div>
                )}
                <TimeBar time={stats.time} duration={duration} margin={config?.time_margin ?? 0.2} points={stats.pts} diff={stats.diff} />
                {plan.exam_def.sections.map((sec, si) => {
                  const items = version.placed.filter((p) => p.section === si)
                  if (!items.length) return null
                  return (
                    <div key={si}>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{sec.title}</h4>
                      <div className="divide-y rounded-xl border">
                        {items.map((p, i) => (
                          <QuestionRow key={p.slot + i} p={p} index={i + 1} topicLabel={topicLabel(p.topic ?? '')}
                            locked={locked.has(lockKey(version.number, p.slot))}
                            onLock={() => setLocked((s) => { const n = new Set(s); const k = lockKey(version.number, p.slot); if (n.has(k)) n.delete(k); else n.add(k); return n })}
                            onSwap={() => setSwapSlot({ key: p.slot, version: version.number, current: p.question_id })} />
                        ))}
                      </div>
                    </div>
                  )
                })}
                {plan.warnings.length > 0 && (
                  <div className="space-y-1 rounded-lg bg-warning/10 p-3 text-sm text-warning">
                    {plan.warnings.map((w) => <div key={w} className="flex gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{w}</div>)}
                  </div>
                )}
              </CardBody>
            </Card>
          )}

          {result && (
            <Card>
              <CardHeader title={<span className="flex items-center gap-2"><FileCheck2 className="h-5 w-5 text-success" />PDF prêts</span>}
                description={<span className="font-mono text-xs">{result.folder}</span>}
                action={desktop && <Button variant="outline" size="sm" onClick={() => api.open(result.folder)}><FolderOpen className="h-3.5 w-3.5" />Ouvrir le dossier</Button>} />
              <CardBody className="grid gap-2 sm:grid-cols-2">
                {result.files.map((f) => (
                  <a key={f.name} href={f.url} target="_blank" rel="noreferrer"
                    onClick={(e) => { if (desktop) { e.preventDefault(); api.open(f.path) } }}
                    className={cn('flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm hover:bg-muted', f.name.includes('_solution') && 'bg-accent/40')}>
                    <FileText2 solution={f.name.includes('_solution')} />
                    <span className="truncate font-mono text-xs">{f.name}</span>
                  </a>
                ))}
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      <SwapDialog open={!!swapSlot} onClose={() => setSwapSlot(null)} req={lastReq} slot={swapSlot}
        exclude={version?.placed.map((p) => p.question_id) ?? []} onPick={applySwap} />
      <AddProfessorDialog open={addProfOpen} onClose={() => setAddProfOpen(false)} onAdd={addProfessor} />
    </div>
  )
}

function FileText2({ solution }: { solution: boolean }) {
  return <span className={cn('grid h-8 w-8 shrink-0 place-items-center rounded-md text-[10px] font-bold', solution ? 'bg-primary text-primary-foreground' : 'bg-danger/10 text-danger')}>{solution ? 'SOL' : 'PDF'}</span>
}

function TimeBar({ time, duration, margin, points, diff }: { time: number; duration: number; margin: number; points: number; diff: number }) {
  const target = duration * (1 - margin)
  const pct = Math.min(100, (time / duration) * 100)
  const over = time > target
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <div className="sm:col-span-2">
        <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />Temps estimé {Math.round(time)} min</span>
          <span>cible ≤ {Math.round(target)} min sur {durationText(duration)}</span>
        </div>
        <div className="relative h-2.5 overflow-hidden rounded-full bg-muted">
          <div className={cn('h-full rounded-full transition-all', over ? 'bg-warning' : 'bg-primary')} style={{ width: `${pct}%` }} />
          <div className="absolute top-0 h-full w-0.5 bg-foreground/40" style={{ left: `${(1 - margin) * 100}%` }} />
        </div>
      </div>
      <div className="flex items-center justify-around rounded-lg bg-muted px-2 text-center">
        <div><div className="text-lg font-semibold tabular-nums">{Math.round(points)}</div><div className="text-[10px] uppercase text-muted-foreground">points</div></div>
        <div><div className="text-lg font-semibold tabular-nums">{diff.toFixed(1)}</div><div className="text-[10px] uppercase text-muted-foreground">difficulté</div></div>
      </div>
    </div>
  )
}

function fmtValues(v: Record<string, unknown>) {
  return Object.entries(v).map(([k, x]) => `${k} = ${typeof x === 'number' ? String(x).replace('.', ',') : String(x).slice(0, 18)}`).join('  ·  ')
}

function QuestionRow({ p, index, topicLabel, locked, onLock, onSwap }: { p: Placed; index: number; topicLabel: string; locked: boolean; onLock: () => void; onSwap: () => void }) {
  return (
    <div className="group flex items-center gap-4 px-4 py-3">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted text-sm font-semibold tabular-nums">{index}</div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate font-medium">{p.title}</span>
          <Badge>{topicLabel}</Badge>
          {p.answer && <Badge tone="success">Rép. {p.answer}</Badge>}
        </div>
        <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">{fmtValues(p.values) || 'aucune variable'}</div>
      </div>
      <div className="hidden items-center gap-4 text-xs text-muted-foreground md:flex">
        <span className="tabular-nums">{p.time_min} min</span>
        <Difficulty value={p.difficulty ?? 0} />
        <span className="w-12 text-right font-medium tabular-nums text-foreground">{Math.round(p.points * 100) / 100} pts</span>
      </div>
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" title="Remplacer cette question" onClick={onSwap}><ArrowLeftRight className="h-4 w-4" /></Button>
        <Button size="icon" variant={locked ? 'subtle' : 'ghost'} title={locked ? 'Déverrouiller' : 'Verrouiller (garder lors de la régénération)'} onClick={onLock}>
          {locked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4 opacity-50" />}
        </Button>
      </div>
    </div>
  )
}

function SwapDialog({ open, onClose, req, slot, exclude, onPick }: { open: boolean; onClose: () => void; req: ExamRequest | null; slot: { key: string; current: string } | null; exclude: string[]; onPick: (id: string) => void }) {
  const [items, setItems] = useState<QuestionSummary[] | null>(null)
  useEffect(() => {
    if (!open || !req || !slot) return
    setItems(null)
    api.alternatives({ ...req, slot: slot.key, exclude }).then(setItems).catch((e) => toast.error(e.message))
  }, [open, slot?.key]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()} title="Remplacer la question" description="Choisissez une autre question du même thème." className="max-w-2xl">
      {!items ? <div className="py-10 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div> :
        items.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">Aucune autre question disponible pour ce thème.</p> :
          <div className="max-h-[60vh] divide-y overflow-auto rounded-xl border">
            {items.map((q) => (
              <button key={q.id} onClick={() => onPick(q.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted cursor-pointer">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{q.title}</div>
                  <div className="text-xs text-muted-foreground">{q.topic.replace(/_/g, ' ')} · {q.time_min} min · utilisée {q.times_used}×</div>
                </div>
                <Difficulty value={q.difficulty} />
              </button>
            ))}
          </div>}
    </Dialog>
  )
}

function AddProfessorDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (n: string) => void }) {
  const [name, setName] = useState('')
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()} title="Ajouter un professeur">
      <form onSubmit={(e) => { e.preventDefault(); onAdd(name); setName('') }} className="space-y-4">
        <Input autoFocus placeholder="Prénom Nom" value={name} onChange={(e) => setName(e.target.value)} />
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Annuler</Button><Button type="submit">Ajouter</Button></div>
      </form>
    </Dialog>
  )
}

function StructureEditor({ def, onChange, topics, onSave }: { def: ExamDef; onChange: (d: ExamDef) => void; topics: { value: string; label: string }[]; onSave: () => void }) {
  const update = (fn: (d: ExamDef) => void) => { const d = structuredClone(def); fn(d); onChange(d) }
  const total = def.sections.reduce((a, s) => a + (s.type === 'conceptuel' && s.points ? s.points : s.slots.reduce((b, sl) => b + (sl.points ?? 0) * sl.count, 0)), 0)
  return (
    <Card>
      <CardHeader title="Structure" description={<>Thèmes et nombre de questions · <b>{total} points</b></>}
        action={<Button variant="ghost" size="sm" onClick={onSave}>Enregistrer</Button>} />
      <CardBody className="space-y-5">
        {def.sections.map((sec, si) => (
          <div key={si} className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{sec.title}</span>
              {sec.type === 'conceptuel' && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">total
                  <Input className="h-7 w-14 px-2 text-xs" type="number" value={sec.points ?? ''} onChange={(e) => update((d) => { d.sections[si].points = Number(e.target.value) })} /> pts
                </span>
              )}
            </div>
            {sec.slots.map((sl, li) => {
              const t = sl.topics ?? (sl.topic ? [sl.topic] : [])
              return (
                <div key={li} className="flex items-center gap-2">
                  <Select className="h-8 flex-1 text-xs" value={t[0]} onChange={(v) => update((d) => { d.sections[si].slots[li] = { ...sl, topic: v, topics: undefined } })}
                    options={topics} placeholder="Thème" />
                  {t.length > 1 && <Badge title={t.join(', ')}>+{t.length - 1}</Badge>}
                  <Input className="h-8 w-12 px-2 text-center text-xs" type="number" min={1} value={sl.count} title="Nombre de questions"
                    onChange={(e) => update((d) => { d.sections[si].slots[li].count = Math.max(1, Number(e.target.value)) })} />
                  {sec.type !== 'conceptuel' && (
                    <Input className="h-8 w-14 px-2 text-center text-xs" type="number" value={sl.points ?? ''} title="Points"
                      onChange={(e) => update((d) => { d.sections[si].slots[li].points = Number(e.target.value) })} />
                  )}
                  <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => update((d) => { d.sections[si].slots.splice(li, 1) })}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              )
            })}
            <Button variant="ghost" size="sm" className="text-primary" onClick={() => update((d) => { d.sections[si].slots.push({ topic: topics[0]?.value, count: 1, points: sec.type === 'conceptuel' ? undefined : 20 }) })}>
              <Plus className="h-3.5 w-3.5" />Ajouter un thème
            </Button>
          </div>
        ))}
      </CardBody>
    </Card>
  )
}
