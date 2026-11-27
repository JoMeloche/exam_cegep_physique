import { NavLink, Route, Routes } from 'react-router-dom'
import { FileText, Library as LibraryIcon, LogOut, Moon, PlusCircle, Settings as SettingsIcon, Sun, Sparkles, Users } from 'lucide-react'
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
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  useEffect(() => { api.health().then((h) => setLatexOk(!!h.latex)).catch(() => setLatexOk(false)) }, [])
  useEffect(() => { api.config().then((c) => setNeedsSetup(!c.setup_done)).catch(() => setNeedsSetup(false)) }, [])

  if (needsSetup === null) return null
  if (needsSetup) return <Setup onDone={() => setNeedsSetup(false)} />

  return (
    <div className="flex h-full">
      <aside className="flex w-60 shrink-0 flex-col border-r bg-card/60 px-3 py-5 backdrop-blur">
        <div className="mb-8 flex items-center gap-2.5 px-2">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <FileText className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <div className="font-semibold">Examens</div>
            <div className="text-xs text-muted-foreground">générateur automatique</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
              <Icon className="h-4 w-4" />{label}
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink to="/admin"
              className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
              <Users className="h-4 w-4" />Utilisateurs
              {!!auth.pending && <span className="ml-auto rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold leading-none text-primary-foreground">{auth.pending}</span>}
            </NavLink>
          )}
        </nav>
        <div className="mt-auto space-y-3 px-2">
          {latexOk === false && (
            <div className="rounded-lg bg-warning/10 p-2.5 text-xs text-warning">LaTeX introuvable. Voir Paramètres.</div>
          )}
          <button onClick={() => setDark(!dark)} className="flex w-full items-center gap-2 rounded-lg px-1 py-1 text-sm text-muted-foreground hover:text-foreground cursor-pointer">
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />} {dark ? 'Mode clair' : 'Mode sombre'}
          </button>
          {auth.user && (
            <div className="flex items-center gap-2 border-t pt-3">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-xs font-semibold text-primary">
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
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Generate />} />
          <Route path="/library" element={<Library />} />
          <Route path="/question/new" element={<QuestionEditor />} />
          <Route path="/question/edit/*" element={<QuestionEditor />} />
          <Route path="/exports" element={<Exports />} />
          <Route path="/settings" element={<Settings />} />
          {isAdmin && <Route path="/admin" element={<Admin />} />}
        </Routes>
      </main>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="sticky top-0 z-10 flex items-end justify-between gap-4 border-b bg-background/80 px-8 py-5 backdrop-blur">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">{actions}</div>
    </div>
  )
}
