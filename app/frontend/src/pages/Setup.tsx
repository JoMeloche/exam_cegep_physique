import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, ArrowRight, Check, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardBody } from '@/components/ui/card'
import { Field, Input } from '@/components/ui/input'
import { CoursesEditor, LogoEditor, ProfessorsEditor, bankFoldersOf } from '@/components/ConfigEditors'
import { api, type Config } from '@/lib/api'
import { cn } from '@/lib/utils'

const STEPS = ['Établissement', 'Professeurs', 'Cours']

export default function Setup({ onDone }: { onDone: () => void }) {
  const nav = useNavigate()
  const [cfg, setCfg] = useState<Config | null>(null)
  const [folders, setFolders] = useState<string[]>([])
  const [step, setStep] = useState(0)
  useEffect(() => {
    api.config().then((c) => setCfg({ ...c, professors: c.professors.length ? c.professors : [''] }))
    api.courses().then((cs) => setFolders(cs.filter((c) => c.topics.length).map((c) => c.code)))
  }, [])
  if (!cfg) return null
  const set = (p: Partial<Config>) => setCfg({ ...cfg, ...p })
  const profs = cfg.professors.map((p) => p.trim()).filter(Boolean)
  const canNext = step === 0 ? cfg.school.trim() !== '' : step === 1 ? profs.length > 0 : Object.keys(cfg.courses).length > 0

  async function finish() {
    try {
      await api.saveConfig({ ...cfg!, professors: profs, default_professor: cfg!.default_professor && profs.includes(cfg!.default_professor) ? cfg!.default_professor : profs[0], setup_done: true })
      toast.success('Configuration terminée')
      onDone(); nav('/')
    } catch (e) { toast.error((e as Error).message) }
  }

  return (
    <div className="grid min-h-full place-items-center p-8">
      <div className="w-full max-w-3xl">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-primary text-primary-foreground"><FileText className="h-6 w-6" /></div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Bienvenue</h1>
            <p className="text-sm text-muted-foreground">Trois étapes pour adapter l'application à votre cégep. Tout se modifie plus tard dans Paramètres.</p>
          </div>
        </div>
        <div className="mb-4 flex gap-2">
          {STEPS.map((s, i) => (
            <div key={s} className={cn('flex flex-1 items-center gap-2 rounded-lg border px-3 py-2 text-sm', i === step ? 'border-primary bg-accent text-primary' : i < step ? 'text-success' : 'text-muted-foreground')}>
              <span className={cn('grid h-5 w-5 place-items-center rounded-full text-xs font-semibold', i < step ? 'bg-success text-white' : i === step ? 'bg-primary text-primary-foreground' : 'bg-muted')}>{i < step ? <Check className="h-3 w-3" /> : i + 1}</span>{s}
            </div>
          ))}
        </div>
        <Card>
          <CardBody className="min-h-[300px] space-y-5">
            {step === 0 && (<>
              <Field label="Nom de l'établissement" hint="Imprimé en haut de la page couverture."><Input autoFocus value={cfg.school} onChange={(e) => set({ school: e.target.value })} placeholder="Cégep de …" /></Field>
              <Field label="Logo (optionnel)"><LogoEditor value={cfg.logo} onChange={(logo) => set({ logo })} /></Field>
            </>)}
            {step === 1 && (
              <Field label="Professeurs" hint="Ils apparaissent dans le menu déroulant de l'écran Générer.">
                <ProfessorsEditor value={cfg.professors} onChange={(professors) => set({ professors })} />
              </Field>
            )}
            {step === 2 && (
              <Field label="Vos cours">
                <CoursesEditor value={cfg.courses} onChange={(courses) => set({ courses })} bankFolders={bankFoldersOf(cfg, folders)} />
              </Field>
            )}
          </CardBody>
          <div className="flex justify-between border-t px-5 py-4">
            <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={step === 0}><ArrowLeft className="h-4 w-4" />Retour</Button>
            {step < STEPS.length - 1
              ? <Button onClick={() => setStep(step + 1)} disabled={!canNext}>Suivant<ArrowRight className="h-4 w-4" /></Button>
              : <Button onClick={finish} disabled={!canNext}><Check className="h-4 w-4" />Terminer</Button>}
          </div>
        </Card>
      </div>
    </div>
  )
}
