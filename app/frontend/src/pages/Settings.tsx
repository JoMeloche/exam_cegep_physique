import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { CheckCircle2, Plus, Save, Trash2, XCircle } from 'lucide-react'
import { PageHeader } from '@/App'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { Field, Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { api, type Config } from '@/lib/api'

export default function Settings() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [health, setHealth] = useState<{ root: string; latex: string | null; version: string } | null>(null)
  const [newCourse, setNewCourse] = useState('')
  useEffect(() => { api.config().then(setCfg); api.health().then(setHealth) }, [])
  if (!cfg) return null
  const set = (patch: Partial<Config>) => setCfg({ ...cfg, ...patch })

  async function save() {
    try { setCfg(await api.saveConfig(cfg!)); setHealth(await api.health()); toast.success('Paramètres enregistrés') } catch (e) { toast.error((e as Error).message) }
  }

  return (
    <div>
      <PageHeader title="Paramètres" subtitle={health && <span className="font-mono text-xs">Bibliothèque : {health.root}</span>}
        actions={<Button onClick={save}><Save className="h-4 w-4" />Enregistrer</Button>} />
      <div className="grid gap-6 p-8 lg:grid-cols-2">
        <Card>
          <CardHeader title="Établissement et professeurs" />
          <CardBody className="space-y-4">
            <Field label="Établissement"><Input value={cfg.school} onChange={(e) => set({ school: e.target.value })} /></Field>
            <Field label="Professeurs">
              <div className="space-y-2">
                {cfg.professors.map((p, i) => (
                  <div key={i} className="flex gap-2">
                    <Input value={p} onChange={(e) => set({ professors: cfg.professors.map((x, j) => (j === i ? e.target.value : x)) })} />
                    <Button size="icon" variant="ghost" onClick={() => set({ professors: cfg.professors.filter((_, j) => j !== i) })}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
                <Button size="sm" variant="ghost" className="text-primary" onClick={() => set({ professors: [...cfg.professors, ''] })}><Plus className="h-3.5 w-3.5" />Ajouter</Button>
              </div>
            </Field>
            <Field label="Professeur par défaut">
              <Select value={cfg.default_professor} onChange={(v) => set({ default_professor: v })} options={cfg.professors.filter(Boolean).map((p) => ({ value: p, label: p }))} />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="LaTeX et génération" />
          <CardBody className="space-y-4">
            <div className="flex items-center gap-2 rounded-lg bg-muted p-3 text-sm">
              {health?.latex ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-danger" />}
              <span className="truncate font-mono text-xs">{health?.latex ?? 'Aucune installation LaTeX trouvée'}</span>
            </div>
            <Field label="Chemin de LaTeX (optionnel)" hint="Laisser vide pour utiliser le LaTeX inclus avec l'application.">
              <Input value={cfg.latex.path} onChange={(e) => set({ latex: { ...cfg.latex, path: e.target.value } })} placeholder="C:\\…\\bin\\windows" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Marge de temps" hint="Temps estimé visé = durée × (1 − marge)">
                <Input type="number" step="0.05" min="0" max="0.6" value={cfg.time_margin} onChange={(e) => set({ time_margin: Number(e.target.value) })} />
              </Field>
              <Field label="Versions par défaut"><Input type="number" min="1" max="8" value={cfg.default_versions} onChange={(e) => set({ default_versions: Number(e.target.value) })} /></Field>
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Cours" description="Le code apparaît dans le nom des fichiers ; le titre et le groupe sur la page couverture." />
          <CardBody className="space-y-2">
            {Object.entries(cfg.courses).map(([code, c]) => (
              <div key={code} className="grid grid-cols-12 items-center gap-2">
                <div className="col-span-3 font-mono text-sm">{code}</div>
                <Input className="col-span-3" value={c.title ?? ''} placeholder="Titre (ex. Physique)" onChange={(e) => set({ courses: { ...cfg.courses, [code]: { ...c, title: e.target.value } } })} />
                <Input className="col-span-3" value={c.full_title ?? ''} placeholder="Nom complet" onChange={(e) => set({ courses: { ...cfg.courses, [code]: { ...c, full_title: e.target.value } } })} />
                <Input className="col-span-2" value={c.group ?? ''} placeholder="groupe 2" onChange={(e) => set({ courses: { ...cfg.courses, [code]: { ...c, group: e.target.value } } })} />
                <Button size="icon" variant="ghost" onClick={() => { const cs = { ...cfg.courses }; delete cs[code]; set({ courses: cs }) }}><Trash2 className="h-4 w-4" /></Button>
              </div>
            ))}
            <form className="flex gap-2 pt-2" onSubmit={(e) => { e.preventDefault(); if (newCourse) { set({ courses: { ...cfg.courses, [newCourse]: { title: '', group: '' } } }); setNewCourse('') } }}>
              <Input className="w-56 font-mono" value={newCourse} onChange={(e) => setNewCourse(e.target.value.replace(/[^A-Za-z0-9_-]/g, ''))} placeholder="203-NYA-05" />
              <Button type="submit" variant="outline"><Plus className="h-4 w-4" />Ajouter un cours</Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
