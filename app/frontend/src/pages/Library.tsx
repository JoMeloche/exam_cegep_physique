import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { AlertTriangle, Clock, Eye, Loader2, Plus, Search } from 'lucide-react'
import { PageHeader } from '@/App'
import { Button } from '@/components/ui/button'
import { Badge, Card, Difficulty } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Segmented } from '@/components/ui/switch'
import { api, type Course, type QuestionSummary } from '@/lib/api'
import { cn } from '@/lib/utils'

const MODE_LABEL: Record<string, string> = { auto: 'Auto', manual: 'LaTeX', answers_only: 'Réponses', none: 'Aucune' }

export default function Library() {
  const nav = useNavigate()
  const [courses, setCourses] = useState<Course[]>([])
  const [course, setCourse] = useState<string>('')
  const [topic, setTopic] = useState<string>('')
  const [type, setType] = useState<'all' | 'developpement' | 'conceptuel'>('all')
  const [search, setSearch] = useState('')
  const [review, setReview] = useState(false)
  const [sort, setSort] = useState<'topic' | 'unused' | 'difficulty'>('topic')
  const [items, setItems] = useState<QuestionSummary[] | null>(null)
  const [previewing, setPreviewing] = useState<string | null>(null)

  useEffect(() => { api.courses().then((cs) => { setCourses(cs); setCourse(cs.find((c) => c.topics.length)?.code ?? cs[0]?.code ?? '') }) }, [])
  useEffect(() => {
    if (!course) return
    setItems(null)
    const t = setTimeout(() => api.questions({ course, topic: topic || undefined, type: type === 'all' ? undefined : type, q: search || undefined })
      .then((r) => setItems(r.items)).catch((e) => toast.error(e.message)), 150)
    return () => clearTimeout(t)
  }, [course, topic, type, search])

  const courseObj = courses.find((c) => c.code === course)
  const shown = useMemo(() => {
    let xs = items ?? []
    if (review) xs = xs.filter((q) => q.needs_review)
    if (sort === 'unused') xs = [...xs].sort((a, b) => (a.last_used || '').localeCompare(b.last_used || ''))
    if (sort === 'difficulty') xs = [...xs].sort((a, b) => a.difficulty - b.difficulty)
    return xs
  }, [items, review, sort])

  const grouped = useMemo(() => {
    const m = new Map<string, QuestionSummary[]>()
    for (const q of shown) { const k = sort === 'topic' ? q.topic : ''; m.set(k, [...(m.get(k) ?? []), q]) }
    return [...m.entries()]
  }, [shown, sort])

  async function preview(q: QuestionSummary) {
    setPreviewing(q.id)
    try {
      const full = await api.question(q.id)
      const r = await api.testQuestion({ course: full.course, topic: full.topic, name: full.name, meta: full.meta, body: full.body, solution_tex: full.solution_tex, draws: 1 })
      if (r.pdf) window.open(`/api/previews/${r.pdf}.pdf`, '_blank')
      else toast.error(r.problems.join(' · '))
    } catch (e) { toast.error((e as Error).message) } finally { setPreviewing(null) }
  }

  const label = (t: string) => courseObj?.topics.find((x) => x.name === t)?.label ?? t.replace(/_/g, ' ')
  const reviewCount = (items ?? []).filter((q) => q.needs_review).length

  return (
    <div>
      <PageHeader title="Bibliothèque" subtitle={items ? `${shown.length} question${shown.length > 1 ? 's' : ''}` : 'Chargement…'}
        actions={<Button onClick={() => nav('/question/new')}><Plus className="h-4 w-4" />Nouvelle question</Button>} />
      <div className="space-y-6 p-8">
        <Card className="flex flex-wrap items-center gap-3 p-3">
          <div className="relative min-w-[240px] flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Rechercher dans le titre ou le texte…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select className="w-44" value={course} onChange={(v) => { setCourse(v); setTopic('') }} options={courses.map((c) => ({ value: c.code, label: c.code }))} />
          <Select className="w-56" value={topic || '__all'} onChange={(v) => setTopic(v === '__all' ? '' : v)}
            options={[{ value: '__all', label: 'Tous les thèmes' }, ...(courseObj?.topics ?? []).map((t) => ({ value: t.name, label: `${t.label} (${t.n_dev + t.n_concept})` }))]} />
          <Segmented value={type} onChange={setType} options={[{ value: 'all', label: 'Toutes' }, { value: 'developpement', label: 'Développement' }, { value: 'conceptuel', label: 'Conceptuelles' }]} />
          <Select className="w-48" value={sort} onChange={(v) => setSort(v as typeof sort)} options={[{ value: 'topic', label: 'Par thème' }, { value: 'unused', label: 'Moins utilisées d\'abord' }, { value: 'difficulty', label: 'Par difficulté' }]} />
          {reviewCount > 0 && (
            <button onClick={() => setReview(!review)} className={cn('flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm cursor-pointer', review ? 'bg-warning/15 text-warning' : 'text-muted-foreground hover:bg-muted')}>
              <AlertTriangle className="h-4 w-4" />À réviser ({reviewCount})
            </button>
          )}
        </Card>

        {!items && <div className="py-20 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" /></div>}
        {grouped.map(([t, qs]) => (
          <section key={t}>
            {t && <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">{label(t)} <Badge>{qs.length}</Badge></h2>}
            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {qs.map((q) => (
                <Card key={q.id} className="group flex flex-col p-4 transition-shadow hover:shadow-md">
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <Link to={`/question/edit/${q.id}`} className="font-medium leading-snug hover:text-primary">{q.title}</Link>
                    <Badge tone={q.type === 'conceptuel' ? 'primary' : 'default'}>{q.type === 'conceptuel' ? 'Conceptuelle' : 'Développement'}</Badge>
                  </div>
                  <p className="line-clamp-2 flex-1 text-sm text-muted-foreground">{q.excerpt}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{q.time_min} min</span>
                    <Difficulty value={q.difficulty} />
                    <span>{q.n_variables} var.</span>
                    {q.type === 'conceptuel'
                      ? <Badge tone={q.answer ? 'success' : 'warning'}>{q.answer ? `Réponse : ${q.answer}` : 'Réponse manquante'}</Badge>
                      : <Badge tone={q.solution_mode === 'none' ? 'warning' : 'success'}>Solution : {MODE_LABEL[q.solution_mode]}</Badge>}
                    {q.needs_review && <Badge tone="warning">À réviser</Badge>}
                    <span className="ml-auto">{q.times_used ? `utilisée ${q.times_used}× · ${q.last_used}` : 'jamais utilisée'}</span>
                  </div>
                  <div className="mt-3 flex gap-2 border-t pt-3 opacity-70 transition-opacity group-hover:opacity-100">
                    <Button size="sm" variant="outline" onClick={() => preview(q)} disabled={previewing === q.id}>
                      {previewing === q.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />}Aperçu PDF
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => nav(`/question/edit/${q.id}`)}>Modifier</Button>
                  </div>
                </Card>
              ))}
            </div>
          </section>
        ))}
        {items && !shown.length && <p className="py-16 text-center text-muted-foreground">Aucune question ne correspond.</p>}
      </div>
    </div>
  )
}
