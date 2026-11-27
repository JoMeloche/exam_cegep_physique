import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { AlertTriangle, CheckCircle2, FlaskConical, ImagePlus, Loader2, Plus, Save, Trash2, Wand2, X } from 'lucide-react'
import { PageHeader } from '@/App'
import { LatexEditor } from '@/components/LatexEditor'
import { Button } from '@/components/ui/button'
import { Badge, Card, CardBody, CardHeader } from '@/components/ui/card'
import { Field, Input, Textarea } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Segmented } from '@/components/ui/switch'
import { api, type Course, type PartSpec, type QType, type QuestionMeta, type TestResult, type VariableSpec } from '@/lib/api'
import { cn } from '@/lib/utils'

type Mode = QuestionMeta['solution']['mode']
interface VarRow extends VariableSpec { name: string; valuesText?: string }
interface PartRow extends PartSpec { key: string; kind: 'equation' | 'expr' }

const VAR_TYPES = [
  { value: 'integer', label: 'Entier' }, { value: 'decimal', label: 'Décimal' }, { value: 'sigfig', label: 'Chiffres sig.' },
  { value: 'choice', label: 'Liste de nombres' }, { value: 'text', label: 'Liste LaTeX' },
]
const VREF = /\\(?:v|vsi)\{([^{}]+)\}/g

function detect(...texts: string[]) {
  const out: string[] = []
  for (const t of texts) for (const m of t.matchAll(VREF)) if (!out.includes(m[1])) out.push(m[1])
  return out
}

const SI: Record<string, [number, string]> = { g: [0.001, 'kg'], cm: [0.01, 'm'], mm: [0.001, 'm'], km: [1000, 'm'], ms: [0.001, 's'], 'km/h': [1 / 3.6, 'm/s'], kHz: [1000, 'Hz'], 'g/m': [0.001, 'kg/m'], nm: [1e-9, 'm'] }

function guessUnit(text: string, name: string) {
  const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const m = text.match(new RegExp(`\\\\qty\\{\\\\v\\{${esc}\\}\\}\\{([^}]*)\\}`)) ?? text.match(new RegExp(`\\\\v\\{${esc}\\}\\s*\\\\text\\{\\s*([^}]*)\\}`))
  return m ? m[1].trim() : ''
}

function emptyVar(name: string, text = ''): VarRow {
  const unit = guessUnit(text, name)
  const si = SI[unit]
  return { name, type: 'decimal', min: 1, max: 10, step: 0.1, unit, label: '', ...(si ? { si: si[0], si_unit: si[1] } : {}) }
}

export default function QuestionEditor() {
  const nav = useNavigate()
  const loc = useLocation()
  const editId = loc.pathname.startsWith('/question/edit/') ? decodeURIComponent(loc.pathname.slice('/question/edit/'.length)) : null

  const [courses, setCourses] = useState<Course[]>([])
  const [course, setCourse] = useState('')
  const [topic, setTopic] = useState('')
  const [newTopic, setNewTopic] = useState('')
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [qtype, setQtype] = useState<QType>('developpement')
  const [points, setPoints] = useState(20)
  const [time, setTime] = useState(15)
  const [difficulty, setDifficulty] = useState(3)
  const [body, setBody] = useState('')
  const [vars, setVars] = useState<VarRow[]>([])
  const [constraints, setConstraints] = useState<string[]>([])
  const [mode, setMode] = useState<Mode>('auto')
  const [parts, setParts] = useState<PartRow[]>([{ key: 'a', kind: 'equation', find: '', equation: '', unit: '', label: '' }])
  const [solution, setSolution] = useState('')
  const [choices, setChoices] = useState<string[]>([])
  const [answer, setAnswer] = useState('')
  const [pinLast, setPinLast] = useState(0)
  const [explanation, setExplanation] = useState('')
  const [figures, setFigures] = useState<string[]>([])
  const [extra, setExtra] = useState<Record<string, unknown>>({})
  const [test, setTest] = useState<TestResult | null>(null)
  const [busy, setBusy] = useState<'test' | 'save' | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.courses().then((cs) => {
      setCourses(cs)
      if (!editId) { const c = cs.find((x) => x.topics.length) ?? cs[0]; if (c) { setCourse(c.code); setTopic(c.topics[0]?.name ?? '') } }
    })
  }, [editId])

  useEffect(() => {
    if (!editId) return
    api.question(editId).then((q) => {
      const m = q.meta
      setCourse(q.course); setTopic(q.topic); setName(q.name); setTitle(m.title); setQtype(m.type)
      setPoints(m.points); setTime(m.time_min); setDifficulty(m.difficulty); setBody(q.body); setSolution(q.solution_tex)
      setVars(Object.entries(m.variables ?? {}).map(([n, v]) => ({ name: n, ...v, valuesText: (v.values ?? []).join(v.type === 'text' ? ' ;; ' : ', ') })))
      setConstraints(m.constraints ?? []); setMode(m.solution.mode)
      const ps = Object.entries(m.solution.parts ?? {}).map(([k, p]) => ({ key: k, kind: (p.expr ? 'expr' : 'equation') as PartRow['kind'], ...p }))
      setParts(ps.length ? ps : [{ key: 'a', kind: 'equation' }])
      setChoices(m.choices ?? []); setAnswer(m.answer ?? ''); setPinLast(Number(m.pin_last ?? 0)); setExplanation(m.explanation ?? '')
      setFigures(m.figures ?? [])
      const known = new Set(['title', 'type', 'points', 'time_min', 'difficulty', 'figures', 'tags', 'variables', 'constraints', 'solution', 'answer', 'explanation', 'choices', 'pin_last', 'history'])
      setExtra(Object.fromEntries(Object.entries(m).filter(([k]) => !known.has(k))))
    }).catch((e) => toast.error(e.message))
  }, [editId])

  // keep one row per \v{...} found in the LaTeX
  const detected = useMemo(() => detect(body, solution, explanation), [body, solution, explanation])
  useEffect(() => {
    setVars((cur) => {
      const have = new Set(cur.map((v) => v.name))
      const add = detected.filter((n) => !have.has(n)).map((n) => emptyVar(n, body + '\n' + solution))
      return add.length ? [...cur, ...add] : cur
    })
  }, [detected])

  const courseObj = courses.find((c) => c.code === course)
  const isConcept = qtype === 'conceptuel'

  function setVar(i: number, patch: Partial<VarRow>) { setVars((vs) => vs.map((v, j) => (j === i ? { ...v, ...patch } : v))) }
  function setPart(i: number, patch: Partial<PartRow>) { setParts((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p))) }

  function payload() {
    const variables: Record<string, VariableSpec> = {}
    for (const v of vars) {
      const { name: n, valuesText, ...spec } = v
      const s: VariableSpec = { type: spec.type, unit: spec.unit || undefined, label: spec.label || undefined, symbol: spec.symbol || undefined }
      if (spec.type === 'choice' || spec.type === 'text') {
        const raw = (valuesText ?? '').split(spec.type === 'text' ? ';;' : /[,;]/).map((x) => x.trim()).filter(Boolean)
        s.values = spec.type === 'choice' ? raw.map((x) => Number(x.replace(',', '.'))) : raw
      } else {
        s.min = Number(spec.min); s.max = Number(spec.max)
        if (spec.type === 'sigfig') s.sigfigs = Number(spec.sigfigs ?? 3)
        else if (spec.step) s.step = Number(spec.step)
      }
      if (spec.si && Number(spec.si) !== 1) { s.si = Number(spec.si); s.si_unit = spec.si_unit || undefined }
      variables[n] = JSON.parse(JSON.stringify(s))
    }
    const partsOut: Record<string, PartSpec> = {}
    for (const p of parts) {
      if (p.kind === 'expr' ? !p.expr : !(p.find && p.equation)) continue
      const o: PartSpec = p.kind === 'expr' ? { expr: p.expr } : { find: p.find, equation: p.equation }
      if (p.unit) o.unit = p.unit
      if (p.label) o.label = p.label
      if (p.symbol) o.symbol = p.symbol
      partsOut[p.key] = o
    }
    const meta: QuestionMeta = {
      ...extra, title: title || name, type: qtype, points, time_min: time, difficulty, figures,
      variables, constraints: constraints.filter((c) => c.trim()),
      solution: { mode, ...(Object.keys(partsOut).length ? { parts: partsOut } : {}) },
    }
    if (isConcept) {
      if (answer) meta.answer = answer
      if (explanation) meta.explanation = explanation
      if (choices.length) { meta.choices = choices; if (pinLast) meta.pin_last = pinLast }
    }
    return { course, topic: topic === '__new' ? newTopic : topic, name, meta, body, solution_tex: mode === 'manual' ? solution : '', original_id: editId }
  }

  async function runTest() {
    setBusy('test'); setTest(null)
    try { setTest(await api.testQuestion({ ...payload(), draws: 5 })) } catch (e) { toast.error((e as Error).message) } finally { setBusy(null) }
  }

  async function save() {
    setBusy('save')
    try {
      const q = await api.saveQuestion({ ...payload(), reviewed: true })
      toast.success('Question enregistrée')
      if (q.id !== editId) nav(`/question/edit/${q.id}`, { replace: true })
    } catch (e) { toast.error((e as Error).message, { duration: 10000 }) } finally { setBusy(null) }
  }

  async function remove() {
    if (!editId || !confirm('Supprimer cette question ?')) return
    await api.deleteQuestion(editId); toast.success('Question supprimée'); nav('/library')
  }

  async function uploadFigure(f: File) {
    try {
      const { name: fn } = await api.uploadFigure(f)
      setFigures((fs) => Array.from(new Set([...fs, fn])))
      setBody((b) => b + `\n\\begin{center}\n    \\includegraphics[width=0.45\\linewidth]{Figures/${fn}}\n\\end{center}\n`)
    } catch (e) { toast.error((e as Error).message) }
  }

  const unused = vars.filter((v) => !detected.includes(v.name)).map((v) => v.name)

  return (
    <div>
      <PageHeader title={editId ? 'Modifier la question' : 'Importer une question'}
        subtitle={editId ? <span className="font-mono text-xs">{editId}</span> : 'Écrivez la question en LaTeX ; chaque \\v{nom} devient une variable.'}
        actions={<>
          {editId && <Button variant="ghost" onClick={remove}><Trash2 className="h-4 w-4" />Supprimer</Button>}
          <Button variant="outline" onClick={runTest} disabled={!!busy}>{busy === 'test' ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}Tester (5 tirages)</Button>
          <Button onClick={save} disabled={!!busy || !name}>{busy === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Enregistrer</Button>
        </>} />

      <div className="grid gap-6 p-8 2xl:grid-cols-[1fr_520px]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Identification" />
            <CardBody className="grid gap-4 md:grid-cols-3">
              <Field label="Cours">
                <Select value={course} onChange={(v) => { setCourse(v); setTopic(courses.find((c) => c.code === v)?.topics[0]?.name ?? '__new') }} options={courses.map((c) => ({ value: c.code, label: c.code }))} />
              </Field>
              <Field label="Section (thème)">
                <Select value={topic} onChange={setTopic} options={[...(courseObj?.topics ?? []).map((t) => ({ value: t.name, label: t.label })), { value: '__new', label: '+ Nouveau thème…' }]} />
              </Field>
              {topic === '__new' ? (
                <Field label="Nouveau thème" hint="Sans accents ni espaces, ex. Effet_Compton"><Input value={newTopic} onChange={(e) => setNewTopic(e.target.value)} /></Field>
              ) : <div className="hidden md:block" />}
              <Field label="Nom du fichier" hint="ex. masse_ressort_energie"><Input value={name} onChange={(e) => setName(e.target.value.replace(/[^A-Za-z0-9_-]/g, '_'))} /></Field>
              <Field label="Titre" className="md:col-span-2"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Masse-ressort sachant E, m, k" /></Field>
              <Field label="Type">
                <Segmented value={qtype} onChange={(v) => { setQtype(v); if (v === 'conceptuel') { setPoints(4); setTime(4); setMode('none') } }}
                  options={[{ value: 'developpement', label: 'Développement' }, { value: 'conceptuel', label: 'Conceptuelle' }]} />
              </Field>
              <div className="grid grid-cols-3 gap-3 md:col-span-2">
                <Field label="Points"><Input type="number" value={points} onChange={(e) => setPoints(Number(e.target.value))} /></Field>
                <Field label="Temps estimé (min)"><Input type="number" value={time} onChange={(e) => setTime(Number(e.target.value))} /></Field>
                <Field label="Difficulté">
                  <div className="flex h-9 items-center gap-1">
                    {[1, 2, 3, 4, 5].map((d) => (
                      <button key={d} type="button" onClick={() => setDifficulty(d)}
                        className={cn('h-8 w-8 rounded-md text-sm font-semibold cursor-pointer', d <= difficulty ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}>{d}</button>
                    ))}
                  </div>
                </Field>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Énoncé (LaTeX)" description={<>Insérez une valeur avec <code className="rounded bg-muted px-1">{'\\v{m}'}</code>, ex. <code className="rounded bg-muted px-1">{'\\qty{\\v{m}}{g}'}</code></>}
              action={<>
                <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.pdf" className="hidden" onChange={(e) => e.target.files?.[0] && uploadFigure(e.target.files[0])} />
                <Button size="sm" variant="outline" onClick={() => fileRef.current?.click()}><ImagePlus className="h-3.5 w-3.5" />Figure</Button>
              </>} />
            <CardBody className="space-y-3">
              <LatexEditor value={body} onChange={setBody} minHeight="200px" placeholder={'L\'énergie mécanique d\'un système bloc-ressort est de \\qty{\\v{Em}}{J}...'} />
              {isConcept && <p className="text-xs text-muted-foreground">Pour des choix mélangés à chaque version, placez <code className="rounded bg-muted px-1">\choices</code> dans l'énoncé et listez les choix plus bas.</p>}
              {figures.length > 0 && <div className="flex flex-wrap gap-2">{figures.map((f) => <Badge key={f}>{f}<button onClick={() => setFigures(figures.filter((x) => x !== f))} className="cursor-pointer"><X className="h-3 w-3" /></button></Badge>)}</div>}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Variables" description="Une ligne par variable détectée : intervalle et type de nombre. Les calculs utilisent les unités SI." />
            <CardBody className="space-y-3">
              {vars.length === 0 && <p className="text-sm text-muted-foreground">Aucune variable : écrivez <code>{'\\v{nom}'}</code> dans l'énoncé.</p>}
              {vars.map((v, i) => (
                <div key={v.name} className={cn('grid grid-cols-12 items-end gap-2 rounded-lg border p-3', unused.includes(v.name) && 'border-dashed opacity-70')}>
                  <div className="col-span-12 flex items-center justify-between md:col-span-2 md:block">
                    <div className="font-mono text-sm font-semibold">{v.name}</div>
                    {unused.includes(v.name) && <button className="text-xs text-danger cursor-pointer" onClick={() => setVars(vars.filter((_, j) => j !== i))}>retirer (inutilisée)</button>}
                  </div>
                  <Field label="Type" className="col-span-6 md:col-span-2"><Select className="h-8 text-xs" value={v.type} onChange={(t) => setVar(i, { type: t as VarRow['type'] })} options={VAR_TYPES} /></Field>
                  {v.type === 'choice' || v.type === 'text' ? (
                    <Field label={v.type === 'text' ? 'Valeurs (séparées par ;;)' : 'Valeurs (séparées par ,)'} className="col-span-6 md:col-span-4">
                      <Input className="h-8 text-xs" value={v.valuesText ?? ''} onChange={(e) => setVar(i, { valuesText: e.target.value })} />
                    </Field>
                  ) : (<>
                    <Field label="Min" className="col-span-3 md:col-span-1"><Input className="h-8 px-2 text-xs" type="number" value={v.min ?? ''} onChange={(e) => setVar(i, { min: e.target.value as unknown as number })} /></Field>
                    <Field label="Max" className="col-span-3 md:col-span-1"><Input className="h-8 px-2 text-xs" type="number" value={v.max ?? ''} onChange={(e) => setVar(i, { max: e.target.value as unknown as number })} /></Field>
                    {v.type === 'sigfig'
                      ? <Field label="C.S." className="col-span-3 md:col-span-2"><Input className="h-8 px-2 text-xs" type="number" value={v.sigfigs ?? 3} onChange={(e) => setVar(i, { sigfigs: Number(e.target.value) })} /></Field>
                      : <Field label="Pas" className="col-span-3 md:col-span-2"><Input className="h-8 px-2 text-xs" type="number" value={v.step ?? ''} onChange={(e) => setVar(i, { step: e.target.value as unknown as number })} /></Field>}
                  </>)}
                  <Field label="Unité" className="col-span-3 md:col-span-1"><Input className="h-8 px-2 text-xs" value={v.unit ?? ''} onChange={(e) => setVar(i, { unit: e.target.value })} /></Field>
                  <Field label="Facteur SI" className="col-span-3 md:col-span-1"><Input className="h-8 px-2 text-xs" type="number" placeholder="1" value={v.si ?? ''} onChange={(e) => setVar(i, { si: e.target.value as unknown as number })} /></Field>
                  <Field label="Description" className="col-span-12 md:col-span-2"><Input className="h-8 text-xs" value={v.label ?? ''} onChange={(e) => setVar(i, { label: e.target.value })} placeholder="Masse du bloc" /></Field>
                </div>
              ))}
              <div className="space-y-2 pt-2">
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Contraintes (optionnel)</div>
                {constraints.map((c, i) => (
                  <div key={i} className="flex gap-2">
                    <Input className="font-mono text-xs" value={c} onChange={(e) => setConstraints(constraints.map((x, j) => (j === i ? e.target.value : x)))} placeholder="v < 0.9*sqrt(2*Em/m)" />
                    <Button size="icon" variant="ghost" onClick={() => setConstraints(constraints.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
                <Button size="sm" variant="ghost" className="text-primary" onClick={() => setConstraints([...constraints, ''])}><Plus className="h-3.5 w-3.5" />Ajouter une contrainte</Button>
              </div>
            </CardBody>
          </Card>

          {isConcept && (
            <Card>
              <CardHeader title="Choix de réponse" description="Mélangés à chaque version ; le corrigé suit le mélange." />
              <CardBody className="space-y-2">
                {choices.map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <button onClick={() => setAnswer(String.fromCharCode(65 + i))} title="Bonne réponse"
                      className={cn('grid h-8 w-8 shrink-0 place-items-center rounded-md text-sm font-semibold cursor-pointer', answer === String.fromCharCode(65 + i) ? 'bg-success text-white' : 'bg-muted')}>{String.fromCharCode(65 + i)}</button>
                    <Input value={c} onChange={(e) => setChoices(choices.map((x, j) => (j === i ? e.target.value : x)))} />
                    <Button size="icon" variant="ghost" onClick={() => setChoices(choices.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
                <div className="flex flex-wrap items-center gap-4 pt-1">
                  <Button size="sm" variant="ghost" className="text-primary" onClick={() => setChoices([...choices, ''])}><Plus className="h-3.5 w-3.5" />Ajouter un choix</Button>
                  <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={pinLast > 0} onChange={(e) => setPinLast(e.target.checked ? 1 : 0)} />Garder le dernier choix à la fin
                  </label>
                  {!choices.length && <Field label="Bonne réponse"><Input className="w-20" value={answer} onChange={(e) => setAnswer(e.target.value.toUpperCase().slice(0, 1))} /></Field>}
                </div>
                <Field label="Explication (corrigé)"><Textarea value={explanation} onChange={(e) => setExplanation(e.target.value)} /></Field>
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader title="Solution" description="Automatique quand c'est possible, sinon en LaTeX." />
            <CardBody className="space-y-4">
              <Segmented value={mode} onChange={setMode} options={[
                { value: 'auto', label: 'Automatique (étapes)' }, { value: 'answers_only', label: 'Réponses seulement' },
                { value: 'manual', label: 'LaTeX' }, { value: 'none', label: 'Aucune' },
              ]} />
              {(mode === 'auto' || mode === 'answers_only' || mode === 'manual') && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">
                    {mode === 'auto' ? 'Pour chaque sous-question : l\'équation de départ et l\'inconnue. L\'application isole l\'inconnue et rédige les 5 étapes.'
                      : mode === 'answers_only' ? 'Pour chaque sous-question : la formule de la réponse finale.'
                        : 'Optionnel : formules des réponses pour le corrigé rapide.'}
                  </p>
                  {parts.map((p, i) => (
                    <div key={i} className="grid grid-cols-12 items-end gap-2 rounded-lg border p-3">
                      <Field label="Partie" className="col-span-2 md:col-span-1"><Input className="h-8 px-2 text-xs" value={p.key} onChange={(e) => setPart(i, { key: e.target.value })} /></Field>
                      {mode === 'auto' || p.kind === 'equation' ? (<>
                        <Field label="Inconnue" className="col-span-4 md:col-span-2"><Input className="h-8 font-mono text-xs" value={p.find ?? ''} onChange={(e) => setPart(i, { find: e.target.value, kind: 'equation' })} placeholder="A" /></Field>
                        <Field label="Équation" className="col-span-6 md:col-span-4"><Input className="h-8 font-mono text-xs" value={p.equation ?? ''} onChange={(e) => setPart(i, { equation: e.target.value, kind: 'equation' })} placeholder="Em = k*A**2/2" /></Field>
                      </>) : (
                        <Field label="Formule" className="col-span-10 md:col-span-6"><Input className="h-8 font-mono text-xs" value={p.expr ?? ''} onChange={(e) => setPart(i, { expr: e.target.value })} placeholder="sqrt(2*Em/k)" /></Field>
                      )}
                      <Field label="Unité" className="col-span-4 md:col-span-1"><Input className="h-8 px-2 text-xs" value={p.unit ?? ''} onChange={(e) => setPart(i, { unit: e.target.value })} /></Field>
                      <Field label="Description" className="col-span-6 md:col-span-3"><Input className="h-8 text-xs" value={p.label ?? ''} onChange={(e) => setPart(i, { label: e.target.value })} placeholder="Amplitude" /></Field>
                      <div className="col-span-2 flex justify-end md:col-span-1">
                        <Button size="icon" variant="ghost" onClick={() => setParts(parts.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></Button>
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" className="text-primary" onClick={() => setParts([...parts, { key: String.fromCharCode(97 + parts.length), kind: 'equation' }])}><Plus className="h-3.5 w-3.5" />Équation</Button>
                    {mode !== 'auto' && <Button size="sm" variant="ghost" className="text-primary" onClick={() => setParts([...parts, { key: String.fromCharCode(97 + parts.length), kind: 'expr' }])}><Plus className="h-3.5 w-3.5" />Formule directe</Button>}
                  </div>
                </div>
              )}
              {mode === 'manual' && <LatexEditor value={solution} onChange={setSolution} minHeight="240px" placeholder={'\\subsubsection*{Question a)}\n... \\fpeval{round(sqrt(2*\\v{Em}/\\v{k}), 3)} ...'} />}
            </CardBody>
          </Card>
        </div>

        <div className="2xl:sticky 2xl:top-24 2xl:self-start">
          <TestPanel test={test} busy={busy === 'test'} onTest={runTest} />
        </div>
      </div>
    </div>
  )
}

function TestPanel({ test, busy, onTest }: { test: TestResult | null; busy: boolean; onTest: () => void }) {
  if (!test) return (
    <Card className="grid min-h-[300px] place-items-center border-dashed p-8 text-center">
      <div>
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-accent text-primary"><Wand2 className="h-6 w-6" /></div>
        <p className="text-sm text-muted-foreground">Le test compile la question avec 5 jeux de valeurs aléatoires et affiche le PDF et les réponses.</p>
        <Button className="mt-4" variant="outline" onClick={onTest} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}Tester</Button>
      </div>
    </Card>
  )
  const ok = test.problems.length === 0
  return (
    <Card>
      <CardHeader title={<span className={cn('flex items-center gap-2', ok ? 'text-success' : 'text-danger')}>{ok ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}{ok ? 'Compilation réussie' : 'À corriger'}</span>} />
      <CardBody className="space-y-4">
        {!ok && <ul className="space-y-1 text-sm text-danger">{test.problems.map((p) => <li key={p}>• {p}</li>)}</ul>}
        {test.log && <pre className="max-h-40 overflow-auto rounded-lg bg-muted p-2 text-[11px]">{test.log}</pre>}
        {test.draws.length > 0 && (
          <div className="overflow-auto rounded-lg border">
            <table className="w-full text-xs">
              <thead className="bg-muted text-muted-foreground"><tr><th className="px-2 py-1.5 text-left">#</th>{Object.keys(test.draws[0]).map((k) => <th key={k} className="px-2 py-1.5 text-left font-mono">{k}</th>)}{test.answers[0]?.map((a) => <th key={a.key} className="px-2 py-1.5 text-left">{a.key}) {a.name}</th>)}</tr></thead>
              <tbody>{test.draws.map((d, i) => (
                <tr key={i} className="border-t"><td className="px-2 py-1.5">{i + 1}</td>{Object.values(d).map((x, j) => <td key={j} className="px-2 py-1.5 font-mono">{String(x).slice(0, 24)}</td>)}
                  {test.answers[i]?.map((a) => <td key={a.key} className="px-2 py-1.5 font-mono text-primary">{a.value} {a.unit}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {test.pdf && <iframe title="Aperçu" src={`/api/previews/${test.pdf}.pdf`} className="h-[70vh] w-full rounded-lg border bg-white" />}
      </CardBody>
    </Card>
  )
}
