import { useState } from 'react'
import { CheckCircle2, Eye, EyeOff, FileText, KeyRound, Loader2, LogIn, ShieldCheck, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardBody } from '@/components/ui/card'
import { Field, Input, Textarea } from '@/components/ui/input'
import { Segmented } from '@/components/ui/switch'
import { authApi } from '@/lib/api'
import { cn } from '@/lib/utils'

type Mode = 'login' | 'signup'

export function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <Input {...props} type={show ? 'text' : 'password'} className="pr-9" />
      <button type="button" tabIndex={-1} onClick={() => setShow(!show)} aria-label={show ? 'Masquer' : 'Afficher'}
        className="absolute right-2 top-2 text-muted-foreground hover:text-foreground cursor-pointer">
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}

export function passwordHint(pw: string): { ok: boolean; text: string } {
  if (!pw) return { ok: false, text: 'Au moins 10 caractères. Une courte phrase est idéale.' }
  if (pw.length < 10) return { ok: false, text: `Encore ${10 - pw.length} caractère${10 - pw.length > 1 ? 's' : ''}.` }
  return { ok: true, text: 'Longueur suffisante.' }
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-full lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-primary p-12 text-primary-foreground lg:flex lg:flex-col">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-black/10 blur-2xl" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15"><FileText className="h-5 w-5" /></div>
          <div className="text-lg font-semibold">Générateur d'examens</div>
        </div>
        <div className="relative mt-auto max-w-md space-y-5">
          <h2 className="text-3xl font-semibold leading-tight">Des examens en LaTeX, plusieurs versions, solutions comprises.</h2>
          <ul className="space-y-3 text-sm opacity-90">
            {['Votre propre banque de questions, à partir de la banque de départ',
              'Des valeurs différentes pour chaque version, solutions calculées',
              'Partagez vos questions avec les collègues de votre choix'].map((t) => (
              <li key={t} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />{t}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="grid place-items-center p-6 sm:p-10">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  )
}

export function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [reason, setReason] = useState('')
  const [website, setWebsite] = useState('')  // honeypot, hidden from people
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      if (mode === 'login') {
        await authApi.login(email, password)
        onSignedIn()
      } else {
        const r = await authApi.signup({ name, email, password, reason, website })
        setSent(r.message); setPassword('')
      }
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  const hint = passwordHint(password)
  const reasonOk = reason.trim().length >= 15
  const canSubmit = mode === 'login' ? email && password : name.trim().length >= 2 && email && hint.ok && reasonOk

  return (
    <Shell>
      <div className="mb-8 lg:hidden flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-primary-foreground"><FileText className="h-5 w-5" /></div>
        <div className="text-lg font-semibold">Générateur d'examens</div>
      </div>
      <h1 className="text-2xl font-semibold tracking-tight">{mode === 'login' ? 'Connexion' : 'Demander un compte'}</h1>
      <p className="mt-1 mb-6 text-sm text-muted-foreground">
        {mode === 'login' ? 'Bon retour ! Entrez vos identifiants.' : 'Chaque demande est examinée par un administrateur avant l\'activation du compte.'}
      </p>
      <Segmented value={mode} onChange={(m) => { setMode(m); setError(''); setSent('') }}
        options={[{ value: 'login', label: 'Se connecter' }, { value: 'signup', label: 'Créer un compte' }]} />
      {sent ? (
        <Card className="mt-6"><CardBody className="flex gap-3">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
          <div className="space-y-2 text-sm"><p className="font-medium">Demande envoyée</p><p className="text-muted-foreground">{sent}</p>
            <Button size="sm" variant="outline" onClick={() => { setSent(''); setMode('login') }}>Retour à la connexion</Button></div>
        </CardBody></Card>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
          {mode === 'signup' && (
            <Field label="Nom complet"><Input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Prénom Nom" maxLength={120} /></Field>
          )}
          <Field label="Courriel"><Input autoFocus type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@cegep.qc.ca" maxLength={320} /></Field>
          <Field label="Mot de passe" hint={mode === 'signup' && <span className={cn(hint.ok && 'text-success')}>{hint.text}</span>}>
            <PasswordInput autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} maxLength={256} />
          </Field>
          {mode === 'signup' && (<>
            <Field label="Pourquoi demandez-vous un compte ?" hint={`${reason.trim().length}/15 caractères minimum · ex. « Enseignant en physique au cégep X, je prépare les examens de NYA. »`}>
              <Textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} placeholder="Votre établissement, vos cours, ce que vous voulez faire avec l'application…" />
            </Field>
            <input type="text" name="website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)}
              className="absolute -left-[9999px] h-0 w-0 opacity-0" aria-hidden="true" />
          </>)}
          {error && <div role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}
          <Button type="submit" size="lg" className="w-full" disabled={busy || !canSubmit}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === 'login' ? <LogIn className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
            {mode === 'login' ? 'Se connecter' : 'Envoyer la demande'}
          </Button>
          {mode === 'login' && <p className="text-center text-xs text-muted-foreground">Mot de passe oublié ? Un administrateur peut vous en donner un temporaire.</p>}
        </form>
      )}
    </Shell>
  )
}

export function AdminSetup({ onDone }: { onDone: () => void }) {
  const [token, setToken] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const hint = passwordHint(password)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError('')
    try { await authApi.setup({ token, name, email, password }); onDone() } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return (
    <Shell>
      <div className="mb-6 grid h-11 w-11 place-items-center rounded-xl bg-accent text-primary"><ShieldCheck className="h-6 w-6" /></div>
      <h1 className="text-2xl font-semibold tracking-tight">Créer le compte administrateur</h1>
      <p className="mt-1 mb-6 text-sm text-muted-foreground">
        Première utilisation. Le code de configuration est affiché dans le journal du serveur :
        <code className="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs">docker compose logs examgen</code>
      </p>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Code de configuration"><div className="relative"><KeyRound className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" /><Input autoFocus className="pl-9 font-mono" value={token} onChange={(e) => setToken(e.target.value)} /></div></Field>
        <Field label="Nom complet"><Input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Courriel"><Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Mot de passe" hint={<span className={cn(hint.ok && 'text-success')}>{hint.text}</span>}>
          <PasswordInput autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <div role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}
        <Button type="submit" size="lg" className="w-full" disabled={busy || !token || !email || !hint.ok}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Créer et se connecter
        </Button>
        <p className="text-xs text-muted-foreground">Ce compte garde la banque de questions déjà présente sur le serveur.</p>
      </form>
    </Shell>
  )
}

export function SignedOut({ needsSetup, refresh }: { needsSetup: boolean; refresh: () => void }) {
  return needsSetup ? <AdminSetup onDone={refresh} /> : <SignIn onSignedIn={refresh} />
}
