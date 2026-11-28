import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Renders a PDF with pdf.js into canvases instead of an <iframe>.
 *
 * The desktop windows (Qt WebEngine on Linux, WebView2 on Windows, WKWebView on macOS) do not all ship a
 * built-in PDF viewer, and the ones that do embed it in an internal frame that the app's
 * Content-Security-Policy refuses. Drawing the pages ourselves works the same everywhere.
 */
let pdfjsPromise: Promise<typeof import('pdfjs-dist')> | undefined

/** pdf.js and its worker, loaded on first use (they are large) and shared by every preview. The worker is
 * bundled by Vite as a .js file so it is served with a JavaScript MIME type everywhere. */
function loadPdfjs() {
  pdfjsPromise ??= Promise.all([
    import('pdfjs-dist/legacy/build/pdf.mjs'),
    import('pdfjs-dist/legacy/build/pdf.worker.min.mjs?worker'),
  ]).then(([pdfjs, { default: PdfWorker }]) => {
    pdfjs.GlobalWorkerOptions.workerPort = new PdfWorker()
    return pdfjs as unknown as typeof import('pdfjs-dist')
  })
  return pdfjsPromise
}

export function PdfView({ url, title, className }: { url: string; title: string; className?: string }) {
  const box = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    const el = box.current
    if (!el) return
    let cancelled = false
    let destroy: (() => void) | undefined
    setState('loading')
    el.replaceChildren()
    ;(async () => {
      try {
        const pdfjs = await loadPdfjs()
        const task = pdfjs.getDocument({ url, useWasm: false, withCredentials: true })
        destroy = () => void task.destroy()
        const doc = await task.promise
        const width = Math.max(320, el.clientWidth - 32)
        const ratio = window.devicePixelRatio || 1
        for (let n = 1; n <= doc.numPages && !cancelled; n++) {
          const page = await doc.getPage(n)
          const base = page.getViewport({ scale: 1 })
          const viewport = page.getViewport({ scale: (width / base.width) * ratio })
          const canvas = document.createElement('canvas')
          canvas.width = Math.floor(viewport.width)
          canvas.height = Math.floor(viewport.height)
          canvas.style.width = `${width}px`
          canvas.className = 'mx-auto mb-4 block rounded bg-white shadow-sm ring-1 ring-black/10 last:mb-0'
          canvas.setAttribute('aria-label', `${title} — page ${n}`)
          await page.render({ canvas, viewport }).promise
          if (cancelled) return
          el.appendChild(canvas)
          if (n === 1) setState('ready')
        }
      } catch (e) {
        if (!cancelled) {
          console.error('PDF preview', e)
          setState('error')
        }
      }
    })()
    return () => {
      cancelled = true
      destroy?.()
    }
  }, [url, title])

  return (
    <div role="document" aria-label={title} aria-busy={state === 'loading'}
      className={cn('relative h-[70vh] w-full overflow-auto rounded-lg border bg-muted/60 p-4', className)}>
      {state === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Chargement de l'aperçu…
        </div>
      )}
      {state === 'error' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground">
          <AlertTriangle className="size-5 text-amber-500" />
          Impossible d'afficher le PDF ici. <a href={url} target="_blank" rel="noreferrer" className="text-primary hover:underline">L'ouvrir à part</a>
        </div>
      )}
      <div ref={box} />
    </div>
  )
}
