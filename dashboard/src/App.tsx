import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Planning from './pages/Planning'
import Taken from './pages/Taken'
import Resources from './pages/Resources'

const navItems = [
  { to: '/', label: 'Overzicht', icon: '~' },
  { to: '/chat', label: 'Chat', icon: '>' },
  { to: '/planning', label: 'Planning', icon: '#' },
  { to: '/taken', label: 'Taken', icon: '*' },
  { to: '/resources', label: 'Resources', icon: '%' },
]

function App() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Benwa Intelligence</h1>
          <div className="subtitle">Bouwplanning</div>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => isActive ? 'active' : ''}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          v0.2.0
        </div>
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/planning" element={<Planning />} />
          <Route path="/taken" element={<Taken />} />
          <Route path="/resources" element={<Resources />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
