import { useState, useEffect, useCallback } from 'react'
import {
  type Taak,
  type VoorgesteldeMutatie,
  type Melding,
  type Afhankelijkheden,
  type VerschovenTaak,
  takenApi,
  mutatiesApi,
  meldingenApi,
  afhankelijkhedenApi,
} from '../hooks/useApi'
import { usePush } from '../hooks/usePush'
import { Bell, BellOff, Check, Inbox, Link2, User, X } from 'lucide-react'

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
  gepland:  { bg: 'var(--blue-bg)',   text: 'var(--blue)',   dot: 'var(--blue)',   label: 'Gepland' },
  bezig:    { bg: 'var(--yellow-bg)', text: 'var(--yellow)', dot: 'var(--yellow)', label: 'Bezig' },
  klaar:    { bg: 'var(--green-bg)',  text: 'var(--green)',  dot: 'var(--green)',  label: 'Klaar' },
}

// ─── component ──────────────────────────────────────────────────────────────

function Planning() {
  const [taken, setTaken] = useState<Taak[]>([])
  const [laden, setLaden] = useState(true)
  const [huidigeMaandag, setHuidigeMaandag] = useState<Date>(() => getMondayOfWeek(new Date()))
  const [filterStatus, setFilterStatus] = useState<string>('alle')
  const [filterBedrijf, setFilterBedrijf] = useState<string>('alle')
  const [zoek, setZoek] = useState('')

  // Mobiel: één dag tegelijk tonen i.p.v. vijf smalle kolommen
  const [isMobiel, setIsMobiel] = useState(window.innerWidth < 768)
  const [gekozenDag, setGekozenDag] = useState<number>(() => {
    const d = new Date().getDay() // 1 = ma ... 5 = vr
    return d >= 1 && d <= 5 ? d - 1 : 0
  })
  useEffect(() => {
    const f = () => setIsMobiel(window.innerWidth < 768)
    window.addEventListener('resize', f)
    return () => window.removeEventListener('resize', f)
  }, [])

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

  // ─── Voorgestelde wijzigingen + meldingen ──────────────────────────────────
  const [voorstellen, setVoorstellen] = useState<VoorgesteldeMutatie[]>([])
  const [meldingen, setMeldingen] = useState<Melding[]>([])
  const [bezigId, setBezigId] = useState<string | null>(null)

  const laadVoorstellen = useCallback(async () => {
    try { setVoorstellen(await mutatiesApi.lijst()) } catch { setVoorstellen([]) }
  }, [])

  const laadMeldingen = useCallback(async () => {
    try { setMeldingen(await meldingenApi.lijst()) } catch { setMeldingen([]) }
  }, [])

  useEffect(() => { laadVoorstellen(); laadMeldingen() }, [laadVoorstellen, laadMeldingen])

  const bevestigVoorstel = async (id: string) => {
    setBezigId(id)
    try {
      const res = await mutatiesApi.bevestig(id)
      meldCascade(res.automatisch_verschoven)
      await Promise.all([laadTaken(), laadVoorstellen(), laadMeldingen()])
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Bevestigen mislukt')
    } finally {
      setBezigId(null)
    }
  }

  const wijsVoorstelAf = async (id: string) => {
    setBezigId(id)
    try {
      await mutatiesApi.afwijs(id)
      await laadVoorstellen()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Afwijzen mislukt')
    } finally {
      setBezigId(null)
    }
  }

  const markeerGelezen = async (id: string) => {
    try {
      await meldingenApi.markeerGelezen(id)
      setMeldingen(ms => ms.map(m => (m.id === id ? { ...m, gelezen: true } : m)))
    } catch { /* stil */ }
  }

  const ongelezenMeldingen = meldingen.filter(m => !m.gelezen)

  // ─── Push-meldingen op dit apparaat ────────────────────────────────────────
  const push = usePush()

  // ─── Volgorde-relaties (klik op een taak) ──────────────────────────────────
  const [geselecteerdeTaak, setGeselecteerdeTaak] = useState<Taak | null>(null)
  const [afhankelijkheden, setAfhankelijkheden] = useState<Afhankelijkheden | null>(null)
  const [nieuweVoorganger, setNieuweVoorganger] = useState('')
  const [afhBezig, setAfhBezig] = useState(false)
  const [cascadeBericht, setCascadeBericht] = useState<string | null>(null)

  const meldCascade = (verschoven?: VerschovenTaak[]) => {
    if (!verschoven || verschoven.length === 0) return
    setCascadeBericht(
      `${verschoven.length} ${verschoven.length === 1 ? 'taak is' : 'taken zijn'} automatisch mee verschoven: ` +
      verschoven.map(v => `${v.naam} → ${v.nieuwe_start} t/m ${v.nieuwe_eind}`).join(' · ')
    )
  }

  const openTaak = async (taak: Taak) => {
    setGeselecteerdeTaak(taak)
    setNieuweVoorganger('')
    setAfhankelijkheden(null)
    try {
      setAfhankelijkheden(await afhankelijkhedenApi.lijst(taak.id))
    } catch {
      setAfhankelijkheden({ voorgangers: [], volgers: [] })
    }
  }

  const voegVoorgangerToe = async () => {
    if (!geselecteerdeTaak || !nieuweVoorganger) return
    setAfhBezig(true)
    try {
      const res = await afhankelijkhedenApi.toevoegen(geselecteerdeTaak.id, nieuweVoorganger)
      meldCascade(res.automatisch_verschoven)
      setAfhankelijkheden(await afhankelijkhedenApi.lijst(geselecteerdeTaak.id))
      setNieuweVoorganger('')
      if (res.automatisch_verschoven?.length) await laadTaken()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Toevoegen mislukt')
    } finally {
      setAfhBezig(false)
    }
  }

  const verwijderVoorganger = async (voorgangerId: string) => {
    if (!geselecteerdeTaak) return
    setAfhBezig(true)
    try {
      await afhankelijkhedenApi.verwijderen(geselecteerdeTaak.id, voorgangerId)
      setAfhankelijkheden(await afhankelijkhedenApi.lijst(geselecteerdeTaak.id))
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Verwijderen mislukt')
    } finally {
      setAfhBezig(false)
    }
  }

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
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h2>Planning</h2>
          <p>Weekoverzicht bouwwerkzaamheden</p>
        </div>
        {push.status !== 'niet-ondersteund' && (
          <button
            className="secondary"
            disabled={push.status === 'bezig' || push.status === 'geweigerd'}
            onClick={push.status === 'aan' ? push.zetUit : push.zetAan}
            title={push.status === 'geweigerd'
              ? 'Meldingen zijn geblokkeerd in je browserinstellingen'
              : 'Ontvang planningswijzigingen als melding op dit apparaat'}
            style={{ padding: '8px 14px', fontSize: 13, flexShrink: 0 }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {push.status === 'aan' && <><Bell size={14} /> Push-meldingen aan</>}
              {push.status === 'uit' && <><BellOff size={14} /> Zet push-meldingen aan</>}
              {push.status === 'bezig' && 'Bezig...'}
              {push.status === 'geweigerd' && <><BellOff size={14} /> Meldingen geblokkeerd</>}
            </span>
          </button>
        )}
      </div>

      {/* Cascade-banner: toont wat er automatisch mee verschoven is */}
      {cascadeBericht && (
        <div className="card" style={{
          marginBottom: 20, borderLeft: '3px solid var(--blue)',
          display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center',
        }}>
          <span style={{ fontSize: 13, color: 'var(--text)', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Link2 size={15} style={{ color: 'var(--blue)', flexShrink: 0 }} />
            {cascadeBericht}
          </span>
          <button className="secondary" onClick={() => setCascadeBericht(null)}
            style={{ padding: '4px 10px', fontSize: 12, flexShrink: 0 }}><X size={13} /></button>
        </div>
      )}

      {/* Voorgestelde wijzigingen — alleen de zender ziet en bevestigt zijn eigen voorstellen */}
      {voorstellen.length > 0 && (
        <div className="card" style={{ marginBottom: 20, borderLeft: '3px solid var(--navy)' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Inbox size={16} style={{ color: 'var(--navy)' }} />
            Voorgestelde wijzigingen ({voorstellen.length})
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 14 }}>
            Door AI herkend uit je berichten. Bevestig om de planning aan te passen, of wijs af.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {voorstellen.map(v => {
              const p = v.voorstel
              const periode = p.startdatum
                ? `${p.startdatum}${p.einddatum && p.einddatum !== p.startdatum ? ` t/m ${p.einddatum}` : ''}`
                : null
              const isAanmaken = p.actie === 'taak_aanmaken'
              return (
                <div key={v.id} style={{
                  background: 'var(--bg-white)',
                  border: '1px solid var(--border)',
                  borderRadius: 10,
                  padding: '12px 14px',
                }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                    <span style={{
                      background: isAanmaken ? 'var(--green-bg)' : 'var(--blue-bg)',
                      color: isAanmaken ? 'var(--green)' : 'var(--blue)',
                      borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 700,
                      letterSpacing: 0.4,
                    }}>
                      {isAanmaken ? 'NIEUWE TAAK' : 'WIJZIGING'}
                    </span>
                    {v.bron === 'weer' && (
                      <span style={{
                        background: 'var(--yellow-bg)', color: 'var(--yellow)',
                        borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 700,
                        letterSpacing: 0.4,
                      }}>
                        WEERBEWAKING
                      </span>
                    )}
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      vertrouwen {Math.round((p.vertrouwen ?? 0) * 100)}%
                    </span>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                    {p.samenvatting || p.naam || 'Voorstel'}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-sub)', marginBottom: 4 }}>
                    {[p.naam, periode, p.toegewezen_aan].filter(Boolean).join('  ·  ')}
                  </div>
                  {p.komt_na && p.komt_na.length > 0 && (
                    <div style={{ fontSize: 12, color: 'var(--blue)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Link2 size={12} style={{ flexShrink: 0 }} />
                      Komt na: {p.komt_na
                        .map(id => taken.find(t => t.id === id)?.naam || 'onbekende taak')
                        .join(', ')} — schuift automatisch mee bij uitloop
                    </div>
                  )}
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', marginBottom: 10 }}>
                    “{v.ruwe_tekst}”
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => bevestigVoorstel(v.id)}
                      disabled={bezigId === v.id}
                      style={{
                        background: 'var(--green)', color: '#fff', border: 'none',
                        borderRadius: 6, padding: '7px 16px', fontSize: 13, fontWeight: 600,
                        cursor: bezigId === v.id ? 'wait' : 'pointer', opacity: bezigId === v.id ? 0.6 : 1,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      <Check size={14} /> Bevestig
                    </button>
                    <button
                      className="secondary"
                      onClick={() => wijsVoorstelAf(v.id)}
                      disabled={bezigId === v.id}
                      style={{ padding: '7px 16px', fontSize: 13 }}
                    >
                      Afwijzen
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Meldingen — wijzigingen die jou (direct of via datumoverlap) raken */}
      {meldingen.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Bell size={16} style={{ color: 'var(--navy)' }} /> Meldingen
            </span>
            {ongelezenMeldingen.length > 0 && (
              <span style={{
                background: 'var(--navy)', color: '#fff', borderRadius: 20,
                padding: '1px 9px', fontSize: 12, fontWeight: 700,
              }}>
                {ongelezenMeldingen.length} nieuw
              </span>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {meldingen.slice(0, 10).map(m => (
              <div
                key={m.id}
                onClick={() => !m.gelezen && markeerGelezen(m.id)}
                style={{
                  background: m.gelezen ? 'var(--bg-white)' : 'var(--blue-bg)',
                  border: `1px solid ${m.gelezen ? 'var(--border)' : 'var(--blue)'}`,
                  borderRadius: 6, padding: '9px 12px',
                  cursor: m.gelezen ? 'default' : 'pointer',
                  display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center',
                }}
              >
                <span style={{ fontSize: 13, color: m.gelezen ? 'var(--text-muted)' : 'var(--text)' }}>
                  {m.tekst}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  {new Date(m.tijdstip).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })}
                  {!m.gelezen && ' · markeer gelezen'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

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
      <div style={{ display: 'grid', gridTemplateColumns: isMobiel ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Taken deze week', waarde: weekStats.totaal, kleur: 'var(--text)' },
          { label: 'Gepland', waarde: weekStats.gepland, kleur: 'var(--blue)' },
          { label: 'Bezig', waarde: weekStats.bezig, kleur: 'var(--yellow)' },
          { label: 'Klaar', waarde: weekStats.klaar, kleur: 'var(--green)' },
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
      ) : isMobiel ? (
        /* ── Mobiel: dag-selector + één dag als lijst ─────────────────── */
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 14 }}>
            {weekDagen.map((dag, i) => {
              const actief = i === gekozenDag
              const isVandaag = toISO(dag) === vandaagISO
              return (
                <button
                  key={i}
                  onClick={() => setGekozenDag(i)}
                  style={{
                    padding: '10px 0', borderRadius: 8, cursor: 'pointer',
                    border: `1px solid ${actief ? 'var(--navy)' : isVandaag ? 'var(--navy)' : 'var(--border)'}`,
                    background: actief ? 'var(--navy)' : 'var(--bg-white)',
                    color: actief ? '#fff' : 'var(--text)',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{DAGEN[i]}</div>
                  <div style={{ fontSize: 11, opacity: 0.75, marginTop: 1 }}>
                    {dag.getDate()} {dag.toLocaleDateString('nl-NL', { month: 'short' })}
                  </div>
                  {takenPerDag[i].length > 0 && (
                    <div style={{ fontSize: 11, fontWeight: 700, marginTop: 2, color: actief ? '#fff' : 'var(--navy)' }}>
                      {takenPerDag[i].length} {takenPerDag[i].length === 1 ? 'taak' : 'taken'}
                    </div>
                  )}
                </button>
              )
            })}
          </div>

          {takenPerDag[gekozenDag].length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>
              Geen taken op {DAGEN[gekozenDag].toLowerCase()} {weekDagen[gekozenDag].getDate()} {weekDagen[gekozenDag].toLocaleDateString('nl-NL', { month: 'short' })}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {takenPerDag[gekozenDag].map(taak => {
                const stijl = statusStijl[taak.status] ?? statusStijl.gepland
                const start = taak.startdatum ? taak.startdatum.slice(0, 10) : ''
                const eind = taak.einddatum ? taak.einddatum.slice(0, 10) : start
                return (
                  <div
                    key={taak.id}
                    onClick={() => openTaak(taak)}
                    style={{
                      background: 'var(--bg-white)',
                      border: '1px solid var(--border)',
                      borderLeft: `4px solid ${stijl.dot}`,
                      borderRadius: 8,
                      padding: '12px 14px',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', lineHeight: 1.35 }}>
                        {taak.naam}
                      </div>
                      <span style={{
                        background: stijl.bg, color: stijl.text, flexShrink: 0,
                        borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600,
                      }}>
                        {stijl.label}
                      </span>
                    </div>
                    <div style={{ fontSize: 12.5, color: 'var(--text-sub)', marginTop: 6, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
                      {taak.toegewezen_aan && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                          <User size={12} /> {taak.toegewezen_aan}
                        </span>
                      )}
                      {start && <span>{start === eind ? start : `${start} t/m ${eind}`}</span>}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
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
                          <div key={taak.id} onClick={() => openTaak(taak)} title="Klik voor volgorde-instellingen" style={{
                            background: stijl.bg,
                            borderRadius: 8,
                            padding: '8px 10px',
                            borderLeft: `3px solid ${stijl.dot}`,
                            cursor: 'pointer',
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
                                <User size={11} style={{ flexShrink: 0 }} />
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

      {/* Volgorde-venster: welke taken moeten eerst klaar zijn? */}
      {geselecteerdeTaak && (
        <div
          onClick={() => setGeselecteerdeTaak(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            className="card"
            style={{ width: 'min(500px, 92vw)', maxHeight: '80vh', overflowY: 'auto', marginBottom: 0 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
              <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Link2 size={17} style={{ color: 'var(--navy)', flexShrink: 0 }} />
                {geselecteerdeTaak.naam}
              </div>
              <button className="secondary" onClick={() => setGeselecteerdeTaak(null)}
                style={{ padding: '4px 10px', fontSize: 12 }}><X size={13} /></button>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
              {geselecteerdeTaak.startdatum
                ? `${geselecteerdeTaak.startdatum.slice(0, 10)} t/m ${(geselecteerdeTaak.einddatum || geselecteerdeTaak.startdatum).slice(0, 10)}`
                : 'Nog geen datum'}
              {geselecteerdeTaak.toegewezen_aan && ` · ${geselecteerdeTaak.toegewezen_aan}`}
            </div>

            {afhankelijkheden === null ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Laden...</div>
            ) : (
              <>
                {/* Voorgangers */}
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
                  Kan pas beginnen als dit klaar is:
                </div>
                {afhankelijkheden.voorgangers.length === 0 ? (
                  <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
                    Nog geen voorgangers ingesteld.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
                    {afhankelijkheden.voorgangers.map(v => (
                      <div key={v.id} style={{
                        background: 'var(--bg-white)', border: '1px solid var(--border)',
                        borderRadius: 8, padding: '8px 12px',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
                      }}>
                        <span style={{ fontSize: 13, color: 'var(--text)' }}>
                          {v.naam}
                          {v.einddatum && (
                            <span style={{ color: 'var(--text-muted)' }}> · klaar op {v.einddatum}</span>
                          )}
                        </span>
                        <button
                          className="secondary"
                          disabled={afhBezig}
                          onClick={() => verwijderVoorganger(v.id)}
                          style={{ padding: '3px 9px', fontSize: 12, flexShrink: 0 }}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Voorganger toevoegen */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
                  <select
                    value={nieuweVoorganger}
                    onChange={e => setNieuweVoorganger(e.target.value)}
                    style={{
                      flex: 1, background: 'var(--bg-white)', border: '1px solid var(--border)',
                      borderRadius: 8, padding: '8px 10px', color: 'var(--text)', fontSize: 13,
                    }}
                  >
                    <option value="">— Kies een taak die eerst klaar moet zijn —</option>
                    {taken
                      .filter(t =>
                        t.id !== geselecteerdeTaak.id &&
                        !afhankelijkheden.voorgangers.some(v => v.id === t.id))
                      .map(t => (
                        <option key={t.id} value={t.id}>
                          {t.naam}{t.toegewezen_aan ? ` (${t.toegewezen_aan})` : ''}
                        </option>
                      ))}
                  </select>
                  <button
                    onClick={voegVoorgangerToe}
                    disabled={afhBezig || !nieuweVoorganger}
                    style={{
                      background: 'var(--navy)', color: '#fff', border: 'none', borderRadius: 8,
                      padding: '8px 14px', fontSize: 13, fontWeight: 700,
                      cursor: afhBezig || !nieuweVoorganger ? 'not-allowed' : 'pointer',
                      opacity: afhBezig || !nieuweVoorganger ? 0.5 : 1,
                    }}
                  >
                    + Toevoegen
                  </button>
                </div>

                {/* Volgers (alleen-lezen) */}
                {afhankelijkheden.volgers.length > 0 && (
                  <>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
                      Schuift automatisch mee als deze taak uitloopt:
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {afhankelijkheden.volgers.map(v => (
                        <div key={v.id} style={{
                          background: 'var(--bg-white)', border: '1px solid var(--border)',
                          borderRadius: 6, padding: '8px 12px', fontSize: 13, color: 'var(--text-sub)',
                          display: 'flex', alignItems: 'center', gap: 8,
                        }}>
                          <Link2 size={13} style={{ color: 'var(--blue)', flexShrink: 0 }} />
                          {v.naam}
                          {v.startdatum && ` · start ${v.startdatum}`}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Planning
