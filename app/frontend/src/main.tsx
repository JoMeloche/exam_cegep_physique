import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import App from './App'
import { AuthProvider } from './lib/auth'
import { SignedOut } from './pages/Auth'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <AuthProvider signedOut={(st, refresh) => <SignedOut needsSetup={!!st.needs_setup} refresh={refresh} />}>
        <App />
      </AuthProvider>
      <Toaster richColors position="bottom-right" />
    </HashRouter>
  </StrictMode>,
)
