import { useEffect, useState } from 'react'
import { FolderOpen } from 'lucide-react'
import { PageHeader } from '@/App'
import { Button } from '@/components/ui/button'
import { Badge, Card, CardBody, CardHeader } from '@/components/ui/card'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

export default function Exports() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.exports>>>([])
  const [desktop, setDesktop] = useState(false)
  useEffect(() => { api.exports().then(setItems); api.health().then((h) => setDesktop(h.desktop)) }, [])
  return (
    <div>
      <PageHeader title="Examens produits" subtitle="Tous les PDF générés, par cours et par examen." />
      <div className="space-y-4 p-8">
        {!items.length && <p className="py-16 text-center text-muted-foreground">Aucun examen généré pour l'instant.</p>}
        {items.map((e) => (
          <Card key={e.folder}>
            <CardHeader title={<span className="flex items-center gap-2">{e.name.replace(/_/g, ' ')} <Badge>{e.course}</Badge></span>}
              description={new Date(e.modified).toLocaleString('fr-CA')}
              action={desktop && <Button size="sm" variant="outline" onClick={() => api.open(e.folder)}><FolderOpen className="h-3.5 w-3.5" />Ouvrir</Button>} />
            <CardBody className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {e.files.map((f) => {
                const sol = f.includes('_solution')
                return (
                  <a key={f} href={`/api/exports/${e.course}/${e.name}/${f}`} target="_blank" rel="noreferrer"
                    onClick={(ev) => { if (desktop) { ev.preventDefault(); api.open(`${e.folder}/${f}`) } }}
                    className="flex items-center gap-3 rounded-lg border px-3 py-2 text-sm hover:bg-muted">
                    <span className={cn('grid h-7 w-7 place-items-center rounded-md text-[9px] font-bold', sol ? 'bg-primary text-primary-foreground' : 'bg-danger/10 text-danger')}>{sol ? 'SOL' : 'PDF'}</span>
                    <span className="truncate font-mono text-xs">{f}</span>
                  </a>
                )
              })}
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  )
}
