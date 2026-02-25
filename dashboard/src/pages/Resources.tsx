import { useState, useEffect } from 'react'
import { type Resource, type ResourceType, resourcesApi } from '../hooks/useApi'

const STORAGE_KEY = 'benwa-resources'

const demoResources: Resource[] = [
  { id: '1', naam: 'Jan de Vries', type: 'persoon', beschikbaarheid: true, toegewezen_taken: ['Funderingswerk'] },
  { id: '2', naam: 'Pieter Bakker', type: 'persoon', beschikbaarheid: true, toegewezen_taken: ['Ruwbouw muren'] },
  { id: '3', naam: 'Klaas Mulder', type: 'persoon', beschikbaarheid: false, toegewezen_taken: [] },
  { id: '4', naam: 'Hijskraan #1', type: 'apparatuur', beschikbaarheid: true, toegewezen_taken: ['Dakconstructie'] },
  { id: '5', naam: 'Betonmixer', type: 'apparatuur', beschikbaarheid: true, toegewezen_taken: ['Funderingswerk'] },
]

function loadResources(): Resource[] {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    try { return JSON.parse(stored) } catch { /* fall through */ }
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(demoResources))
  return demoResources
}

function saveResources(resources: Resource[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(resources))
}

type FilterType = 'alles' | ResourceType

function Resources() {
  const [resources, setResources] = useState<Resource[]>(loadResources)
  const [filter, setFilter] = useState<FilterType>('alles')
  const [modalOpen, setModalOpen] = useState(false)

  // Form state
  const [formNaam, setFormNaam] = useState('')
  const [formType, setFormType] = useState<ResourceType>('persoon')
  const [formBeschikbaar, setFormBeschikbaar] = useState(true)

  // Try to fetch from API on mount, fallback to localStorage
  useEffect(() => {
    resourcesApi.lijst()
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setResources(data)
          saveResources(data)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => { saveResources(resources) }, [resources])

  const filtered = filter === 'alles' ? resources : resources.filter(r => r.type === filter)

  function openAdd() {
    setFormNaam('')
    setFormType('persoon')
    setFormBeschikbaar(true)
    setModalOpen(true)
  }

  function handleSave() {
    if (!formNaam.trim()) return

    const newResource: Resource = {
      id: crypto.randomUUID(),
      naam: formNaam,
      type: formType,
      beschikbaarheid: formBeschikbaar,
      toegewezen_taken: [],
    }
    setResources(prev => [...prev, newResource])
    // Fire-and-forget sync to beliefs API
    resourcesApi.aanmaken(newResource).catch(() => {})
    setModalOpen(false)
  }

  const filters: { key: FilterType; label: string }[] = [
    { key: 'alles', label: 'Alles' },
    { key: 'persoon', label: 'Personen' },
    { key: 'apparatuur', label: 'Apparatuur' },
  ]

  return (
    <div>
      <div className="page-header">
        <h2>Resources</h2>
        <p>Medewerkers en apparatuur beheren</p>
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
        <button className="primary" onClick={openAdd}>+ Toevoegen</button>
      </div>

      <div className="grid-2">
        {filtered.map(resource => (
          <div key={resource.id} className="resource-card">
            <div className="resource-card-header">
              <span className="resource-card-naam">{resource.naam}</span>
              <span className={`status-badge ${resource.type === 'persoon' ? 'info' : 'warning'}`}>
                {resource.type === 'persoon' ? 'Persoon' : 'Apparatuur'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
              <span className={`status-dot ${resource.beschikbaarheid ? 'online' : 'offline'}`} />
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {resource.beschikbaarheid ? 'Beschikbaar' : 'Niet beschikbaar'}
              </span>
            </div>
            {resource.toegewezen_taken.length > 0 && (
              <div className="resource-card-meta">
                Toegewezen: {resource.toegewezen_taken.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="empty-state">Geen resources gevonden voor dit filter.</div>
      )}

      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Resource toevoegen</h3>

            <div className="form-group">
              <label>Naam</label>
              <input type="text" value={formNaam} onChange={e => setFormNaam(e.target.value)} placeholder="Naam van resource" />
            </div>

            <div className="form-group">
              <label>Type</label>
              <select value={formType} onChange={e => setFormType(e.target.value as ResourceType)}>
                <option value="persoon">Persoon</option>
                <option value="apparatuur">Apparatuur</option>
              </select>
            </div>

            <div className="form-group">
              <label>Beschikbaarheid</label>
              <div className="checkbox-group">
                <input type="checkbox" checked={formBeschikbaar} onChange={e => setFormBeschikbaar(e.target.checked)} />
                <span style={{ fontSize: 14 }}>Beschikbaar</span>
              </div>
            </div>

            <div className="modal-actions">
              <button className="secondary" onClick={() => setModalOpen(false)}>Annuleren</button>
              <button className="primary" onClick={handleSave}>Opslaan</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Resources
