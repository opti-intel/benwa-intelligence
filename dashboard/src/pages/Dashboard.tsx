import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Sun, Cloud, CloudRain, CloudSnow, CloudLightning,
  Circle, CheckCircle, Flame, AlertTriangle, ChevronRight,
  Clock, Search, X,
} from 'lucide-react'
import { type Taak, takenApi } from '../hooks/useApi'

// ─── Uitgebreid taaktype (extra velden voor productiefase) ────────────────────
interface ExtTaak extends Taak {
  isUrgent?: boolean
  discipline?: string
  type?: string        // 'Droogdag' | 'Wachttijd' | undefined
}

// ─── Discipline → kleur linkerrand ───────────────────────────────────────────
const DISC_KLEUR: Record<string, string> = {
  Tegelwerk:    '#f97316',
  Stucwerk:     '#eab308',
  Loodgieterij: '#3b82f6',
  Elektra:      '#f59e0b',
  Schilderwerk: '#22c55e',
  Metselwerk:   '#ef4444',
  Timmerwerk:   '#a16207',
}
function discKleur(d?: string) { return DISC_KLEUR[d ?? ''] ?? 'var(--border)' }

// ─── Weericoon op basis van WMO weathercode ──────────────────────────────────
function WeerIconen({ code, size = 16 }: { code: number; size?: number }) {
  const s = { width: size, height: size }
  if (code === 0)  return <Sun style={{ ...s, color: '#facc15' }} />
  if (code <= 3)   return <Cloud style={{ ...s, color: '#94a3b8' }} />
  if (code <= 48)  return <Cloud style={{ ...s, color: '#64748b' }} />
  if (code <= 67)  return <CloudRain style={{ ...s, color: '#60a5fa' }} />
  if (code <= 77)  return <CloudSnow style={{ ...s, color: '#bfdbfe' }} />
  if (code <= 82)  return <CloudRain style={{ ...s, color: '#3b82f6' }} />
  return               <CloudLightning style={{ ...s, color: '#a855f7' }} />
}
function weerLabel(code: number) {
  if (code === 0)  return 'Helder'
  if (code <= 3)   return 'Bewolkt'
  if (code <= 48)  return 'Mist'
  if (code <= 67)  return 'Regen'
  if (code <= 77)  return 'Sneeuw'
  if (code <= 82)  return 'Buien'
  return 'Onweer'
}

// ─── Status-icoon (klikbaar) ─────────────────────────────────────────────────
function StatusIcoon({ status, onClick }: { status: string; onClick: () => void }) {
  const base: React.CSSProperties = {
    cursor: 'pointer', flexShrink: 0, marginTop: 2, background: 'none', border: 'none', padding: 0,
  }
  if (status === 'klaar') return (
    <button style={base} onClick={onClick} title="Klik om status te wijzigen">
      <CheckCircle size={18} style={{ color: '#22c55e' }} />
    </button>
  )
  if (status === 'bezig') return (
    <button style={base} onClick={onClick} title="Klik om status te wijzigen">
      <div style={{
        width: 18, height: 18, borderRadius: '50%', border: '2px solid #3b82f6',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#3b82f6' }} />
      </div>
    </button>
  )
  return (
    <button style={base} onClick={onClick} title="Klik om status te wijzigen">
      <Circle size={18} style={{ color: '#cbd5e1' }} />
    </button>
  )
}

// ─── Hulpfuncties ─────────────────────────────────────────────────────────────
const STATUS_CYCLE: Record<string, string> = { gepland: 'bezig', bezig: 'klaar', klaar: 'gepland' }
const WEEKDAGEN = ['Ma', 'Di', 'Wo', 'Do', 'Vr']
const STATUS_KLEUR: Record<string, string> = { gepland: '#4a3a8a', bezig: '#1a6a7a', klaar: '#1a6b42' }
const STATUS_BG:    Record<string, string> = { gepland: '#eeebfa', bezig: '#e6f4f7', klaar: '#e6f5ee' }

function toISO(d: Date) { return d.toISOString().slice(0, 10) }
function addDays(d: Date, n: number) { const r = new Date(d); r.setDate(r.getDate() + n); return r }
function getMaandag(d: Date) {
  const r = new Date(d); const day = r.getDay()
  r.setDate(r.getDate() - (day === 0 ? 6 : day - 1)); r.setHours(0,0,0,0); return r
}
function formatDag(iso: string) {
  return new Date(iso).toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long' })
}
function taakOpDag(t: Taak, iso: string) {
  if (!t.startdatum) return false
  const s = t.startdatum.slice(0,10), e = t.einddatum ? t.einddatum.slice(0,10) : s
  return iso >= s && iso <= e
}

// ─── Mockdata voor disciplines / urgency (overbruggt ontbrekende backend velden)
function verrijkTaak(t: Taak): ExtTaak {
  const disciplines = ['Tegelwerk','Stucwerk','Elektra','Loodgieterij','Schilderwerk','Metselwerk','Timmerwerk']
  const naam = t.naam.toLowerCase()
  const disc = disciplines.find(d => naam.includes(d.toLowerCase()))
  const type = naam.includes('droogdag') ? 'Droogdag' : naam.includes('wachttijd') ? 'Wachttijd' : undefined
  return { ...t, discipline: disc, type, isUrgent: naam.includes('urgent') || naam.includes('spoed') }
}

// ─── Hoofd-component ──────────────────────────────────────────────────────────
function Dashboard() {
  const navigate = useNavigate()

  // State
  const [taken,      setTaken]      = useState<ExtTaak[]>([])
  const [laden,      setLaden]      = useState(true)
  const [weer,       setWeer]       = useState<{ temp: number; code: number; wind: number } | null>(null)
  const [zoekterm,   setZoekterm]   = useState('')
  const [aiAlerts,   setAiAlerts]   = useState([
    { id: '1', bericht: '⚠️ AI Interventie: 1 planningsconflict gedetecteerd via chat (Tegelzetter geeft vertraging aan).', actie: 'Bekijk Oplossing' },
  ])
  const [actieveOplossing, setActieveOplossing] = useState<string | null>(null)
  const [uitgeklapteGroepen, setUitgeklapteGroepen] = useState<Record<string, boolean>>({})
  const [isMobiel, setIsMobiel]     = useState(window.innerWidth < 900)

  // Responsive listener
  useEffect(() => {
    const fn = () => setIsMobiel(window.innerWidth < 900)
    window.addEventListener('resize', fn)
    return () => window.removeEventListener('resize', fn)
  }, [])

  // Taken laden
  const laadTaken = useCallback(async () => {
    try {
      const data = await takenApi.lijst()
      setTaken(data.map(verrijkTaak))
    } catch { /* keep state */ }
    finally { setLaden(false) }
  }, [])

  useEffect(() => { laadTaken() }, [laadTaken])
  useEffect(() => {
    const i = setInterval(laadTaken, 15000)
    window.addEventListener('focus', laadTaken)
    return () => { clearInterval(i); window.removeEventListener('focus', laadTaken) }
  }, [laadTaken])

  // Weer laden via Open-Meteo (Veldhoven)
  useEffect(() => {
    fetch('https://api.open-meteo.com/v1/forecast?latitude=51.4167&longitude=5.4167&current_weather=true')
      .then(r => r.json())
      .then(d => setWeer({
        temp: Math.round(d.current_weather.temperature),
        code: d.current_weather.weathercode,
        wind: Math.round(d.current_weather.windspeed),
      }))
      .catch(() => {})
  }, [])

  // Status togglen
  function toggleStatus(id: string) {
    setTaken(prev => prev.map(t =>
      t.id === id ? { ...t, status: STATUS_CYCLE[t.status] as ExtTaak['status'] } : t
    ))
  }

  // ─── Berekeningen ─────────────────────────────────────────────────────────
  const vandaag  = toISO(new Date())
  const maandag  = getMaandag(new Date())
  const weekDagen = [0,1,2,3,4].map(i => toISO(addDays(maandag, i)))

  // Splits actieve taken van wacht-/droogtaken
  const actieveTaken  = taken.filter(t => t.type !== 'Droogdag' && t.type !== 'Wachttijd')
  const wachtTaken    = taken.filter(t => t.type === 'Droogdag'  || t.type === 'Wachttijd')

  const totaal       = actieveTaken.length  || 1
  const klaarAantal  = actieveTaken.filter(t => t.status === 'klaar').length
  const bezigAantal  = actieveTaken.filter(t => t.status === 'bezig').length
  const klaarPct     = Math.round(klaarAantal / totaal * 100)
  const bezigPct     = Math.round(bezigAantal / totaal * 100)

  const vandaagTaken = actieveTaken.filter(t => taakOpDag(t, vandaag))
  const weekTaken    = actieveTaken.filter(t => weekDagen.some(d => taakOpDag(t, d)))
  const bedrijven    = new Set(actieveTaken.map(t => t.toegewezen_aan).filter(Boolean))
  const takenPerDag  = weekDagen.map(d => actieveTaken.filter(t => taakOpDag(t, d)))

  // Zoekfilter op vandaagtaken
  const gefilterdeVandaag = vandaagTaken.filter(t =>
    !zoekterm ||
    t.naam.toLowerCase().includes(zoekterm.toLowerCase()) ||
    (t.toegewezen_aan ?? '').toLowerCase().includes(zoekterm.toLowerCase()) ||
    (t.beschrijving   ?? '').toLowerCase().includes(zoekterm.toLowerCase())
  )

  // Volgende werkdag
  let eersteTaakDatum = ''
  if (vandaagTaken.length === 0 && taken.length > 0) {
    const datums = taken.map(t => t.startdatum?.slice(0,10))
      .filter((d): d is string => !!d && d >= vandaag).sort()
    eersteTaakDatum = datums[0] || ''
  }

  // Groepeer vandaag per bedrijf
  const perBedrijf: Record<string, ExtTaak[]> = {}
  for (const t of gefilterdeVandaag) {
    const b = t.toegewezen_aan || 'Onbekend'
    if (!perBedrijf[b]) perBedrijf[b] = []
    perBedrijf[b].push(t)
  }

  // ─── KPI-kaart helper ────────────────────────────────────────────────────
  function KPIKaart({
    waarde, label, kleur, pct,
  }: { waarde: string | number; label: string; kleur: string; pct: number }) {
    return (
      <div className="card" style={{ cursor: 'default', position: 'relative', paddingBottom: 20 }}>
        <div className="metric-value" style={{ color: kleur }}>{waarde}</div>
        <div className="metric-label">{label}</div>
        {/* Progress bar */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: 4, background: 'var(--border)', borderRadius: '0 0 10px 10px', overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', width: `${pct}%`, background: kleur,
            borderRadius: '0 0 10px 10px', transition: 'width 0.7s ease',
          }} />
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ margin: 0 }}>Overzicht</h2>
          <p style={{ margin: 0 }}>
            {new Date().toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>

        {/* Zoekbalk */}
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--text-muted)', pointerEvents: 'none',
          }} />
          <input
            type="text"
            value={zoekterm}
            onChange={e => setZoekterm(e.target.value)}
            placeholder="Zoek taak of bedrijf…"
            style={{
              paddingLeft: 32, paddingRight: 12, height: 34, fontSize: 13,
              border: '1px solid var(--border)', borderRadius: 8,
              background: 'var(--bg)', color: 'var(--text)', outline: 'none', width: 200,
            }}
          />
        </div>

        {/* Weer-widget */}
        {weer && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 12px', border: '1px solid var(--border)',
            borderRadius: 8, background: 'var(--bg)', fontSize: 13,
          }}>
            <WeerIconen code={weer.code} size={16} />
            <span style={{ fontWeight: 700, color: 'var(--text)' }}>{weer.temp}°C</span>
            <span style={{ color: 'var(--text-muted)' }}>{weerLabel(weer.code)}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>· {weer.wind} km/u</span>
          </div>
        )}
      </div>

      {/* ── AI Alerts ────────────────────────────────────────────────────── */}
      {aiAlerts.map(alert => (
        <div key={alert.id} style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          background: '#fffbeb', borderLeft: '4px solid #f59e0b',
          borderRadius: '0 8px 8px 0', padding: '12px 14px',
          marginBottom: 16,
        }}>
          <AlertTriangle size={18} style={{ color: '#f59e0b', flexShrink: 0, marginTop: 1 }} />
          <span style={{ flex: 1, fontSize: 13, color: '#92400e', lineHeight: 1.5 }}>{alert.bericht}</span>
          <button
            onClick={() => setActieveOplossing(alert.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '6px 12px', background: '#f59e0b', color: '#fff',
              border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer', flexShrink: 0,
            }}>
            {alert.actie} <ChevronRight size={12} />
          </button>
          <button
            onClick={() => setAiAlerts(a => a.filter(x => x.id !== alert.id))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#d97706', flexShrink: 0, padding: 0 }}
          >
            <X size={16} />
          </button>
        </div>
      ))}

      {/* ── KPI kaarten ──────────────────────────────────────────────────── */}
      <div className="grid-4 mb-24">
        <KPIKaart waarde={laden ? '…' : vandaagTaken.length} label="Taken vandaag"
          kleur={vandaagTaken.length > 0 ? 'var(--teal)' : 'var(--text-muted)'}
          pct={Math.min(100, (vandaagTaken.length / 10) * 100)} />
        <KPIKaart waarde={laden ? '…' : weekTaken.length} label="Taken deze week"
          kleur="var(--navy)" pct={Math.min(100, (weekTaken.length / 50) * 100)} />
        <KPIKaart waarde={laden ? '…' : bedrijven.size} label="Bedrijven actief"
          kleur="#818cf8" pct={Math.min(100, (bedrijven.size / 10) * 100)} />
        <KPIKaart waarde={laden ? '…' : `${klaarAantal}/${actieveTaken.length}`} label="Taken klaar"
          kleur="#4ade80" pct={klaarPct} />
      </div>

      {/* ── Hoofdgrid (flex-col mobiel, grid desktop) ─────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobiel ? '1fr' : '1fr 1fr',
        gap: 20, marginBottom: 20,
      }}>

        {/* Vandaag */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h3>📅 Vandaag</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })}
              {zoekterm && <> · filter: <em>"{zoekterm}"</em></>}
            </span>
          </div>

          {laden ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>Laden…</div>
          ) : gefilterdeVandaag.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
              {zoekterm ? `Geen resultaten voor "${zoekterm}".` : 'Geen werkzaamheden vandaag.'}
              {!zoekterm && eersteTaakDatum && (
                <div style={{ marginTop: 8 }}>
                  Volgende taken: <strong style={{ color: 'var(--text)' }}>{formatDag(eersteTaakDatum)}</strong>
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(perBedrijf).map(([bedrijf, btaken]) => (
                <div key={bedrijf}>
                  <div style={{
                    fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                    marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em',
                  }}>
                    {bedrijf} — {btaken.length} {btaken.length === 1 ? 'taak' : 'taken'}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {btaken.slice(0, uitgeklapteGroepen[bedrijf] ? btaken.length : 5).map(t => (
                      <div key={t.id} style={{
                        display: 'flex', alignItems: 'flex-start', gap: 8,
                        background: STATUS_BG[t.status] ?? '#f8fafc',
                        borderLeft: `3px solid ${discKleur(t.discipline) !== 'var(--border)'
                          ? discKleur(t.discipline)
                          : (STATUS_KLEUR[t.status] ?? '#94a3b8')}`,
                        borderRadius: 6, padding: '7px 10px',
                      }}>
                        <StatusIcoon status={t.status} onClick={() => toggleStatus(t.id)} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
                          }}>
                            <span style={{
                              fontSize: 13,
                              color: STATUS_KLEUR[t.status] ?? 'var(--text)',
                              textDecoration: t.status === 'klaar' ? 'line-through' : 'none',
                              fontWeight: 500,
                            }}>
                              {t.naam}
                            </span>
                            {t.isUrgent && (
                              <span style={{ display: 'flex', alignItems: 'center', gap: 2, color: '#ef4444', fontSize: 11, fontWeight: 700 }}>
                                <Flame size={12} /> Urgent
                              </span>
                            )}
                            {t.discipline && (
                              <span style={{
                                fontSize: 11, background: 'rgba(0,0,0,0.06)',
                                color: 'var(--text-sub)', padding: '1px 6px', borderRadius: 4,
                              }}>
                                {t.discipline}
                              </span>
                            )}
                          </div>
                          {t.beschrijving && (
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {t.beschrijving}
                            </div>
                          )}
                        </div>
                        <span style={{
                          fontSize: 11, fontWeight: 600, flexShrink: 0,
                          color: STATUS_KLEUR[t.status] ?? 'var(--text-muted)',
                        }}>
                          {t.status === 'klaar' ? 'Gereed' : t.status === 'bezig' ? 'Bezig' : 'Gepland'}
                        </span>
                      </div>
                    ))}
                    {btaken.length > 5 && (
                      <button
                        onClick={() => setUitgeklapteGroepen(prev => ({ ...prev, [bedrijf]: !prev[bedrijf] }))}
                        style={{
                          fontSize: 12, color: 'var(--teal)', paddingLeft: 4,
                          background: 'none', border: 'none', cursor: 'pointer',
                          fontWeight: 600, textAlign: 'left', padding: '4px 4px',
                        }}
                      >
                        {uitgeklapteGroepen[bedrijf]
                          ? '▲ Minder tonen'
                          : `▼ +${btaken.length - 5} meer tonen…`}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Deze week */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h3>📆 Deze week</h3>
            <button
              onClick={() => navigate('/planning')}
              style={{ fontSize: 12, color: 'var(--navy)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              Volledige planning →
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {weekDagen.map((dag, i) => {
              const count = takenPerDag[i].length
              const isVandaag = dag === vandaag
              const bedrijvenDag = new Set(takenPerDag[i].map(t => t.toegewezen_aan).filter(Boolean))
              const klaarDag = takenPerDag[i].filter(t => t.status === 'klaar').length
              return (
                <div key={dag} onClick={() => navigate('/planning')} style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
                  borderRadius: 8, cursor: 'pointer',
                  background: isVandaag ? 'var(--navy)20' : 'transparent',
                  border: isVandaag ? '1px solid var(--navy)40' : '1px solid transparent',
                }}>
                  <div style={{ width: 32, fontWeight: 700, fontSize: 13, color: isVandaag ? 'var(--navy)' : 'var(--text-muted)' }}>
                    {WEEKDAGEN[i]}
                  </div>
                  <div style={{ flex: 1 }}>
                    {count > 0 ? (
                      <>
                        <div style={{ height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%',
                            width: `${Math.min(100, (count / 20) * 100)}%`,
                            background: isVandaag ? 'var(--navy)' : 'var(--teal)',
                            borderRadius: 3, transition: 'width 0.5s',
                          }} />
                        </div>
                        {/* Voortgang klaar/totaal */}
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                          {klaarDag}/{count} klaar · {[...bedrijvenDag].slice(0,2).join(', ')}{bedrijvenDag.size > 2 ? ` +${bedrijvenDag.size - 2}` : ''}
                        </div>
                      </>
                    ) : (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Geen taken</div>
                    )}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: count > 0 ? 'var(--text)' : 'var(--text-muted)', minWidth: 24, textAlign: 'right' }}>
                    {count > 0 ? count : '–'}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Extra KPI's onderaan weekkaart */}
          <div style={{
            marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)',
            display: 'flex', gap: 20,
          }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Voortgang</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 80, height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${klaarPct}%`, background: '#4ade80', borderRadius: 3, transition: 'width 0.7s' }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#22c55e' }}>{klaarPct}%</span>
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>In uitvoering</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 80, height: 5, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${bezigPct}%`, background: 'var(--teal)', borderRadius: 3, transition: 'width 0.7s' }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--teal)' }}>{bezigPct}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Wacht- & droogtijden ──────────────────────────────────────────── */}
      {wachtTaken.length > 0 && (
        <div style={{
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 10, marginBottom: 20, overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 16px', borderBottom: '1px solid var(--border)',
          }}>
            <Clock size={14} style={{ color: 'var(--text-muted)' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>
              Wacht- &amp; droogtijden
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
              {wachtTaken.length} items
            </span>
          </div>
          {wachtTaken.map(t => (
            <div key={t.id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 16px', borderBottom: '1px solid var(--border)',
            }}>
              <Clock size={13} style={{ color: '#cbd5e1', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: 13, color: 'var(--text-sub)' }}>{t.naam}</span>
                {t.beschrijving && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{t.beschrijving}</div>
                )}
              </div>
              <span style={{
                fontSize: 11, background: 'var(--border)', color: 'var(--text-muted)',
                padding: '2px 8px', borderRadius: 10,
              }}>
                {t.type}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── AI Oplossing Drawer ──────────────────────────────────────────── */}
      {actieveOplossing && (
        <>
          {/* Overlay */}
          <div
            onClick={() => setActieveOplossing(null)}
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
              zIndex: 100,
            }}
          />
          {/* Drawer */}
          <div style={{
            position: 'fixed', right: 0, top: 0, bottom: 0,
            width: isMobiel ? '100%' : 420,
            background: 'var(--bg-white)', zIndex: 101,
            boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
            display: 'flex', flexDirection: 'column',
            animation: 'slideInRight 0.25s ease',
          }}>
            {/* Header */}
            <div style={{
              padding: '16px 20px', borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <AlertTriangle size={18} color="#f59e0b" />
              <span style={{ fontWeight: 700, fontSize: 15, flex: 1 }}>AI Oplossingsvoorstel</span>
              <button
                onClick={() => setActieveOplossing(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Inhoud */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>

              <div style={{
                background: '#fffbeb', border: '1px solid #f59e0b40',
                borderRadius: 10, padding: 14, marginBottom: 20,
              }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#92400e', marginBottom: 4 }}>
                  ⚠️ Gedetecteerd conflict
                </div>
                <div style={{ fontSize: 13, color: '#92400e', lineHeight: 1.5 }}>
                  Tegelzetter (Ahmed Yilmaz – Derhaag BV) geeft via chat aan dat hij 2 dagen vertraging heeft
                  door materiaallevering. Dit raakt 3 afhankelijke taken in week 18.
                </div>
              </div>

              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12, color: 'var(--text)' }}>
                🤖 Aanbevolen aanpak
              </div>

              {[
                {
                  stap: 1, titel: 'Tegelwerk uitstellen',
                  omschrijving: 'Verschuif "Tegelwerk badkamer" van di 30 apr → do 2 mei. Geen andere taken geblokkeerd.',
                  actie: 'Pas planning aan',
                  kleur: '#3aa8c1',
                },
                {
                  stap: 2, titel: 'Alternatieve vakman inzetten',
                  omschrijving: 'Pieter Smit (Smit Tegels BV) heeft dinsdag en woensdag beschikbaarheid. Geschatte kostenmeerprijs: €240.',
                  actie: 'Stuur bericht',
                  kleur: '#6b5aad',
                },
                {
                  stap: 3, titel: 'Opdrachtgever informeren',
                  omschrijving: 'AI stelt een conceptbericht op voor de opdrachtgever over de vertraging van 2 werkdagen.',
                  actie: 'Concept bekijken',
                  kleur: '#2a5298',
                },
              ].map(item => (
                <div key={item.stap} style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 10, padding: 14, marginBottom: 12,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{
                      width: 22, height: 22, borderRadius: '50%',
                      background: item.kleur, color: '#fff',
                      fontSize: 12, fontWeight: 700,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      {item.stap}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>{item.titel}</span>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-sub)', lineHeight: 1.5, margin: '0 0 10px 30px' }}>
                    {item.omschrijving}
                  </p>
                  <div style={{ paddingLeft: 30 }}>
                    <button style={{
                      padding: '5px 12px', background: item.kleur, color: '#fff',
                      border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    }}>
                      {item.actie} →
                    </button>
                  </div>
                </div>
              ))}

              <div style={{
                background: 'var(--green-bg)', border: '1px solid var(--green)40',
                borderRadius: 10, padding: 14, marginTop: 8,
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--green)', marginBottom: 4 }}>
                  ✅ Verwacht resultaat
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-sub)', lineHeight: 1.5 }}>
                  Vertraging beperkt van 5 naar 2 werkdagen. Opleverdatum blijft haalbaar.
                </div>
              </div>
            </div>

            {/* Footer */}
            <div style={{
              padding: '14px 20px', borderTop: '1px solid var(--border)',
              display: 'flex', gap: 10,
            }}>
              <button
                onClick={() => { setAiAlerts(a => a.filter(x => x.id !== actieveOplossing)); setActieveOplossing(null) }}
                style={{
                  flex: 1, padding: '9px 0', background: 'var(--green)', color: '#fff',
                  border: 'none', borderRadius: 8, fontWeight: 600, fontSize: 13, cursor: 'pointer',
                }}
              >
                ✓ Oplossing accepteren
              </button>
              <button
                onClick={() => setActieveOplossing(null)}
                style={{
                  padding: '9px 16px', background: 'var(--bg)', color: 'var(--text-sub)',
                  border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, cursor: 'pointer',
                }}
              >
                Sluiten
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── Snelkoppelingen ───────────────────────────────────────────────── */}
      <div className="quick-links">
        {[
          { to: '/chat',     icon: '💬', label: 'Chat',      desc: 'Taak invoeren via chat' },
          { to: '/planning', icon: '📅', label: 'Planning',  desc: 'Weekoverzicht bekijken' },
          { to: '/taken',    icon: '✅', label: 'Taken',     desc: 'Alle taken beheren' },
          { to: '/pdf',      icon: '📄', label: 'PDF Invoer', desc: 'Planning importeren' },
        ].map(link => (
          <Link key={link.to} to={link.to} className="quick-link-card">
            <div style={{ fontSize: 24, marginBottom: 6 }}>{link.icon}</div>
            <div className="quick-link-label">{link.label}</div>
            <div className="quick-link-desc">{link.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default Dashboard
