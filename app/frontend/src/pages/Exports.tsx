import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Download, FileText, FolderOpen, Loader2, Sparkles, Trash2 } from 'lucide-react'
import { PageHeader } from '@/App'
import { Button } from '@/components/ui/button'
import { Badge, Card, CardBody, CardHeader } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Select } from '@/components/ui/select'
import { api, exportZipUrl, type ExportItem } from '@/lib/api'
import { cn } from '@/lib/utils'

const dateFmt = new Intl.DateTimeFormat('fr-CA', { dateStyle: 'long' })
const stampFmt = new Intl.DateTimeFormat('fr-CA', { dateStyle: 'medium', timeStyle: 'short' })

function examDate(iso?: string) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  return dateFmt.format(new Date(y, m - 1, d))
}

export function PdfLink({ course, folder, file, desktop, folderPath, solution: sol }: { course: string; folder: string; file: string; desktop: boolean; folderPath: string; solution: boolean }) {
  return (
    <a href={`/api/exports/${encodeURIComponent(course)}/${encodeURIComponent(folder)}/${encodeURIComponent(file)}`} target="_blank" rel="noreferrer"
      onClick={(ev) => { if (desktop) { ev.preventDefault(); api.open(`${folderPath}/${file}`) } }}
      title={file}
      className={cn('flex min-w-0 items-center gap-3 rounded-lg border px-3 py-2 text-sm transition-colors hover:bg-muted', sol && 'bg-accent/40')}>
      <span className={cn('grid h-7 w-7 shrink-0 place-items-center rounded-md text-[9px] font-bold', sol ? 'bg-primary text-primary-foreground' : 'bg-danger/10 text-danger')} aria-hidden>{sol ? 'SOL' : 'PDF'}</span>
      <span className="truncate font-mono text-xs">{file}</span>
    </a>
  )
}

export default function Exports() {
  const [items, setItems] = useState<ExportItem[] | null>(null)
  const [desktop, setDesktop] = useState(false)
  const [course, setCourse] = useState('')
  const [deleting, setDeleting] = useState<ExportItem | null>(null)
  const [busy, setBusy] = useState(false)
  const load = () => api.exports().then(setItems).catch((e) => { toast.error(e.message); setItems([]) })
  useEffect(() => { load(); api.health().then((h) => setDesktop(h.desktop)).catch(() => {}) }, [])

  const courses = useMemo(() => Array.from(new Set((items ?? []).map((e) => e.course))).sort(), [items])
  const shown = (items ?? []).filter((e) => !course || e.course === course)

  async function remove() {
    if (!deleting) return
    setBusy(true)
    try {
      await api.deleteExport(deleting.course, deleting.name)
      toast.success('Examen supprimé')
      setDeleting(null); await load()
    } catch (e) { toast.error((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div>
      <PageHeader title="Examens produits" subtitle="Tous les PDF générés, par cours et par examen."
        actions={courses.length > 1 && (
          <Select className="w-48" value={course || '__all'} onChange={(v) => setCourse(v === '__all' ? '' : v)}
            options={[{ value: '__all', label: 'Tous les cours' }, ...courses.map((c) => ({ value: c, label: c }))]} />
        )} />
      <div className="space-y-4 p-4 sm:p-6 lg:p-8">
        {!items && <div className="py-20 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" /></div>}
        {items && !items.length && (
          <Card className="grid min-h-[320px] place-items-center border-dashed p-8 text-center">
            <div className="max-w-sm">
              <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-accent text-primary"><FileText className="h-7 w-7" /></div>
              <h2 className="text-lg font-semibold">Aucun examen pour l'instant</h2>
              <p className="mt-2 text-sm text-muted-foreground">Les examens que vous exportez dans l'écran Générer apparaissent ici, avec leurs solutionnaires.</p>
              <Link to="/" className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
                <Sparkles className="h-4 w-4" />Générer un examen
              </Link>
            </div>
          </Card>
        )}
        {shown.map((e) => {
          const pairs = e.pairs ?? e.files.map((f) => ({ exam: f, solution: null }))
          const meta = [e.date && examDate(e.date), e.professor, e.n_versions && `${e.n_versions} version${e.n_versions > 1 ? 's' : ''}`].filter(Boolean).join(' · ')
          return (
            <Card key={e.course + e.name}>
              <CardHeader
                title={<span className="flex flex-wrap items-center gap-2">{e.name.replace(/_/g, ' ')} <Badge>{e.course}</Badge></span>}
                description={<>{meta && <span>{meta} · </span>}<span>produit le {stampFmt.format(new Date(e.modified))}</span></>}
                action={<div className="flex flex-wrap justify-end gap-2">
                  {desktop
                    ? <Button size="sm" variant="outline" onClick={() => api.open(e.folder)}><FolderOpen className="h-3.5 w-3.5" />Ouvrir le dossier</Button>
                    : <a href={exportZipUrl(e.course, e.name)} className="inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium hover:bg-muted"><Download className="h-3.5 w-3.5" />Tout (ZIP)</a>}
                  <Button size="sm" variant="ghost" aria-label={`Supprimer ${e.name.replace(/_/g, ' ')} (${e.course})`} title="Supprimer" onClick={() => setDeleting(e)}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>} />
              <CardBody className="space-y-2">
                {pairs.map((p, i) => (
                  <div key={i} className="grid gap-2 sm:grid-cols-2">
                    {p.exam ? <PdfLink course={e.course} folder={e.name} file={p.exam} desktop={desktop} folderPath={e.folder} solution={false} /> : <span />}
                    {p.solution && <PdfLink course={e.course} folder={e.name} file={p.solution} desktop={desktop} folderPath={e.folder} solution />}
                  </div>
                ))}
                {!desktop && pairs.length > 1 && (
                  <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs">
                    <a className="text-primary hover:underline" href={exportZipUrl(e.course, e.name, 'exams')}>Examens seulement (ZIP)</a>
                    <a className="text-primary hover:underline" href={exportZipUrl(e.course, e.name, 'solutions')}>Solutionnaires seulement (ZIP)</a>
                  </div>
                )}
              </CardBody>
            </Card>
          )
        })}
      </div>
      <Dialog open={!!deleting} onOpenChange={(v) => !v && setDeleting(null)} title="Supprimer cet examen ?"
        description={deleting ? `${deleting.name.replace(/_/g, ' ')} (${deleting.course}) : les ${deleting.files.length} PDF et leurs sources LaTeX seront effacés. L'historique d'utilisation des questions est conservé.` : ''}>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDeleting(null)}>Annuler</Button>
          <Button variant="danger" onClick={remove} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}Supprimer</Button>
        </div>
      </Dialog>
    </div>
  )
}
