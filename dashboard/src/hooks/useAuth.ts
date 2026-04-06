/**
 * Auth context + hook voor JWT login/logout.
 * Token wordt opgeslagen in localStorage zodat je ingelogd blijft na pagina refresh.
 */

import { createContext, useContext, useState } from 'react'

export interface Gebruiker {
  id: string
  naam: string
  rol: 'admin' | 'aannemer' | 'vakman' | 'medewerker'
  bedrijf: string
}

interface AuthState {
  gebruiker: Gebruiker | null
  token: string | null
  laden: boolean
}

interface AuthContext extends AuthState {
  login: (email: string, wachtwoord: string) => Promise<void>
  logout: () => void
  isAdmin: boolean
}

// Sla token op in localStorage
const TOKEN_KEY = 'opti_intel_token'
const GEBRUIKER_KEY = 'opti_intel_gebruiker'

export function getOpgeslagenToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function authHeaders(): Record<string, string> {
  const token = getOpgeslagenToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// Singleton context — wordt in main.tsx gewrapped
export const AuthContext = createContext<AuthContext>({
  gebruiker: null,
  token: null,
  laden: true,
  login: async () => {},
  logout: () => {},
  isAdmin: false,
})

export function useAuth(): AuthContext {
  return useContext(AuthContext)
}

export function useAuthState() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [gebruiker, setGebruiker] = useState<Gebruiker | null>(() => {
    try {
      const raw = localStorage.getItem(GEBRUIKER_KEY)
      return raw ? JSON.parse(raw) : null
    } catch { return null }
  })
  const [laden, setLaden] = useState(false)

  async function login(email: string, wachtwoord: string) {
    setLaden(true)
    try {
      const form = new URLSearchParams()
      form.append('username', email)
      form.append('password', wachtwoord)

      const res = await fetch('/api/ingestion/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString(),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Inloggen mislukt' }))
        throw new Error(err.detail || 'Inloggen mislukt')
      }

      const data = await res.json()
      const nieuweGebruiker: Gebruiker = {
        id: data.id ?? '',
        naam: data.naam,
        rol: data.rol,
        bedrijf: data.bedrijf,
      }

      localStorage.setItem(TOKEN_KEY, data.access_token)
      localStorage.setItem(GEBRUIKER_KEY, JSON.stringify(nieuweGebruiker))
      setToken(data.access_token)
      setGebruiker(nieuweGebruiker)
    } finally {
      setLaden(false)
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(GEBRUIKER_KEY)
    setToken(null)
    setGebruiker(null)
  }

  return {
    token,
    gebruiker,
    laden,
    login,
    logout,
    isAdmin: gebruiker?.rol === 'admin' || gebruiker?.rol === 'aannemer',
  }
}
