import { useState, useEffect, useCallback } from 'react'
import { type Taak, type TaakStatus, takenApi, loadTakenFromStorage, saveTakenToStorage } from '../hooks/useApi'

const demoTaken: Taak[] = [
  { id: '1', naam: 'Funderingswerk', beschrijving: 'Graven en storten van de fundering', status: 'klaar', startdatum: '2026-03-01', einddatum: '2026-03-14', toegewezen_aan: 'Jan de Vries' },
  { id: '2', naam: 'Ruwbouw muren', beschrijving: 'Metselwerk voor alle draagmuren', status: 'bezig', startdatum: '2026-03-15', einddatum: '2026-04-10', toegewezen_aan: 'Pieter Bakker' },
  { id: '3', naam: 'Dakconstructie', beschrijving: 'Plaatsen van dakspanten en dakbedekking', status: 'gepland', startdatum: '2026-04-11', einddatum: '2026-04-25', toegewezen_aan: 'Klaas Mulder' },
  { id: '4', naam: 'Elektriciteit aanleggen', beschrijving: 'Bekabeling en groepenkast installeren', status: 'gepland', startdatum: '2026-04-15', einddatum: '2026-05-01', toegewezen_aan: 'Ahmed El Amrani' },
  { id: '5', naam: 'Loodgieterij', beschrijving: 'Waterleiding en riolering aansluiten', status: 'gepland', startdatum: '2026-04-20', einddatum: '2026-05-05', toegewezen_aan: 'Willem Jansen' },
  { id: '6', naam: 'Afwerking & schilderwerk', beschrijving: 'Stucwerk, schilderen en vloeren leggen', status: 'gepland', startdatum: '2026-05-06', einddatum: '2026-05-30', toegewezen_aan: 'Sophie van Dijk' },
]

function loadTaken(): Taak[] {
  const stored = loadTakenFromStorage()
  if (stored.length > 0) return stored
  // Seed demo data on first load
  saveTakenToStorage(demoTaken)
  return demoTaken
}

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
  const [taken, setTaken] = useState<Taak[]>(loadTaken)
  const [filter, setFilter] = useState<FilterStatus>('alles')
  const [modalOpen, setModalOpen] = useState(false)
  const [editTaak, setEditTaak] = useState<Taak | null>(null)

  // Form state
  const [formNaam, setFormNaam] = useState('')
  const [formBeschrijving, setFormBeschrijving] = useState('')
  const [formStatus, setFormStatus] = useState<TaakStatus>('gepland')
  const [formStart, setFormStart] = useState('')
  const [formEind, setFormEind] = useState('')
  const [formToegewezen, setFormToegewezen] = useState('')

  useEffect(() => { saveTakenToStorage(taken) }, [taken])

  // Refresh when page regains focus (e.g. after creating tasks in Chat)
  const refreshFromStorage = useCallback(() => {
    const stored = loadTakenFromStorage()
    if (stored.length > 0) setTaken(stored)
  }, [])

  useEffect(() => {
    window.addEventListener('focus', refreshFromStorage)
    window.addEventListener('storage', refreshFromStorage)
    return () => {
      window.removeEventListener('focus', refreshFromStorage)
      window.removeEventListener('storage', refreshFromStorage)
    }
  }, [refreshFromStorage])

  const filtered = filter === 'alles' ? taken : taken.filter(t => t.status === filter)

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

  function handleSave() {
    if (!formNaam.trim()) return

    if (editTaak) {
      setTaken(prev => prev.map(t =>
        t.id === editTaak.id
          ? { ...t, naam: formNaam, beschrijving: formBeschrijving, status: formStatus, startdatum: formStart, einddatum: formEind, toegewezen_aan: formToegewezen }
          : t
      ))
    } else {
      const newTaak: Taak = {
        id: crypto.randomUUID(),
        naam: formNaam,
        beschrijving: formBeschrijving,
        status: formStatus,
        startdatum: formStart,
        einddatum: formEind,
        toegewezen_aan: formToegewezen,
      }
      setTaken(prev => [...prev, newTaak])
      // Fire-and-forget sync to ingestion API
      takenApi.aanmaken(newTaak).catch(() => {})
    }
    setModalOpen(false)
  }

  function handleDelete() {
    if (!editTaak) return
    setTaken(prev => prev.filter(t => t.id !== editTaak.id))
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

      <div className="filter-bar">
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
        <button className="primary" onClick={openAdd}>+ Nieuwe taak</button>
      </div>

      <div className="grid-2">
        {filtered.map(taak => (
          <div key={taak.id} className="taak-card" onClick={() => openEdit(taak)}>
            <div className="taak-card-header">
              <span className="taak-card-naam">{taak.naam}</span>
              <span className={`status-badge ${statusBadgeClass[taak.status]}`}>
                {statusLabels[taak.status]}
              </span>
            </div>
            {taak.beschrijving && (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>{taak.beschrijving}</div>
            )}
            <div className="taak-card-meta">
              <span>{formatDate(taak.startdatum)} — {formatDate(taak.einddatum)}</span>
              {taak.toegewezen_aan && <span>Toegewezen aan: {taak.toegewezen_aan}</span>}
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
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
              <input type="text" value={formToegewezen} onChange={e => setFormToegewezen(e.target.value)} placeholder="Naam medewerker" />
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
