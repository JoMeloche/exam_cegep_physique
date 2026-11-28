import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { ImagePlus, Plus, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { api, type Config, type CourseInfo } from '@/lib/api'

export function ProfessorsEditor({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="space-y-2">
      {value.map((p, i) => (
        <div key={i} className="flex gap-2">
          <Input value={p} placeholder="Prénom Nom" aria-label={`Professeur ${i + 1}`} onChange={(e) => onChange(value.map((x, j) => (j === i ? e.target.value : x)))} />
          <Button size="icon" variant="ghost" aria-label={`Retirer ${p || 'ce professeur'}`} title="Retirer" onClick={() => onChange(value.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></Button>
        </div>
      ))}
      <Button size="sm" variant="ghost" className="text-primary" onClick={() => onChange([...value, ''])}><Plus className="h-3.5 w-3.5" />Ajouter un professeur</Button>
    </div>
  )
}

export function CoursesEditor({ value, onChange, bankFolders }: { value: Record<string, CourseInfo>; onChange: (v: Record<string, CourseInfo>) => void; bankFolders: string[] }) {
  const [code, setCode] = useState('')
  const set = (c: string, patch: Partial<CourseInfo>) => onChange({ ...value, [c]: { ...value[c], ...patch } })
  return (
    <div className="space-y-3">
      <div className="hidden grid-cols-12 gap-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground md:grid">
        <div className="col-span-2">Dossier</div><div className="col-span-2">Code imprimé</div><div className="col-span-2">Titre (en-tête)</div>
        <div className="col-span-2">Nom du cours</div><div className="col-span-1">Groupe</div><div className="col-span-2">Utilise aussi la banque de</div>
      </div>
      {Object.entries(value).map(([c, info]) => (
        <div key={c} className="grid grid-cols-12 items-center gap-2">
          <div className="col-span-12 font-mono text-sm md:col-span-2">{c}</div>
          <Input className="col-span-6 font-mono md:col-span-2" value={info.print_code ?? ''} placeholder={c} aria-label={`Code du cours imprimé pour ${c}`} title="Code du cours tel qu'il apparaît sur l'en-tête et dans le nom des fichiers. Laissez vide pour utiliser le nom du dossier."
            onChange={(e) => set(c, { print_code: e.target.value })} />
          <Input className="col-span-6 md:col-span-2" value={info.title ?? ''} placeholder="Physique" aria-label={`Titre imprimé sur l'en-tête pour ${c}`} title="Imprimé sur l'en-tête, devant le code du cours" onChange={(e) => set(c, { title: e.target.value })} />
          <Input className="col-span-6 md:col-span-2" value={info.full_title ?? ''} placeholder="Mécanique" aria-label={`Nom du cours ${c}`} title={info.full_title} onChange={(e) => set(c, { full_title: e.target.value })} />
          <Input className="col-span-5 md:col-span-1" value={info.group ?? ''} placeholder="groupe 1" aria-label={`Groupe de ${c}`} onChange={(e) => set(c, { group: e.target.value })} />
          <div className="col-span-6 flex flex-wrap items-center gap-1 md:col-span-2">
            {(info.questions_from ?? []).map((f) => (
              <Badge key={f}>{f}<button className="cursor-pointer" aria-label={`Ne plus utiliser la banque ${f}`} onClick={() => set(c, { questions_from: (info.questions_from ?? []).filter((x) => x !== f) })}><X className="h-3 w-3" /></button></Badge>
            ))}
            <select aria-label={`Utiliser aussi la banque d'un autre dossier pour ${c}`} className="h-7 cursor-pointer rounded-md border bg-card px-1 text-xs" value="" onChange={(e) => e.target.value && set(c, { questions_from: Array.from(new Set([...(info.questions_from ?? []), e.target.value])) })}>
              <option value="">+ banque…</option>
              {bankFolders.filter((f) => f !== c).map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <Button size="icon" variant="ghost" className="col-span-1" aria-label={`Retirer le cours ${c}`} title="Retirer le cours" onClick={() => { const v = { ...value }; delete v[c]; onChange(v) }}><Trash2 className="h-4 w-4" /></Button>
        </div>
      ))}
      <form className="flex flex-wrap gap-2 pt-1" onSubmit={(e) => { e.preventDefault(); const k = code.trim().toUpperCase(); if (!k) return; if (value[k]) { toast.error(`Le cours ${k} existe déjà`); return } onChange({ ...value, [k]: { title: '', full_title: '', group: '' } }); setCode('') }}>
        <Input className="w-full font-mono sm:w-56" aria-label="Code du nouveau cours" value={code} onChange={(e) => setCode(e.target.value.replace(/[^A-Za-z0-9_-]/g, ''))} placeholder="203-NYA-05" />
        <Button type="submit" variant="outline"><Plus className="h-4 w-4" />Ajouter un cours</Button>
      </form>
      <p className="text-xs text-muted-foreground">L'en-tête de l'examen affiche « <b>Titre</b> <b>Code imprimé</b> (groupe) », par exemple « Physique 203-NYC-05 ». Le code imprimé sert aussi au nom des fichiers; laissez-le vide pour utiliser le nom du dossier.</p>
      <p className="text-xs text-muted-foreground">« Utilise aussi la banque de » permet, par exemple, à votre cours 203-NYC-05 de piger dans les questions du dossier 203-SN3-RE.</p>
    </div>
  )
}

export function LogoEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  async function upload(f: File) {
    try { const { name } = await api.uploadFigure(f); onChange(name) } catch (e) { toast.error((e as Error).message) }
  }
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-16 w-28 place-items-center overflow-hidden rounded-lg border bg-white">
        {value ? <img src={`/api/figures/${encodeURIComponent(value)}`} alt="Logo de l'établissement" className="max-h-14 max-w-24 object-contain" /> : <span className="text-xs text-muted-foreground">aucun logo</span>}
      </div>
      <input ref={ref} type="file" accept=".png,.jpg,.jpeg,.pdf" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <Button size="sm" variant="outline" onClick={() => ref.current?.click()}><ImagePlus className="h-3.5 w-3.5" />{value ? 'Changer' : 'Téléverser'}</Button>
      {value && <Button size="sm" variant="ghost" onClick={() => onChange('')}>Retirer</Button>}
    </div>
  )
}

export function bankFoldersOf(cfg: Config | null, courseCodes: string[]) {
  return Array.from(new Set([...courseCodes, ...Object.keys(cfg?.courses ?? {})])).sort()
}
