import { useState } from 'react'
import { Search, ChevronDown, ChevronRight, User, Wrench, Plus, X } from 'lucide-react'

interface Resource {
  id: string
  naam: string
  type: 'persoon' | 'apparatuur'
  bedrijf: string
  functie?: string
  beschikbaarheid: boolean
  toegewezen_taken: string[]
}

const DEMO: Resource[] = [
  { id: '1',  naam: 'Ahmed Yilmaz',    type: 'persoon',    bedrijf: 'Derhaag BV',      functie: 'Tegelzetter',   beschikbaarheid: false, toegewezen_taken: ['Tegelwerk badkamer'] },
  { id: '2',  naam: 'Kevin Derhaag',   type: 'persoon',    bedrijf: 'Derhaag BV',      functie: 'Uitvoerder',    beschikbaarheid: true,  toegewezen_taken: [] },
  { id: '3',  naam: 'Stucmachine #1',  type: 'apparatuur', bedrijf: 'Derhaag BV',      functie: 'Apparatuur',    beschikbaarheid: true,  toegewezen_taken: ['Stucwerk woonkamer'] },
  { id: '4',  naam: 'Jan de Vries',    type: 'persoon',    bedrijf: 'De Vries Bouw',   functie: 'Metselaar',     beschikbaarheid: true,  toegewezen_taken: ['Funderingswerk', 'Ruwbouw muren'] },
  { id: '5',  naam: 'Pieter de Vries', type: 'persoon',    bedrijf: 'De Vries Bouw',   functie: 'Timmerman',     beschikbaarheid: true,  toegewezen_taken: ['Dakconstructie'] },
  { id: '6',  naam: 'Hijskraan #1',    type: 'apparatuur', bedrijf: 'De Vries Bouw',   functie: 'Apparatuur',    beschikbaarheid: true,  toegewezen_taken: ['Dakconstructie'] },
  { id: '7',  naam: 'Betonmixer #2',   type: 'apparatuur', bedrijf: 'De Vries Bouw',   functie: 'Apparatuur',    beschikbaarheid: false, toegewezen_taken: [] },
  { id: '8',  naam: 'Pieter Smit',     type: 'persoon',    bedrijf: 'Smit Tegels BV',  functie: 'Tegelzetter',   beschikbaarheid: true,  toegewezen_taken: [] },
  { id: '9',  naam: 'Lisa Smit',       type: 'persoon',    bedrijf: 'Smit Tegels BV',  functie: 'Projectleider', beschikbaarheid: true,  toegewezen_taken: ['Tegelwerk keuken'] },
  { id: '10', naam: 'Klaas Mulder',    type: 'persoon',    bedrijf: 'Elektra Noord',   functie: 'Elektricien',   beschikbaarheid: false, toegewezen_taken: ['Elektra begane grond'] },
  { id: '11', naam: 'Tom Mulder',      type: 'persoon',    bedrijf: 'Elektra Noord',   functie: 'Monteur',       beschikbaarheid: true,  toegewezen_taken: [] },
]

const STORAGE_KEY = 'benwa-resources-v2'

function laadResources(): Resource[] {
  try { const s = localStorage.getItem(STORAGE_KEY); return s ? JSON.parse(s) : DEMO }
  catch { return DEMO }
}

export default function Resources() {
  const [resources, setResources] = useState<Resource[]>(laadResources)
  const [zoekterm, setZoekterm] = useState('')
  const [typeFilter, setTypeFilter] = useState<'alles' | 'persoon' | 'apparatuur'>('alles')
  const [beschikbaarFilter, setBeschikbaarFilter] = useState<'alles' | 'beschikbaar' | 'bezet'>('alles')
  const [uitgeklapteBedrijven, setUitgeklapteBedrijven] = useState<Record<string, boolean>>({})
  const [modalOpen, setModalOpen] = useState(false)

  // Form
  const [formNaam, setFormNaam] = useState('')
  const [formType, setFormType] = useState<'persoon' | 'apparatuur'>('persoon')
  const [formFunctie, setFormFunctie] = useState('')
  const [formBedrijf, setFormBedrijf] = useState('')
  const [formAndersBedrijf, setFormAndersBedrijf] = useState('')
  const [formBeschikbaar, setFormBeschikbaar] = useState(true)

  const gefilterd = resources.filter(r => {
    const z = zoekterm.toLowerCase()
    const matchZoek = !z || r.naam.toLowerCase().includes(z) || r.bedrijf.toLowerCase().includes(z) || (r.functie ?? '').toLowerCase().includes(z)
    const matchType = typeFilter === 'alles' || r.type === typeFilter
    const matchB = beschikbaarFilter === 'alles' || (beschikbaarFilter === 'beschikbaar' ? r.beschikbaarheid : !r.beschikbaarheid)
    return matchZoek && matchType && matchB
  })

  const perBedrijf: Record<string, Resource[]> = {}
  gefilterd.forEach(r => { if (!perBedrijf[r.bedrijf]) perBedrijf[r.bedrijf] = []; perBedrijf[r.bedrijf].push(r) })
  const bedrijven = Object.keys(perBedrijf).sort()

  function isOpen(naam: string) { return uitgeklapteBedrijven[naam] !== false }

  function handleSave() {
    const bedrijfNaam = formBedrijf === '__anders__' ? formAndersBedrijf.trim() : formBedrijf
    if (!formNaam.trim() || !bedrijfNaam) return
    const updated = [...resources, {
      id: crypto.randomUUID(), naam: formNaam.trim(), type: formType,
      bedrijf: bedrijfNaam, functie: formFunctie.trim() || undefined,
      beschikbaarheid: formBeschikbaar, toegewezen_taken: [],
    }]
    setResources(updated)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    setModalOpen(false)
    setFormNaam(''); setFormFunctie(''); setFormBedrijf(''); setFormAndersBedrijf('')
  }

  const bestaandeBedrijven = [...new Set(resources.map(r => r.bedrijf))].sort()

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <h2>Resources</h2>
          <p>{resources.length} resources · {bestaandeBedrijven.length} bedrijven · {resources.filter(r => r.beschikbaarheid).length} beschikbaar</p>
        </div>
        <button className="primary" onClick={() => setModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Plus size={14} /> Toevoegen
        </button>
      </div>

      {/* Zoek + filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 180 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input type="text" placeholder="Zoek op naam, bedrijf of functie…" value={zoekterm} onChange={e => setZoekterm(e.target.value)}
            style={{ width: '100%', padding: '9px 12px 9px 32px', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, background: 'var(--bg-white)', outline: 'none', boxSizing: 'border-box' }} />
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value as typeof typeFilter)}
          style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, background: 'var(--bg-white)', cursor: 'pointer' }}>
          <option value="alles">Alle types</option>
          <option value="persoon">Personen</option>
          <option value="apparatuur">Apparatuur</option>
        </select>
        <select value={beschikbaarFilter} onChange={e => setBeschikbaarFilter(e.target.value as typeof beschikbaarFilter)}
          style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, background: 'var(--bg-white)', cursor: 'pointer' }}>
          <option value="alles">Alle beschikbaarheid</option>
          <option value="beschikbaar">Beschikbaar</option>
          <option value="bezet">Bezet</option>
        </select>
      </div>

      {/* Resources per bedrijf */}
      {bedrijven.length === 0 ? (
        <div className="empty-state">Geen resources gevonden.</div>
      ) : bedrijven.map(bedrijf => {
        const items = perBedrijf[bedrijf]
        const open = isOpen(bedrijf)
        const aantalBeschikbaar = items.filter(r => r.beschikbaarheid).length
        return (
          <div key={bedrijf} className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
            <button onClick={() => setUitgeklapteBedrijven(prev => ({ ...prev, [bedrijf]: !isOpen(bedrijf) }))}
              style={{ width: '100%', padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', borderBottom: open ? '1px solid var(--border)' : 'none' }}>
              {open ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
              <div style={{ flex: 1 }}>
                <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>{bedrijf}</span>
                <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--text-muted)' }}>{items.length} {items.length === 1 ? 'resource' : 'resources'}</span>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 12, flexShrink: 0, background: aantalBeschikbaar > 0 ? 'var(--green-bg)' : 'var(--red-bg)', color: aantalBeschikbaar > 0 ? 'var(--green)' : 'var(--red)' }}>
                {aantalBeschikbaar}/{items.length} beschikbaar
              </span>
            </button>

            {open && items.map((r, i) => (
              <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 18px', borderBottom: i < items.length - 1 ? '1px solid var(--border)' : 'none', background: 'var(--bg-white)' }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', flexShrink: 0, background: r.type === 'persoon' ? 'var(--blue-bg)' : 'var(--yellow-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {r.type === 'persoon' ? <User size={16} color="var(--blue)" /> : <Wrench size={16} color="var(--yellow)" />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{r.naam}</div>
                  {r.functie && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.functie}</div>}
                  {r.toegewezen_taken.length > 0 && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>📋 {r.toegewezen_taken.join(', ')}</div>}
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 12, flexShrink: 0, background: r.beschikbaarheid ? 'var(--green-bg)' : 'var(--red-bg)', color: r.beschikbaarheid ? 'var(--green)' : 'var(--red)' }}>
                  {r.beschikbaarheid ? 'Beschikbaar' : 'Bezet'}
                </span>
              </div>
            ))}
          </div>
        )
      })}

      {/* Modal */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ margin: 0, flex: 1 }}>Resource toevoegen</h3>
              <button onClick={() => setModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={18} /></button>
            </div>
            <div className="form-group">
              <label>Naam *</label>
              <input type="text" value={formNaam} onChange={e => setFormNaam(e.target.value)} placeholder="Naam van persoon of apparatuur" />
            </div>
            <div className="grid-2">
              <div className="form-group">
                <label>Type</label>
                <select value={formType} onChange={e => setFormType(e.target.value as 'persoon' | 'apparatuur')}>
                  <option value="persoon">Persoon</option>
                  <option value="apparatuur">Apparatuur</option>
                </select>
              </div>
              <div className="form-group">
                <label>Functie</label>
                <input type="text" value={formFunctie} onChange={e => setFormFunctie(e.target.value)} placeholder="bijv. Tegelzetter" />
              </div>
            </div>
            <div className="form-group">
              <label>Bedrijf *</label>
              <select value={formBedrijf} onChange={e => setFormBedrijf(e.target.value)}>
                <option value="">Kies een bedrijf…</option>
                {bestaandeBedrijven.map(b => <option key={b} value={b}>{b}</option>)}
                <option value="__anders__">+ Nieuw bedrijf toevoegen</option>
              </select>
            </div>
            {formBedrijf === '__anders__' && (
              <div className="form-group">
                <label>Naam nieuw bedrijf *</label>
                <input type="text" value={formAndersBedrijf} onChange={e => setFormAndersBedrijf(e.target.value)} placeholder="bijv. Bakker Loodgieters BV" autoFocus />
              </div>
            )}
            <div className="form-group">
              <div className="checkbox-group">
                <input type="checkbox" checked={formBeschikbaar} onChange={e => setFormBeschikbaar(e.target.checked)} />
                <span style={{ fontSize: 14 }}>Momenteel beschikbaar</span>
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
