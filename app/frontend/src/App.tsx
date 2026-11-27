import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { FileText, Library as LibraryIcon, LogOut, Menu, Moon, PlusCircle, Settings as SettingsIcon, Sun, Sparkles, Users, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import Generate from '@/pages/Generate'
import Library from '@/pages/Library'
import QuestionEditor from '@/pages/QuestionEditor'
import Settings from '@/pages/Settings'
import Exports from '@/pages/Exports'
import Setup from '@/pages/Setup'
import Admin from '@/pages/Admin'
import { useAuth } from '@/lib/auth'

const nav = [
  { to: '/', label: 'Générer', icon: Sparkles, end: true },
  { to: '/library', label: 'Bibliothèque', icon: LibraryIcon },
  { to: '/question/new', label: 'Importer', icon: PlusCircle },
  { to: '/exports', label: 'Examens produits', icon: FileText },
  { to: '/settings', label: 'Paramètres', icon: SettingsIcon },
]

export default function App() {
  const { state: auth, logout } = useAuth()
  const isAdmin = auth.user?.role === 'admin'
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const [latexOk, setLatexOk] = useState<boolean | null>(null)
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)
  const [version, setVersion] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  useEffect(() => { setMenuOpen(false) }, [location.pathname])
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])
  useEffect(() => {
    const page = nav.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)))?.label
      ?? (location.pathname.startsWith('/question/edit') ? 'Modifier une question' : location.pathname === '/admin' ? 'Utilisateurs' : '')
    document.title = page ? `${page} · Générateur d'examens` : "Générateur d'examens"
  }, [location.pathname])
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  useEffect(() => { api.health().then((h) => { setLatexOk(!!h.latex); setVersion(h.version) }).catch(() => setLatexOk(false)) }, [])
  useEffect(() => { api.config().then((c) => setNeedsSetup(!c.setup_done)).catch(() => setNeedsSetup(false)) }, [])

  if (needsSetup === null) return null
  if (needsSetup) return <Setup onDone={() => setNeedsSetup(false)} />

  const sidebar = (
    <>
      <div className="mb-8 flex items-center gap-2.5 px-2">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <FileText className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <div className="font-semibold">Examens</div>
          <div className="text-xs text-muted-foreground">générateur automatique</div>
        </div>
      </div>
      <nav className="flex flex-col gap-1" aria-label="Navigation principale">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end}
            className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
            <Icon className="h-4 w-4" aria-hidden />{label}
          </NavLink>
        ))}
        {isAdmin && (
          <NavLink to="/admin"
            className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
            <Users className="h-4 w-4" aria-hidden />Utilisateurs
            {!!auth.pending && <span className="ml-auto rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold leading-none text-primary-foreground" aria-label={`${auth.pending} demande(s) en attente`}>{auth.pending}</span>}
          </NavLink>
        )}
      </nav>
      <div className="mt-auto space-y-3 px-2 pt-6">
        {latexOk === false && (
          <NavLink to="/settings" className="block rounded-lg bg-warning/10 p-2.5 text-xs text-warning hover:bg-warning/15">LaTeX introuvable : les PDF ne peuvent pas être produits. Voir Paramètres.</NavLink>
        )}
        <button onClick={() => setDark(!dark)} className="flex w-full items-center gap-2 rounded-lg px-1 py-1 text-sm text-muted-foreground hover:text-foreground cursor-pointer">
          {dark ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />} {dark ? 'Mode clair' : 'Mode sombre'}
        </button>
        {auth.user && (
          <div className="flex items-center gap-2 border-t pt-3">
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-xs font-semibold text-primary" aria-hidden>
              {auth.user.name.split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('')}
            </div>
            <div className="min-w-0 flex-1 leading-tight">
              <div className="truncate text-sm font-medium">{auth.user.name}</div>
              <div className="truncate text-xs text-muted-foreground">{auth.user.email}</div>
            </div>
            <button onClick={logout} title="Se déconnecter" aria-label="Se déconnecter" className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
        {version && <div className="text-[11px] text-muted-foreground/70">Version {version}</div>}
      </div>
    </>
  )

  return (
    <div className="flex h-full flex-col lg:flex-row">
      <aside className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r bg-card/60 px-3 py-5 backdrop-blur lg:flex">{sidebar}</aside>
      {/* Phones and tablets: a top bar and a slide-in menu instead of the sidebar. */}
      <header className="flex shrink-0 items-center gap-3 border-b bg-card/80 px-4 py-2.5 backdrop-blur lg:hidden">
        <button onClick={() => setMenuOpen(true)} aria-label="Ouvrir le menu" aria-expanded={menuOpen}
          className="-ml-1.5 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer">
          <Menu className="h-5 w-5" />
        </button>
        <div className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-primary-foreground"><FileText className="h-4 w-4" /></div>
        <span className="font-semibold">Examens</span>
        {!!auth.pending && isAdmin && <NavLink to="/admin" className="ml-auto rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground">{auth.pending} en attente</NavLink>}
      </header>
      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMenuOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col overflow-y-auto border-r bg-card px-3 py-5 shadow-xl">
            <button onClick={() => setMenuOpen(false)} aria-label="Fermer le menu"
              className="absolute right-3 top-4 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer">
              <X className="h-5 w-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}
      <main className="min-h-0 min-w-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Generate />} />
          <Route path="/library" element={<Library />} />
          <Route path="/question/new" element={<QuestionEditor />} />
          <Route path="/question/edit/*" element={<QuestionEditor />} />
          <Route path="/exports" element={<Exports />} />
          <Route path="/settings" element={<Settings />} />
          {isAdmin && <Route path="/admin" element={<Admin />} />}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  )
}

function NotFound() {
  return (
    <div className="grid min-h-[60vh] place-items-center p-8 text-center">
      <div>
        <h1 className="text-xl font-semibold">Page introuvable</h1>
        <p className="mt-2 text-sm text-muted-foreground">Cette adresse ne correspond à aucun écran.</p>
        <Link to="/" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">Retour à Générer</Link>
      </div>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="sticky top-0 z-10 flex flex-wrap items-end justify-between gap-x-4 gap-y-3 border-b bg-background/80 px-4 py-4 backdrop-blur sm:px-6 lg:px-8 lg:py-5">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
