import { useState, useEffect } from "react"
import {
  Sun, Cloud, CloudRain, CloudSnow, CloudLightning,
  CheckCircle, Circle, Clock, Flame, Search, Menu, X,
  AlertTriangle, ChevronRight, Users, ClipboardList,
  TrendingUp, Calendar, Home, MessageSquare, FileText,
  LogOut, Settings
} from "lucide-react"

// ─── Types ───────────────────────────────────────────────────────────────────
const STATUS_CYCLE = { gepland: "bezig", bezig: "klaar", klaar: "gepland" }

const DISCIPLINE_BORDER = {
  Tegelwerk:    "border-orange-400",
  Stucwerk:     "border-yellow-400",
  Loodgieterij: "border-blue-400",
  Elektra:      "border-amber-400",
  Schilderwerk: "border-green-400",
  Metselwerk:   "border-red-400",
  Timmerwerk:   "border-orange-700",
}

function weatherInfo(code) {
  if (code === 0)   return { icon: <Sun className="w-4 h-4 text-yellow-400" />,    label: "Helder" }
  if (code <= 3)    return { icon: <Cloud className="w-4 h-4 text-gray-400" />,     label: "Bewolkt" }
  if (code <= 48)   return { icon: <Cloud className="w-4 h-4 text-gray-500" />,     label: "Mist" }
  if (code <= 67)   return { icon: <CloudRain className="w-4 h-4 text-blue-400" />, label: "Regen" }
  if (code <= 77)   return { icon: <CloudSnow className="w-4 h-4 text-blue-200" />, label: "Sneeuw" }
  if (code <= 82)   return { icon: <CloudRain className="w-4 h-4 text-blue-500" />, label: "Buien" }
  return              { icon: <CloudLightning className="w-4 h-4 text-purple-400" />, label: "Onweer" }
}

// ─── Mock data ────────────────────────────────────────────────────────────────
const MOCK_TASKS = [
  { id:"1", naam:"Tegelwerk badkamer",       beschrijving:"Vloertegels leggen",          status:"bezig",   toegewezen_aan:"Tegelzetters BV",  discipline:"Tegelwerk",    isUrgent:true,  startdatum:"2026-04-01", einddatum:"2026-04-05" },
  { id:"2", naam:"Stucwerk woonkamer",        beschrijving:"Wanden afstukken",             status:"gepland", toegewezen_aan:"Stukadoors NL",    discipline:"Stucwerk",                     startdatum:"2026-04-06", einddatum:"2026-04-08" },
  { id:"3", naam:"Elektra begane grond",      beschrijving:"Bekabeling trekken",           status:"klaar",   toegewezen_aan:"Elektro Plus",      discipline:"Elektra",                      startdatum:"2026-03-28", einddatum:"2026-04-01" },
  { id:"4", naam:"Leidingwerk keuken",        beschrijving:"Waterleiding aanleggen",        status:"bezig",   toegewezen_aan:"Loodgieter Pro",    discipline:"Loodgieterij",                 startdatum:"2026-04-02", einddatum:"2026-04-04" },
  { id:"5", naam:"Schilderwerk kozijnen",     beschrijving:"Buiten schilderen",             status:"gepland", toegewezen_aan:"Schilder & Zn",    discipline:"Schilderwerk",                 startdatum:"2026-04-10", einddatum:"2026-04-12" },
  { id:"6", naam:"Metselwerk gevel",          beschrijving:"Buitenmuur optrekken",          status:"gepland", toegewezen_aan:"Metsel Team",       discipline:"Metselwerk",   isUrgent:true,  startdatum:"2026-04-07", einddatum:"2026-04-09" },
  { id:"7", naam:"Timmerwerk vloer",          beschrijving:"Houten vloer plaatsen",         status:"gepland", toegewezen_aan:"Timmerman & Zn",   discipline:"Timmerwerk",                   startdatum:"2026-04-13", einddatum:"2026-04-15" },
  { id:"8", naam:"Droogdag betonvloer",       beschrijving:"Wachten op uitharden beton",    status:"gepland", toegewezen_aan:"",                                             type:"Droogdag" },
  { id:"9", naam:"Wachttijd gemeente",        beschrijving:"Wachten op inspecteur",         status:"gepland", toegewezen_aan:"",                                             type:"Wachttijd" },
]

const INIT_ALERTS = [
  { id:"1", message:"⚠️ AI Interventie: 1 planningsconflict gedetecteerd via chat (Tegelzetter geeft vertraging aan).", actionLabel:"Bekijk Oplossing" },
]

const NAV = [
  { icon: Home,         label: "Overzicht",  active: true  },
  { icon: MessageSquare,label: "Chat",       active: false },
  { icon: Calendar,     label: "Planning",   active: false },
  { icon: ClipboardList,label: "Taken",      active: false },
  { icon: FileText,     label: "PDF Invoer", active: false },
  { icon: Users,        label: "Gebruikers", active: false },
  { icon: Settings,     label: "Resources",  active: false },
]

// ─── Sub-components ───────────────────────────────────────────────────────────
function StatusIcon({ status, onClick }) {
  return (
    <button onClick={onClick} className="flex-shrink-0 mt-0.5" title="Klik om status te wijzigen">
      {status === "klaar"  && <CheckCircle className="w-5 h-5 text-green-500" />}
      {status === "bezig"  && (
        <div className="w-5 h-5 rounded-full border-2 border-blue-500 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-blue-500" />
        </div>
      )}
      {status === "gepland" && <Circle className="w-5 h-5 text-gray-300 hover:text-gray-400 transition-colors" />}
    </button>
  )
}

function KPICard({ label, value, sub, barColor, percent, Icon, iconBg, iconColor, loading }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-2 min-w-0">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide truncate">{label}</span>
        <div className={`w-7 h-7 rounded-lg ${iconBg} flex items-center justify-center flex-shrink-0 ml-2`}>
          <Icon className={`w-4 h-4 ${iconColor}`} />
        </div>
      </div>
      <div className="text-2xl font-bold text-gray-800">{loading ? "—" : value}</div>
      <div className="text-xs text-gray-400">{sub}</div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full transition-all duration-700`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function OptiIntelDashboard() {
  const [tasks,      setTasks]      = useState([])
  const [loading,    setLoading]    = useState(true)
  const [weather,    setWeather]    = useState(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [aiAlerts,   setAiAlerts]   = useState(INIT_ALERTS)
  const [menuOpen,   setMenuOpen]   = useState(false)

  // Fetch taken van backend, fallback op mock-data
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/ingestion/tasks")
        if (!res.ok) throw new Error()
        const data = await res.json()
        setTasks(data.length ? data : MOCK_TASKS)
      } catch {
        setTasks(MOCK_TASKS)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Fetch weer via Open-Meteo (Veldhoven)
  useEffect(() => {
    fetch("https://api.open-meteo.com/v1/forecast?latitude=51.4167&longitude=5.4167&current_weather=true")
      .then(r => r.json())
      .then(d => setWeather({
        temp: Math.round(d.current_weather.temperature),
        code: d.current_weather.weathercode,
        wind: Math.round(d.current_weather.windspeed),
      }))
      .catch(() => {})
  }, [])

  // Status wissel
  function cycleStatus(id) {
    setTasks(prev => prev.map(t =>
      t.id === id ? { ...t, status: STATUS_CYCLE[t.status] } : t
    ))
  }

  // Splits taken
  const activeTasks  = tasks.filter(t => t.type !== "Droogdag" && t.type !== "Wachttijd")
  const waitingTasks = tasks.filter(t => t.type === "Droogdag"  || t.type === "Wachttijd")

  const total       = activeTasks.length || 1
  const doneCount   = activeTasks.filter(t => t.status === "klaar").length
  const busyCount   = activeTasks.filter(t => t.status === "bezig").length
  const geplandCount= activeTasks.filter(t => t.status === "gepland").length

  // Zoekfilter
  const filtered = activeTasks.filter(t =>
    !searchTerm ||
    t.naam.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (t.toegewezen_aan || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
    (t.beschrijving   || "").toLowerCase().includes(searchTerm.toLowerCase())
  )

  const wInfo = weather ? weatherInfo(weather.code) : null

  return (
    <div className="flex h-screen bg-gray-50 font-sans overflow-hidden">

      {/* Sidebar overlay (mobiel) */}
      {menuOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-20 lg:hidden" onClick={() => setMenuOpen(false)} />
      )}

      {/* ── Sidebar ── */}
      <aside className={`
        fixed lg:static top-0 left-0 h-full z-30 w-56 bg-slate-800 flex flex-col flex-shrink-0
        transition-transform duration-200
        ${menuOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
      `}>
        {/* Logo */}
        <div className="px-5 py-4 border-b border-slate-700">
          <div className="text-white font-bold text-base">Opti Intel</div>
          <div className="text-slate-400 text-xs mt-0.5">Bouwplanning Platform</div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ icon: Icon, label, active }) => (
            <button key={label} className={`
              w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors text-left
              ${active ? "bg-teal-600 text-white" : "text-slate-400 hover:bg-slate-700 hover:text-white"}
            `}>
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-slate-700">
          <div className="text-white text-sm font-medium truncate">Beheerder</div>
          <div className="text-slate-400 text-xs truncate">admin@optiintel.nl</div>
          <button className="mt-2 flex items-center gap-1.5 text-slate-400 hover:text-white text-xs transition-colors">
            <LogOut className="w-3 h-3" /> Uitloggen
          </button>
        </div>
        <div className="px-3 pb-3 text-slate-600 text-xs">v0.3.0</div>
      </aside>

      {/* ── Hoofdkolom ── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">

        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 flex-shrink-0">
          {/* Hamburger */}
          <button className="lg:hidden text-gray-500 hover:text-gray-700 p-1" onClick={() => setMenuOpen(true)}>
            <Menu className="w-5 h-5" />
          </button>

          <h1 className="text-sm font-semibold text-gray-800 flex-1">Overzicht</h1>

          {/* Zoekbalk (desktop) */}
          <div className="relative hidden sm:block">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              placeholder="Zoek taak of bedrijf…"
              className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-teal-500 w-48 lg:w-60"
            />
          </div>

          {/* Weer-widget */}
          {wInfo && weather && (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg">
              {wInfo.icon}
              <span className="text-sm font-semibold text-gray-700">{weather.temp}°</span>
              <span className="text-xs text-gray-400 hidden md:inline">{wInfo.label}</span>
              <span className="text-xs text-gray-300 hidden lg:inline">· {weather.wind} km/u</span>
            </div>
          )}
        </header>

        {/* Zoekbalk (mobiel) */}
        <div className="sm:hidden px-4 py-2 bg-white border-b border-gray-100">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              placeholder="Zoek taak of bedrijf…"
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
        </div>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-4 space-y-4">

          {/* AI Alerts */}
          {aiAlerts.map(alert => (
            <div key={alert.id} className="flex items-start gap-3 bg-amber-50 border-l-4 border-amber-500 rounded-r-xl px-4 py-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800 flex-1 leading-relaxed">{alert.message}</p>
              <button className="flex items-center gap-1 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold rounded-lg transition-colors flex-shrink-0">
                {alert.actionLabel} <ChevronRight className="w-3 h-3" />
              </button>
              <button onClick={() => setAiAlerts(a => a.filter(x => x.id !== alert.id))} className="text-amber-300 hover:text-amber-500 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}

          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KPICard label="Totaal taken"   value={activeTasks.length} sub="actieve taken"      barColor="bg-blue-500"   percent={100}                              Icon={ClipboardList} iconBg="bg-blue-50"   iconColor="text-blue-600"  loading={loading} />
            <KPICard label="Gereed"         value={doneCount}          sub={`${Math.round(doneCount/total*100)}% voltooid`}   barColor="bg-green-500"  percent={Math.round(doneCount/total*100)}   Icon={CheckCircle}   iconBg="bg-green-50"  iconColor="text-green-600" loading={loading} />
            <KPICard label="In uitvoering"  value={busyCount}          sub={`${Math.round(busyCount/total*100)}% van taken`}   barColor="bg-orange-400" percent={Math.round(busyCount/total*100)}   Icon={TrendingUp}    iconBg="bg-orange-50" iconColor="text-orange-500" loading={loading} />
            <KPICard label="Ingepland"      value={geplandCount}       sub="nog te starten"    barColor="bg-slate-400"  percent={Math.round(geplandCount/total*100)} Icon={Calendar}      iconBg="bg-slate-50"  iconColor="text-slate-500"  loading={loading} />
          </div>

          {/* Takentabel */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700">Actieve taken</h2>
              <span className="text-xs text-gray-400">{filtered.length} resultaten</span>
            </div>

            {loading ? (
              <div className="py-10 text-center text-gray-400 text-sm animate-pulse">Laden…</div>
            ) : filtered.length === 0 ? (
              <div className="py-10 text-center text-gray-400 text-sm">Geen taken gevonden voor "{searchTerm}"</div>
            ) : (
              <div className="divide-y divide-gray-50">
                {filtered.map(task => (
                  <div
                    key={task.id}
                    className={`flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition-colors border-l-4 ${DISCIPLINE_BORDER[task.discipline] || "border-gray-200"}`}
                  >
                    <StatusIcon status={task.status} onClick={() => cycleStatus(task.id)} />

                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-sm font-medium ${task.status === "klaar" ? "line-through text-gray-400" : "text-gray-800"}`}>
                          {task.naam}
                        </span>
                        {task.isUrgent && (
                          <span className="flex items-center gap-0.5 text-xs text-red-500 font-semibold">
                            <Flame className="w-3.5 h-3.5" /> Urgent
                          </span>
                        )}
                        {task.discipline && (
                          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-md">
                            {task.discipline}
                          </span>
                        )}
                      </div>
                      {task.beschrijving && (
                        <p className="text-xs text-gray-400 mt-0.5 truncate">{task.beschrijving}</p>
                      )}
                      <div className="flex flex-wrap gap-3 mt-1">
                        {task.toegewezen_aan && (
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Users className="w-3 h-3" /> {task.toegewezen_aan}
                          </span>
                        )}
                        {task.startdatum && (
                          <span className="text-xs text-gray-400">
                            {task.startdatum} → {task.einddatum}
                          </span>
                        )}
                      </div>
                    </div>

                    <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-semibold mt-0.5 ${
                      task.status === "klaar"   ? "bg-green-100 text-green-700" :
                      task.status === "bezig"   ? "bg-blue-100  text-blue-700"  :
                                                  "bg-gray-100  text-gray-500"
                    }`}>
                      {task.status === "klaar" ? "Gereed" : task.status === "bezig" ? "Bezig" : "Gepland"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Wacht- & droogtijden */}
          {waitingTasks.length > 0 && (
            <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
                <Clock className="w-4 h-4 text-gray-400" />
                <h2 className="text-sm font-medium text-gray-500">Wacht- &amp; droogtijden</h2>
                <span className="ml-auto text-xs text-gray-400">{waitingTasks.length} items</span>
              </div>
              <div className="divide-y divide-gray-100">
                {waitingTasks.map(task => (
                  <div key={task.id} className="flex items-center gap-3 px-4 py-3">
                    <Clock className="w-4 h-4 text-gray-300 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-gray-500">{task.naam}</span>
                      {task.beschrijving && (
                        <p className="text-xs text-gray-400 mt-0.5">{task.beschrijving}</p>
                      )}
                    </div>
                    <span className="text-xs bg-gray-200 text-gray-500 px-2 py-0.5 rounded-full flex-shrink-0">
                      {task.type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  )
}
