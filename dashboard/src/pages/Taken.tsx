import { useState, useEffect, useCallback } from 'react'
import { type Taak, type TaakStatus, takenApi } from '../hooks/useApi'

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

type FilterStatus = 'alles' | TaakStatus

function Taken() {
  const [taken, setTaken] = useState<Taak[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<FilterStatus>('alles')
  const [filterBedrijf, setFilterBedrijf] = useState<string>('alle')
  const [zoek, setZoek] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editTaak, setEditTaak] = useState<Taak | null>(null)

  // Form state
  const [formNaam, setFormNaam] = useState('')
  const [formBeschrijving, setFormBeschrijving] = useState('')
  const [formStatus, setFormStatus] = useState<TaakStatus>('gepland')
  const [formStart, setFormStart] = useState('')
  const [formEind, setFormEind] = useState('')
  const [formToegewezen, setFormToegewezen] = useState('')

  const fetchTaken = useCallback(async () => {
    try {
      const data = await takenApi.lijst()
      setTaken(data)
    } catch {
      // keep current state on error
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTaken() }, [fetchTaken])

  useEffect(() => {
    window.addEventListener('focus', fetchTaken)
    return () => window.removeEventListener('focus', fetchTaken)
  }, [fetchTaken])

  // Unieke bedrijven
  const alleBedrijven = [...new Set(taken.map(t => t.toegewezen_aan).filter((b): b is string => !!b))].sort()

  // Filter + zoek
  const gefilterd = taken.filter(t => {
    if (filter !== 'alles' && t.status !== filter) return false
    if (filterBedrijf !== 'alle' && t.toegewezen_aan !== filterBedrijf) return false
    if (zoek) {
      const q = zoek.toLowerCase().replace(/\s+/g, '')
      const naam = t.naam.toLowerCase().replace(/\s+/g, '')
      const bedrijf = (t.toegewezen_aan ?? '').toLowerCase().replace(/\s+/g, '')
      const beschr = (t.beschrijving ?? '').toLowerCase().replace(/\s+/g, '')
      if (!naam.includes(q) && !bedrijf.includes(q) && !beschr.includes(q)) return false
    }
    return true
  })

  function openAdd() {
    setEditTaak(null)
    setFormNaam('')
    setFormBeschrijving('')
    setFormStatus('gepland')
    setFormStart('')
    setFormEind('')
    setFormToegewezen('')
    setModalOpen(true)
  }

  function openEdit(taak: Taak) {
    setEditTaak(taak)
    setFormNaam(taak.naam)
    setFormBeschrijving(taak.beschrijving)
    setFormStatus(taak.status)
    setFormStart(taak.startdatum)
    setFormEind(taak.einddatum)
    setFormToegewezen(taak.toegewezen_aan)
    setModalOpen(true)
  }

  async function handleSave() {
    if (!formNaam.trim()) return

    const payload = {
      naam: formNaam,
      beschrijving: formBeschrijving,
      status: formStatus,
      startdatum: formStart,
      einddatum: formEind,
      toegewezen_aan: formToegewezen,
    }

    try {
      if (editTaak) {
        const updated = await takenApi.bijwerken(editTaak.id, payload)
        setTaken(prev => prev.map(t => t.id === editTaak.id ? updated : t))
      } else {
        const created = await takenApi.aanmaken({ ...payload, id: crypto.randomUUID() })
        setTaken(prev => [...prev, created])
      }
    } catch {
      return
    }
    setModalOpen(false)
  }

  async function handleDelete() {
    if (!editTaak) return
    try {
      await takenApi.verwijderen(editTaak.id)
      setTaken(prev => prev.filter(t => t.id !== editTaak.id))
    } catch {
      return
    }
    setModalOpen(false)
  }

  function formatDate(d: string) {
    if (!d) return '—'
    return new Date(d).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const filters: { key: FilterStatus; label: string }[] = [
    { key: 'alles', label: 'Alles' },
    { key: 'gepland', label: 'Gepland' },
    { key: 'bezig', label: 'Bezig' },
    { key: 'klaar', label: 'Klaar' },
  ]

  return (
    <div>
      <div className="page-header">
        <h2>Taken</h2>
        <p>Beheer en volg projecttaken</p>
      </div>

      {/* Zoek + status filter + nieuwe taak */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
        <div className="tabs" style={{ marginBottom: 0 }}>
          {filters.map(f => (
            <button
              key={f.key}
              className={`tab ${filter === f.key ? 'active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Zoek taak, beschrijving of bedrijf..."
          value={zoek}
          onChange={e => setZoek(e.target.value)}
          style={{
            background: 'var(--bg-white)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '8px 14px',
            color: 'var(--text)',
            fontSize: 14,
            minWidth: 220,
            marginLeft: 'auto',
          }}
        />

        <button className="primary" onClick={openAdd}>+ Nieuwe taak</button>
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

      {/* Teller */}
      {!loading && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
          {gefilterd.length} {gefilterd.length === 1 ? 'taak' : 'taken'} gevonden
          {taken.length !== gefilterd.length && ` (van ${taken.length} totaal)`}
        </div>
      )}

      {loading ? (
        <div className="empty-state">Laden...</div>
      ) : (
        <div className="grid-2">
          {gefilterd.map(taak => (
            <div key={taak.id} className="taak-card" onClick={() => openEdit(taak)}>
              <div className="taak-card-header">
                <span className="taak-card-naam">{taak.naam}</span>
                <span className={`status-badge ${statusBadgeClass[taak.status]}`}>
                  {statusLabels[taak.status]}
                </span>
              </div>
              {taak.beschrijving && (
                <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 4 }}>{taak.beschrijving}</div>
              )}
              <div className="taak-card-meta">
                <span>{formatDate(taak.startdatum)} — {formatDate(taak.einddatum)}</span>
                {taak.toegewezen_aan && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span>👤</span>
                    <span>{taak.toegewezen_aan}</span>
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && gefilterd.length === 0 && (
        <div className="empty-state">Geen taken gevonden voor dit filter.</div>
      )}

      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>{editTaak ? 'Taak bewerken' : 'Nieuwe taak'}</h3>

            <div className="form-group">
              <label>Naam</label>
              <input type="text" value={formNaam} onChange={e => setFormNaam(e.target.value)} placeholder="Taaknaam" />
            </div>

            <div className="form-group">
              <label>Beschrijving</label>
              <textarea value={formBeschrijving} onChange={e => setFormBeschrijving(e.target.value)} placeholder="Beschrijving van de taak" style={{ minHeight: 80 }} />
            </div>

            <div className="form-group">
              <label>Status</label>
              <select value={formStatus} onChange={e => setFormStatus(e.target.value as TaakStatus)}>
                <option value="gepland">Gepland</option>
                <option value="bezig">Bezig</option>
                <option value="klaar">Klaar</option>
              </select>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label>Startdatum</label>
                <input type="date" value={formStart} onChange={e => setFormStart(e.target.value)} />
              </div>
              <div className="form-group">
                <label>Einddatum</label>
                <input type="date" value={formEind} onChange={e => setFormEind(e.target.value)} />
              </div>
            </div>

            <div className="form-group">
              <label>Toegewezen aan</label>
              {alleBedrijven.length > 0 ? (
                <select
                  value={formToegewezen}
                  onChange={e => setFormToegewezen(e.target.value)}
                >
                  <option value="">— Kies bedrijf —</option>
                  {alleBedrijven.map(b => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                  <option value="__nieuw__">+ Nieuw bedrijf invoeren</option>
                </select>
              ) : null}
              {(alleBedrijven.length === 0 || formToegewezen === '__nieuw__') && (
                <input
                  type="text"
                  value={formToegewezen === '__nieuw__' ? '' : formToegewezen}
                  onChange={e => setFormToegewezen(e.target.value)}
                  placeholder="Naam bedrijf of medewerker"
                />
              )}
            </div>

            <div className="modal-actions">
              {editTaak && (
                <button className="danger" onClick={handleDelete}>Verwijderen</button>
              )}
              <button className="secondary" onClick={() => setModalOpen(false)}>Annuleren</button>
              <button className="primary" onClick={handleSave}>Opslaan</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Taken
