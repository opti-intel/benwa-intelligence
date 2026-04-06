import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import optiIntelLogo from '../assets/opti-intel-logo.svg'

function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [wachtwoord, setWachtwoord] = useState('')
  const [fout, setFout] = useState('')
  const [laden, setLaden] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFout('')
    setLaden(true)
    try {
      await login(email, wachtwoord)
    } catch (err) {
      setFout(err instanceof Error ? err.message : 'Inloggen mislukt')
    } finally {
      setLaden(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
    }}>
      <div style={{
        background: 'var(--bg-white)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '40px 36px',
        width: '100%',
        maxWidth: 400,
        boxShadow: '0 4px 24px rgba(30,63,110,0.09)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--navy)',
            borderRadius: 12,
            padding: '10px 18px',
          }}>
            <img src={optiIntelLogo} alt="Opti Intel" style={{ width: 120 }} />
          </div>
        </div>

        <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>
          Inloggen
        </h2>
        <p style={{ fontSize: 14, color: 'var(--text-sub)', marginBottom: 24 }}>
          Log in om de bouwplanning te bekijken
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>E-mailadres</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="naam@bedrijf.nl"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Wachtwoord</label>
            <input
              type="password"
              value={wachtwoord}
              onChange={e => setWachtwoord(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {fout && (
            <div style={{
              background: 'var(--red-bg)',
              border: '1px solid #f0c0bb',
              borderRadius: 7,
              padding: '10px 14px',
              fontSize: 13,
              color: 'var(--red)',
              marginBottom: 16,
            }}>
              {fout}
            </div>
          )}

          <button
            type="submit"
            className="primary"
            disabled={laden}
            style={{ width: '100%', padding: '11px', fontSize: 15 }}
          >
            {laden ? 'Bezig...' : 'Inloggen'}
          </button>
        </form>

        <p style={{ marginTop: 20, fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
          Nog geen account? Vraag je beheerder om er één aan te maken.
        </p>
      </div>
    </div>
  )
}

export default Login
