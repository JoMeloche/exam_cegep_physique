import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, type AuthState } from '@/lib/api'

interface AuthCtx { state: AuthState; refresh: () => Promise<void>; logout: () => Promise<void> }
const Ctx = createContext<AuthCtx | null>(null)

export function useAuth(): AuthCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth outside AuthProvider')
  return c
}

/** Loads the account state once, re-checks it when the server says the session ended. */
export function AuthProvider({ children, signedOut }: { children: React.ReactNode; signedOut: (state: AuthState, refresh: () => Promise<void>) => React.ReactNode }) {
  const [state, setState] = useState<AuthState | null>(null)
  const [failed, setFailed] = useState(false)
  const refresh = useCallback(async () => {
    try { setState(await authApi.state()); setFailed(false) } catch { setFailed(true) }
  }, [])
  const logout = useCallback(async () => {
    try { await authApi.logout() } finally { await refresh() }
  }, [refresh])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const on = () => { refresh() }
    window.addEventListener('examgen:signed-out', on)
    return () => window.removeEventListener('examgen:signed-out', on)
  }, [refresh])
  useEffect(() => {
    if (!state?.user?.role || state.user.role !== 'admin') return
    const t = setInterval(refresh, 60_000)  // pending-request badge stays fresh
    return () => clearInterval(t)
  }, [state?.user?.role, refresh])

  if (failed) return <div className="grid h-full place-items-center text-sm text-muted-foreground">Serveur injoignable. <button className="ml-2 underline" onClick={refresh}>Réessayer</button></div>
  if (!state) return null
  if (state.enabled && !state.user) return <>{signedOut(state, refresh)}</>
  return <Ctx.Provider value={{ state, refresh, logout }}>{children}</Ctx.Provider>
}
