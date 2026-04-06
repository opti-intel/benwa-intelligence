import { useState, useEffect, useCallback } from 'react'
import { type Taak, takenApi } from '../hooks/useApi'

// ─── helpers ────────────────────────────────────────────────────────────────

const DAGEN = ['Ma', 'Di', 'Wo', 'Do', 'Vr']

function getMondayOfWeek(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

function addDays(date: Date, n: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + n)
  return d
}

function toISO(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function getWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  const dayNum = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7)
}

function formatDatum(date: Date): string {
  return date.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
}

function taakOpDag(taak: Taak, dagISO: string): boolean {
  if (!taak.startdatum) return false
  const start = taak.startdatum.slice(0, 10)
  const eind = taak.einddatum ? taak.einddatum.slice(0, 10) : start
  return dagISO >= start && dagISO <= eind
}

// ─── status styling ─────────────────────────────────────────────────────────

const statusStijl: Record<string, { bg: string; text: string; dot: string; label: string }> = {
  gepland:  { bg: '#1e1b4b', text: '#a5b4fc', dot: 'var(--purple)', label: 'Gepland' },
  bezig:    { bg: '#1e3a5f', text: '#7dd3fc', dot: 'var(--teal)', label: 'Bezig' },
  klaar:    { bg: '#14532d', text: '#86efac', dot: '#4ade80', label: 'Klaar' },
}

// ─── component ──────────────────────────────────────────────────────────────

function Planning() {
  const [taken, setTaken] = useState<Taak[]>([])
  const [laden, setLaden] = useState(true)
  const [huidigeMaandag, setHuidigeMaandag] = useState<Date>(() => getMondayOfWeek(new Date()))
  const [filterStatus, setFilterStatus] = useState<string>('alle')
  const [filterBedrijf, setFilterBedrijf] = useState<string>('alle')
  const [zoek, setZoek] = useState('')

  const laadTaken = useCallback(async () => {
    setLaden(true)
    try {
      const data = await takenApi.lijst()
      setTaken(data)
    } catch {
      setTaken([])
    } finally {
      setLaden(false)
    }
  }, [])

  useEffect(() => { laadTaken() }, [laadTaken])

  // Week navigatie
  const vorigeWeek = () => setHuidigeMaandag(d => addDays(d, -7))
  const volgendeWeek = () => setHuidigeMaandag(d => addDays(d, 7))
  const naarVandaag = () => setHuidigeMaandag(getMondayOfWeek(new Date()))

  // Dagen van huidige week (ma t/m vr)
  const weekDagen = DAGEN.map((_, i) => addDays(huidigeMaandag, i))
  const weekNummer = getWeekNumber(huidigeMaandag)
  const weekLabel = `${formatDatum(huidigeMaandag)} – ${formatDatum(addDays(huidigeMaandag, 4))}`

  // Unieke bedrijven uit alle taken
  const alleBedrijven = [...new Set(taken.map(t => t.toegewezen_aan).filter((b): b is string => !!b))].sort()

  // Filter taken
  const gefilterdeтaken = taken.filter(t => {
    if (filterStatus !== 'alle' && t.status !== filterStatus) return false
    if (filterBedrijf !== 'alle' && t.toegewezen_aan !== filterBedrijf) return false
    if (zoek) {
      const q = zoek.toLowerCase().replace(/\s+/g, '')
      const naam = t.naam.toLowerCase().replace(/\s+/g, '')
      const bedrijf = (t.toegewezen_aan ?? '').toLowerCase().replace(/\s+/g, '')
      if (!naam.includes(q) && !bedrijf.includes(q)) return false
    }
    return true
  })

  // Taken per dag
  const takenPerDag = weekDagen.map(dag => {
    const iso = toISO(dag)
    return gefilterdeтaken.filter(t => taakOpDag(t, iso))
  })

  // Statistieken voor huidige week
  const weekTaken = new Set(
    weekDagen.flatMap(dag => takenPerDag[weekDagen.indexOf(dag)].map(t => t.id))
  )
  const weekStats = {
    totaal: weekTaken.size,
    gepland: taken.filter(t => weekTaken.has(t.id) && t.status === 'gepland').length,
    bezig: taken.filter(t => weekTaken.has(t.id) && t.status === 'bezig').length,
    klaar: taken.filter(t => weekTaken.has(t.id) && t.status === 'klaar').length,
  }

  const vandaagISO = toISO(new Date())

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <h2>Planning</h2>
        <p>Weekoverzicht bouwwerkzaamheden</p>
      </div>

      {/* Week navigatie */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <button className="secondary" onClick={vorigeWeek} style={{ padding: '8px 14px' }}>← Vorige</button>
        <div style={{
          background: 'var(--bg-white)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '8px 20px',
          textAlign: 'center',
          minWidth: 200,
        }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>
            Week {weekNummer}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>{weekLabel}</div>
        </div>
        <button className="secondary" onClick={volgendeWeek} style={{ padding: '8px 14px' }}>Volgende →</button>
        <button className="secondary" onClick={naarVandaag} style={{ padding: '8px 14px' }}>Vandaag</button>
        <button className="secondary" onClick={laadTaken} style={{ padding: '8px 14px', marginLeft: 8 }}>↻ Vernieuwen</button>

        {/* Zoek */}
        <input
          type="text"
          placeholder="Zoek taak of persoon..."
          value={zoek}
          onChange={e => setZoek(e.target.value)}
          style={{
            background: 'var(--bg-white)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '8px 14px',
            color: 'var(--text)',
            fontSize: 14,
            minWidth: 180,
            marginLeft: 'auto',
          }}
        />

        {/* Status filter */}
        <div className="tabs" style={{ marginBottom: 0 }}>
          {['alle', 'gepland', 'bezig', 'klaar'].map(s => (
            <button
              key={s}
              className={`tab ${filterStatus === s ? 'active' : ''}`}
              onClick={() => setFilterStatus(s)}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Bedrijfsfilter */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        <button
          onClick={() => setFilterBedrijf('alle')}
          style={{
            padding: '6px 14px',
            borderRadius: 20,
            border: '1px solid var(--border)',
            background: filterBedrijf === 'alle' ? 'var(--navy)' : 'var(--bg-white)',
            color: filterBedrijf === 'alle' ? '#fff' : 'var(--text-muted)',
            fontSize: 13,
            fontWeight: filterBedrijf === 'alle' ? 700 : 400,
            cursor: 'pointer',
          }}
        >
          Alle bedrijven
        </button>
        {alleBedrijven.map(b => (
          <button
            key={b}
            onClick={() => setFilterBedrijf(filterBedrijf === b ? 'alle' : b)}
            style={{
              padding: '6px 14px',
              borderRadius: 20,
              border: `1px solid ${filterBedrijf === b ? 'var(--navy)' : 'var(--border)'}`,
              background: filterBedrijf === b ? 'var(--navy)20' : 'var(--bg-white)',
              color: filterBedrijf === b ? 'var(--navy)' : 'var(--text-muted)',
              fontSize: 13,
              fontWeight: filterBedrijf === b ? 700 : 400,
              cursor: 'pointer',
            }}
          >
            {b}
          </button>
        ))}
      </div>

      {/* Weekstatistieken */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Taken deze week', waarde: weekStats.totaal, kleur: 'var(--text)' },
          { label: 'Gepland', waarde: weekStats.gepland, kleur: '#a5b4fc' },
          { label: 'Bezig', waarde: weekStats.bezig, kleur: '#7dd3fc' },
          { label: 'Klaar', waarde: weekStats.klaar, kleur: '#86efac' },
        ].map(stat => (
          <div key={stat.label} className="card" style={{ padding: '14px 18px', marginBottom: 0 }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: stat.kleur }}>{stat.waarde}</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Dagkolommen */}
      {laden ? (
        <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
          Taken laden...
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: 12,
        }}>
          {weekDagen.map((dag, i) => {
            const iso = toISO(dag)
            const isVandaag = iso === vandaagISO
            const dagTaken = takenPerDag[i]

            return (
              <div key={iso} style={{
                background: 'var(--bg-white)',
                border: `1px solid ${isVandaag ? 'var(--navy)' : 'var(--border)'}`,
                borderRadius: 12,
                overflow: 'hidden',
                boxShadow: isVandaag ? '0 0 0 1px var(--navy)' : undefined,
              }}>
                {/* Dag header */}
                <div style={{
                  background: isVandaag ? 'var(--navy)' : 'var(--border)',
                  padding: '10px 14px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <div>
                    <div style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: isVandaag ? '#fff' : 'var(--text)',
                    }}>
                      {DAGEN[i]}
                    </div>
                    <div style={{
                      fontSize: 12,
                      color: isVandaag ? 'rgba(255,255,255,0.8)' : 'var(--text-muted)',
                      marginTop: 1,
                    }}>
                      {formatDatum(dag)}
                    </div>
                  </div>
                  {dagTaken.length > 0 && (
                    <div style={{
                      background: isVandaag ? 'rgba(255,255,255,0.25)' : 'var(--bg-white)',
                      borderRadius: 20,
                      padding: '2px 9px',
                      fontSize: 13,
                      fontWeight: 700,
                      color: isVandaag ? '#fff' : 'var(--text)',
                    }}>
                      {dagTaken.length}
                    </div>
                  )}
                </div>

                {/* Taken */}
                <div style={{ padding: 10, minHeight: 120 }}>
                  {dagTaken.length === 0 ? (
                    <div style={{
                      textAlign: 'center',
                      color: 'var(--text-muted)',
                      fontSize: 13,
                      marginTop: 24,
                    }}>
                      Geen taken
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {dagTaken.map(taak => {
                        const stijl = statusStijl[taak.status] ?? statusStijl.gepland
                        return (
                          <div key={taak.id} style={{
                            background: stijl.bg,
                            borderRadius: 8,
                            padding: '8px 10px',
                            borderLeft: `3px solid ${stijl.dot}`,
                          }}>
                            <div style={{
                              fontSize: 13,
                              fontWeight: 600,
                              color: stijl.text,
                              lineHeight: 1.3,
                              marginBottom: 4,
                            }}>
                              {taak.naam}
                            </div>
                            {taak.toegewezen_aan && (
                              <div style={{
                                fontSize: 11,
                                color: 'var(--text-muted)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                              }}>
                                <span>👤</span>
                                <span>{taak.toegewezen_aan}</span>
                              </div>
                            )}
                            <div style={{
                              display: 'inline-block',
                              marginTop: 4,
                              background: stijl.dot + '30',
                              color: stijl.dot,
                              borderRadius: 4,
                              padding: '1px 6px',
                              fontSize: 11,
                              fontWeight: 600,
                            }}>
                              {stijl.label}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Totaal taken info */}
      <div style={{
        marginTop: 16,
        fontSize: 13,
        color: 'var(--text-muted)',
        textAlign: 'center',
      }}>
        {taken.length} taken totaal in database
        {taken.length > 0 && ` · gebruik de pijltjes om door de planning te navigeren`}
      </div>
    </div>
  )
}

export default Planning
