import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { Menu, X, LayoutDashboard, MessageCircle, Calendar, CheckSquare, FileText, Users, Database, LogOut } from 'lucide-react'
import optiIntelLogo from './assets/opti-intel-logo.svg'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Planning from './pages/Planning'
import Taken from './pages/Taken'
import Resources from './pages/Resources'
import PdfInvoer from './pages/PdfInvoer'
import Gebruikers from './pages/Gebruikers'
import Login from './pages/Login'
import { AuthContext, useAuthState } from './hooks/useAuth'

const navItems = [
  { to: '/',           label: 'Overzicht',   icon: LayoutDashboard, adminOnly: false },
  { to: '/chat',       label: 'Chat',        icon: MessageCircle,   adminOnly: false },
  { to: '/planning',   label: 'Planning',    icon: Calendar,        adminOnly: false },
  { to: '/taken',      label: 'Taken',       icon: CheckSquare,     adminOnly: false },
  { to: '/pdf',        label: 'PDF Invoer',  icon: FileText,        adminOnly: true  },
  { to: '/gebruikers', label: 'Gebruikers',  icon: Users,           adminOnly: true  },
  { to: '/resources',  label: 'Resources',   icon: Database,        adminOnly: true  },
]

function rolLabel(rol: string) {
  if (rol === 'admin') return 'Beheerder'
  if (rol === 'aannemer') return 'Aannemer'
  if (rol === 'vakman') return 'Vakman'
  return 'Medewerker'
}

function App() {
  const auth = useAuthState()
  const [menuOpen, setMenuOpen] = useState(false)

  // Sluit menu bij route-wisseling
  const location = useLocation()
  useEffect(() => { setMenuOpen(false) }, [location.pathname])

  // Sluit menu bij klik buiten sidebar op mobiel
  useEffect(() => {
    if (!menuOpen) return
    function handleClick(e: MouseEvent) {
      const sidebar = document.getElementById('mobile-sidebar')
      if (sidebar && !sidebar.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  // Niet ingelogd → login pagina
  if (!auth.gebruiker) {
    return (
      <AuthContext.Provider value={auth}>
        <Login />
      </AuthContext.Provider>
    )
  }

  const zichtbareItems = navItems.filter(item => !item.adminOnly || auth.isAdmin)

  const sidebarInhoud = (
    <>
      <div className="sidebar-header">
        <img
          src={optiIntelLogo}
          alt="Opti Intel"
          style={{ width: '100%', maxWidth: 160, display: 'block', margin: '0 auto 4px' }}
        />
      </div>

      <nav className="sidebar-nav">
        {zichtbareItems.map(item => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => isActive ? 'active' : ''}
              onClick={() => setMenuOpen(false)}
            >
              <span className="nav-icon"><Icon size={16} /></span>
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      {/* Ingelogde gebruiker + uitlog */}
      <div style={{ padding: '12px 14px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.9)', marginBottom: 2 }}>
          {auth.gebruiker.naam}
        </div>
        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginBottom: 8 }}>
          {rolLabel(auth.gebruiker.rol)}
          {auth.gebruiker.bedrijf ? ` · ${auth.gebruiker.bedrijf}` : ''}
        </div>
        <button
          onClick={auth.logout}
          style={{
            background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 6,
            color: 'rgba(255,255,255,0.7)', fontSize: 12, padding: '5px 10px',
            cursor: 'pointer', width: '100%', textAlign: 'left',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <LogOut size={13} />
          Uitloggen
        </button>
      </div>

      <div className="sidebar-footer">v0.3.1</div>
    </>
  )

  return (
    <AuthContext.Provider value={auth}>
      <div className="app-layout">

        {/* ── Desktop sidebar (altijd zichtbaar ≥ 768px) ─────────────── */}
        <aside className="sidebar sidebar-desktop">
          {sidebarInhoud}
        </aside>

        {/* ── Mobiele overlay + sidebar (alleen zichtbaar < 768px) ────── */}
        {menuOpen && (
          <div
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
              zIndex: 49, display: 'none',
            }}
            className="mobile-overlay"
            onClick={() => setMenuOpen(false)}
          />
        )}

        <aside
          id="mobile-sidebar"
          className={`sidebar sidebar-mobile ${menuOpen ? 'sidebar-mobile--open' : ''}`}
        >
          {/* Sluitknop bovenin op mobiel */}
          <button
            onClick={() => setMenuOpen(false)}
            style={{
              position: 'absolute', top: 12, right: 12,
              background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: 6,
              color: 'rgba(255,255,255,0.7)', cursor: 'pointer',
              width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <X size={16} />
          </button>
          {sidebarInhoud}
        </aside>

        {/* ── Hoofdcontent ─────────────────────────────────────────────── */}
        <div className="main-wrapper">

          {/* Mobiele topbar (alleen zichtbaar < 768px) */}
          <header className="mobile-header">
            <button
              onClick={() => setMenuOpen(v => !v)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text)', padding: 4, display: 'flex', alignItems: 'center',
                flexShrink: 0,
              }}
            >
              <Menu size={26} />
            </button>
            <img
              src={optiIntelLogo}
              alt="Opti Intel"
              style={{ flex: 1, height: 52, width: '100%', objectFit: 'contain', padding: '0 12px' }}
            />
            <div style={{ width: 34, flexShrink: 0 }} />
          </header>

          <main className="main-content">
            <Routes>
              <Route path="/"           element={<Dashboard />} />
              <Route path="/chat"       element={<Chat />} />
              <Route path="/planning"   element={<Planning />} />
              <Route path="/taken"      element={<Taken />} />
              <Route path="/pdf"        element={auth.isAdmin ? <PdfInvoer /> : <Navigate to="/" />} />
              <Route path="/gebruikers" element={auth.isAdmin ? <Gebruikers /> : <Navigate to="/" />} />
              <Route path="/resources"  element={auth.isAdmin ? <Resources /> : <Navigate to="/" />} />
            </Routes>
          </main>
        </div>

      </div>
    </AuthContext.Provider>
  )
}

export default App
