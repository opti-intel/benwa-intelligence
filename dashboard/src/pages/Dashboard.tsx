import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { type Taak, type TaakStatus } from '../hooks/useApi'

interface ActivityItem {
  text: string
  time: string
  type: 'success' | 'info' | 'warning' | 'error'
}

const recentActivity: ActivityItem[] = [
  { text: 'Funderingswerk afgerond en goedgekeurd', time: '2 uur geleden', type: 'success' },
  { text: 'Ruwbouw muren gestart — Pieter Bakker toegewezen', time: '5 uur geleden', type: 'info' },
  { text: 'Hijskraan #1 ingepland voor dakconstructie', time: 'Gisteren', type: 'info' },
  { text: 'Vertraging gemeld bij levering dakspanten', time: 'Gisteren', type: 'warning' },
  { text: 'Planning geoptimaliseerd door solver-engine', time: '2 dagen geleden', type: 'success' },
]

const quickLinks = [
  { to: '/chat', icon: '>', label: 'Chat', desc: 'Stel vragen aan de AI' },
  { to: '/planning', icon: '#', label: 'Planning', desc: 'Bekijk de Gantt-planning' },
  { to: '/taken', icon: '*', label: 'Taken', desc: 'Beheer projecttaken' },
  { to: '/resources', icon: '%', label: 'Resources', desc: 'Medewerkers & apparatuur' },
]

function loadTaken(): Taak[] {
  try {
    const stored = localStorage.getItem('benwa-taken')
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function formatDate(d: string) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('nl-NL', { weekday: 'short', day: 'numeric', month: 'short' })
}

function Dashboard() {
  const [taken, setTaken] = useState<Taak[]>(loadTaken)

  // Refresh taken from localStorage periodically
  useEffect(() => {
    const refresh = () => setTaken(loadTaken())
    const interval = setInterval(refresh, 5000)
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', refresh)
    return () => {
      clearInterval(interval)
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  const totalTaken = taken.length
  const klaarCount = taken.filter(t => t.status === 'klaar').length
  const voortgang = totalTaken > 0 ? Math.round((klaarCount / totalTaken) * 100) : 0

  let resourceCount = 0
  try {
    const stored = localStorage.getItem('benwa-resources')
    if (stored) {
      const res = JSON.parse(stored)
      resourceCount = Array.isArray(res) ? res.filter((r: { beschikbaarheid: boolean }) => r.beschikbaarheid).length : 0
    }
  } catch { /* ignore */ }

  // Count "risks" — tasks that are gepland but should have started
  const risicoCount = taken.filter(t => t.status === 'gepland' && t.startdatum && new Date(t.startdatum) < new Date()).length

  // Upcoming tasks — planned or in-progress within the next 7 days
  const now = new Date()
  const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  const upcoming = taken
    .filter(t => {
      if (t.status === 'klaar') return false
      if (!t.startdatum) return t.status === 'bezig' // show "bezig" tasks without date
      const start = new Date(t.startdatum)
      return start <= weekFromNow
    })
    .sort((a, b) => {
      // "bezig" first, then by start date
      if (a.status === 'bezig' && b.status !== 'bezig') return -1
      if (b.status === 'bezig' && a.status !== 'bezig') return 1
      return (a.startdatum || '').localeCompare(b.startdatum || '')
    })
    .slice(0, 8)

  const statusLabels: Record<TaakStatus, string> = {
    gepland: 'Gepland',
    bezig: 'Bezig',
    klaar: 'Klaar',
  }

  const statusBadgeClass: Record<TaakStatus, string> = {
    gepland: 'pending',
    bezig: 'info',
    klaar: 'success',
  }

  return (
    <div>
      <div className="page-header">
        <h2>Overzicht</h2>
        <p>Projectvoortgang en planning</p>
      </div>

      {/* Metric cards */}
      <div className="grid-4 mb-24">
        <div className="card">
          <div className="metric-value">{totalTaken}</div>
          <div className="metric-label">Aantal Taken</div>
        </div>
        <div className="card">
          <div className="metric-value" style={{ color: 'var(--accent-green)' }}>{voortgang}%</div>
          <div className="metric-label">Voortgang</div>
        </div>
        <div className="card">
          <div className="metric-value">{resourceCount}</div>
          <div className="metric-label">Actieve Resources</div>
        </div>
        <div className="card">
          <div className="metric-value" style={{ color: risicoCount > 0 ? 'var(--accent-red)' : undefined }}>{risicoCount}</div>
          <div className="metric-label">Risico's</div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="card mb-24">
        <div className="card-header">
          <h3>Totale Voortgang</h3>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-green)' }}>{voortgang}%</span>
        </div>
        <div className="voortgang-bar">
          <div className="voortgang-bar-fill" style={{ width: `${voortgang}%` }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          {(['klaar', 'bezig', 'gepland'] as TaakStatus[]).map(s => (
            <span key={s}>{s.charAt(0).toUpperCase() + s.slice(1)}: {taken.filter(t => t.status === s).length}</span>
          ))}
        </div>
      </div>

      {/* Upcoming tasks */}
      <div className="card mb-24">
        <div className="card-header">
          <h3>Komende Taken</h3>
          <Link to="/taken" style={{ fontSize: 13, color: 'var(--accent-blue)', textDecoration: 'none' }}>Alle taken →</Link>
        </div>
        {upcoming.length === 0 ? (
          <div style={{ padding: '16px 0', color: 'var(--text-muted)', fontSize: 13 }}>
            Geen geplande taken deze week. Ga naar <Link to="/chat" style={{ color: 'var(--accent-blue)' }}>Chat</Link> om taken aan te maken.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {upcoming.map(taak => (
              <Link key={taak.id} to="/taken" style={{ textDecoration: 'none', color: 'inherit' }}>
                <div className="upcoming-taak">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                    <span className={`status-badge ${statusBadgeClass[taak.status]}`} style={{ flexShrink: 0 }}>
                      {statusLabels[taak.status]}
                    </span>
                    <span style={{ fontWeight: 500, fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {taak.naam}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: 'var(--text-muted)', flexShrink: 0 }}>
                    {taak.startdatum && <span>{formatDate(taak.startdatum)}</span>}
                    {taak.toegewezen_aan && <span>{taak.toegewezen_aan}</span>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Quick links */}
      <div className="quick-links mb-24">
        {quickLinks.map(link => (
          <Link key={link.to} to={link.to} className="quick-link-card">
            <div className="quick-link-icon">{link.icon}</div>
            <div className="quick-link-label">{link.label}</div>
            <div className="quick-link-desc">{link.desc}</div>
          </Link>
        ))}
      </div>

      {/* Recent activity */}
      <div className="card">
        <div className="card-header">
          <h3>Recente Activiteit</h3>
        </div>
        {recentActivity.map((item, i) => (
          <div key={i} className="activity-item">
            <div
              className="activity-dot"
              style={{
                backgroundColor:
                  item.type === 'success' ? 'var(--accent-green)' :
                  item.type === 'warning' ? 'var(--accent-yellow)' :
                  item.type === 'error' ? 'var(--accent-red)' :
                  'var(--accent-blue)',
              }}
            />
            <div className="activity-content">
              <div className="activity-text">{item.text}</div>
              <div className="activity-time">{item.time}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default Dashboard
