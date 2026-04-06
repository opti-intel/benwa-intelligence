import { useState, useEffect, useCallback } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../hooks/useApi'

interface Gebruiker {
  id: string
  naam: string
  email: string
  rol: 'admin' | 'aannemer' | 'vakman' | 'medewerker'
  bedrijf: string
  actief: boolean
  aangemaakt_op: string
}

interface AuditRegel {
  id: string
  gebruiker_naam: string
  gebruiker_email: string
  actie: string
  details: string
  ip_adres: string
  tijdstip: string
}

// Wachtwoordsterkte check (zelfde regels als backend)
function checkWachtwoord(w: string): { geldig: boolean; fouten: string[] } {
  const fouten: string[] = []
  if (w.length < 8) fouten.push('Minimaal 8 tekens')
  if (!/[A-Z]/.test(w)) fouten.push('Minimaal 1 hoofdletter')
  if (!/[0-9]/.test(w)) fouten.push('Minimaal 1 cijfer')
  return { geldig: fouten.length === 0, fouten }
}

function WachtwoordHint({ wachtwoord }: { wachtwoord: string }) {
  if (!wachtwoord) return null
  const { geldig, fouten } = checkWachtwoord(wachtwoord)
  return (
    <div style={{ marginTop: 6, fontSize: 12 }}>
      {geldig ? (
        <span style={{ color: 'var(--green)', fontWeight: 600 }}>✓ Wachtwoord voldoet aan de eisen</span>
      ) : (
        fouten.map(f => (
          <div key={f} style={{ color: 'var(--red)' }}>✗ {f}</div>
        ))
      )}
    </div>
  )
}

const ACTIE_LABELS: Record<string, { label: string; kleur: string; bg: string }> = {
  login_geslaagd:           { label: 'Ingelogd',            kleur: '#1a6b42', bg: '#e6f5ee' },
  login_mislukt:            { label: 'Inlogpoging mislukt', kleur: '#b94040', bg: '#fdecea' },
  gebruiker_aangemaakt:     { label: 'Account aangemaakt',  kleur: '#1a6a7a', bg: '#e6f4f7' },
  gebruiker_bijgewerkt:     { label: 'Account bijgewerkt',  kleur: '#7a5a1a', bg: '#fdf5e6' },
  gebruiker_verwijderd:     { label: 'Account verwijderd',  kleur: '#b94040', bg: '#fdecea' },
  wachtwoord_reset:         { label: 'Wachtwoord reset',    kleur: '#4a3a8a', bg: '#eeebfa' },
  eigen_wachtwoord_gewijzigd:{ label: 'Eigen wachtwoord',   kleur: '#4a3a8a', bg: '#eeebfa' },
  pdf_geupload:             { label: 'PDF geüpload',         kleur: '#1a6a7a', bg: '#e6f4f7' },
}

function AuditBadge({ actie }: { actie: string }) {
  const stijl = ACTIE_LABELS[actie] || { label: actie, kleur: 'var(--text-sub)', bg: 'var(--bg)' }
  return (
    <span style={{
      padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
      background: stijl.bg, color: stijl.kleur,
    }}>
      {stijl.label}
    </span>
  )
}

function Gebruikers() {
  const [tab, setTab] = useState<'accounts' | 'auditlog'>('accounts')
  const [gebruikers, setGebruikers] = useState<Gebruiker[]>([])
  const [auditLog, setAuditLog] = useState<AuditRegel[]>([])
  const [laden, setLaden] = useState(true)
  const [auditLaden, setAuditLaden] = useState(false)

  const [modalOpen, setModalOpen] = useState(false)
  const [wachtwoordModal, setWachtwoordModal] = useState<Gebruiker | null>(null)
  const [nieuwWachtwoord, setNieuwWachtwoord] = useState('')
  const [wachtwoordFout, setWachtwoordFout] = useState('')

  // Nieuw account form
  const [formNaam, setFormNaam] = useState('')
  const [formEmail, setFormEmail] = useState('')
  const [formWachtwoord, setFormWachtwoord] = useState('')
  const [formRol, setFormRol] = useState<'admin' | 'aannemer' | 'vakman' | 'medewerker'>('vakman')
  const [formBedrijf, setFormBedrijf] = useState('')
  const [formBedrijfAnders, setFormBedrijfAnders] = useState('')
  const [formFout, setFormFout] = useState('')

  const laadGebruikers = useCallback(async () => {
    setLaden(true)
    try {
      const data = await apiGet<Gebruiker[]>('/api/ingestion/auth/gebruikers')
      setGebruikers(data)
    } catch { /* keep state */ }
    finally { setLaden(false) }
  }, [])

  const laadAuditLog = useCallback(async () => {
    setAuditLaden(true)
    try {
      const data = await apiGet<AuditRegel[]>('/api/ingestion/auth/audit-log')
      setAuditLog(data)
    } catch { /* keep state */ }
    finally { setAuditLaden(false) }
  }, [])

  useEffect(() => { laadGebruikers() }, [laadGebruikers])

  useEffect(() => {
    if (tab === 'auditlog') laadAuditLog()
  }, [tab, laadAuditLog])

  async function maakAan() {
    setFormFout('')
    const bedrijfNaam = formBedrijf === '__anders__' ? formBedrijfAnders.trim() : formBedrijf
    if (!formNaam || !formEmail || !formWachtwoord) {
      setFormFout('Vul alle verplichte velden in')
      return
    }
    const { geldig, fouten } = checkWachtwoord(formWachtwoord)
    if (!geldig) {
      setFormFout(`Wachtwoord voldoet niet: ${fouten.join(', ')}`)
      return
    }
    try {
      await apiPost('/api/ingestion/auth/gebruikers', {
        naam: formNaam,
        email: formEmail,
        wachtwoord: formWachtwoord,
        rol: formRol,
        bedrijf: bedrijfNaam,
      })
      setModalOpen(false)
      setFormNaam(''); setFormEmail(''); setFormWachtwoord('')
      setFormBedrijf(''); setFormBedrijfAnders(''); setFormRol('vakman')
      laadGebruikers()
    } catch (err) {
      setFormFout(err instanceof Error ? err.message : 'Aanmaken mislukt')
    }
  }

  async function toggleActief(g: Gebruiker) {
    await apiPatch(`/api/ingestion/auth/gebruikers/${g.id}`, { actief: !g.actief })
    laadGebruikers()
  }

  async function verwijder(g: Gebruiker) {
    if (!confirm(`Gebruiker "${g.naam}" verwijderen? Dit kan niet ongedaan worden.`)) return
    await apiDelete(`/api/ingestion/auth/gebruikers/${g.id}`)
    laadGebruikers()
  }

  async function resetWachtwoord() {
    if (!wachtwoordModal || !nieuwWachtwoord) return
    setWachtwoordFout('')
    const { geldig, fouten } = checkWachtwoord(nieuwWachtwoord)
    if (!geldig) {
      setWachtwoordFout(fouten.join(' • '))
      return
    }
    try {
      await apiPost(`/api/ingestion/auth/gebruikers/${wachtwoordModal.id}/wachtwoord`, {
        nieuw_wachtwoord: nieuwWachtwoord,
      })
      setWachtwoordModal(null)
      setNieuwWachtwoord('')
    } catch (err) {
      setWachtwoordFout(err instanceof Error ? err.message : 'Opslaan mislukt')
    }
  }

  function formatDatum(iso: string) {
    return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  function formatTijdstip(iso: string) {
    return new Date(iso).toLocaleString('nl-NL', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  const tabStijl = (actief: boolean) => ({
    padding: '8px 18px',
    border: 'none',
    borderBottom: actief ? '2px solid var(--navy)' : '2px solid transparent',
    background: 'none',
    fontWeight: actief ? 700 : 500,
    color: actief ? 'var(--navy)' : 'var(--text-sub)',
    cursor: 'pointer',
    fontSize: 14,
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Gebruikers & Beveiliging</h2>
          <p>Beheer accounts, toegangsrechten en bekijk activiteitslog</p>
        </div>
        {tab === 'accounts' && (
          <button className="primary" style={{ marginLeft: 'auto' }} onClick={() => setModalOpen(true)}>
            + Nieuw account
          </button>
        )}
        {tab === 'auditlog' && (
          <button className="secondary" style={{ marginLeft: 'auto' }} onClick={laadAuditLog}>
            ↺ Vernieuwen
          </button>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 20 }}>
        <button style={tabStijl(tab === 'accounts')} onClick={() => setTab('accounts')}>
          Accounts
        </button>
        <button style={tabStijl(tab === 'auditlog')} onClick={() => setTab('auditlog')}>
          Activiteitslog
        </button>
      </div>

      {/* === ACCOUNTS TAB === */}
      {tab === 'accounts' && (
        laden ? (
          <div className="empty-state">Laden...</div>
        ) : (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table>
              <thead>
                <tr>
                  <th>Naam</th>
                  <th>E-mail</th>
                  <th>Bedrijf</th>
                  <th>Rol</th>
                  <th>Status</th>
                  <th>Aangemaakt</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {gebruikers.map(g => (
                  <tr key={g.id}>
                    <td style={{ fontWeight: 600 }}>{g.naam}</td>
                    <td style={{ color: 'var(--text-sub)' }}>{g.email}</td>
                    <td>{g.bedrijf || '—'}</td>
                    <td>
                      <span style={{
                        padding: '3px 9px', borderRadius: 5, fontSize: 12, fontWeight: 600,
                        background: (g.rol === 'admin' || g.rol === 'aannemer') ? 'rgba(30,63,110,0.1)' : g.rol === 'vakman' ? 'rgba(58,168,193,0.12)' : 'var(--bg)',
                        color: (g.rol === 'admin' || g.rol === 'aannemer') ? 'var(--navy)' : g.rol === 'vakman' ? 'var(--teal)' : 'var(--text-sub)',
                      }}>
                        {g.rol === 'admin' ? 'Beheerder' : g.rol === 'aannemer' ? 'Aannemer' : g.rol === 'vakman' ? 'Vakman' : 'Medewerker'}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        padding: '3px 9px', borderRadius: 5, fontSize: 12, fontWeight: 600,
                        background: g.actief ? 'var(--green-bg)' : 'var(--red-bg)',
                        color: g.actief ? 'var(--green)' : 'var(--red)',
                      }}>
                        {g.actief ? 'Actief' : 'Inactief'}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{formatDatum(g.aangemaakt_op)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button className="secondary" style={{ fontSize: 12, padding: '5px 10px' }}
                          onClick={() => { setWachtwoordModal(g); setNieuwWachtwoord(''); setWachtwoordFout('') }}>
                          Wachtwoord
                        </button>
                        <button className="secondary" style={{ fontSize: 12, padding: '5px 10px' }}
                          onClick={() => toggleActief(g)}>
                          {g.actief ? 'Deactiveer' : 'Activeer'}
                        </button>
                        <button className="danger" style={{ fontSize: 12, padding: '5px 10px' }}
                          onClick={() => verwijder(g)}>
                          Verwijder
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {gebruikers.length === 0 && (
              <div className="empty-state">Nog geen gebruikers aangemaakt.</div>
            )}
          </div>
        )
      )}

      {/* === AUDIT LOG TAB === */}
      {tab === 'auditlog' && (
        auditLaden ? (
          <div className="empty-state">Laden...</div>
        ) : (
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table>
              <thead>
                <tr>
                  <th>Tijdstip</th>
                  <th>Gebruiker</th>
                  <th>Actie</th>
                  <th>Details</th>
                  <th>IP-adres</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map(r => (
                  <tr key={r.id}>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12, whiteSpace: 'nowrap' }}>
                      {formatTijdstip(r.tijdstip)}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{r.gebruiker_naam}</div>
                      {r.gebruiker_email && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.gebruiker_email}</div>
                      )}
                    </td>
                    <td><AuditBadge actie={r.actie} /></td>
                    <td style={{ fontSize: 13, color: 'var(--text-sub)' }}>{r.details}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      {r.ip_adres || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {auditLog.length === 0 && (
              <div className="empty-state">Nog geen activiteit geregistreerd.</div>
            )}
          </div>
        )
      )}

      {/* Nieuw account modal */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Nieuw account aanmaken</h3>
            <div className="form-group">
              <label>Naam *</label>
              <input type="text" value={formNaam} onChange={e => setFormNaam(e.target.value)} placeholder="Voor- en achternaam" />
            </div>
            <div className="form-group">
              <label>E-mailadres *</label>
              <input type="email" value={formEmail} onChange={e => setFormEmail(e.target.value)} placeholder="naam@bedrijf.nl" />
            </div>
            <div className="form-group">
              <label>Wachtwoord *</label>
              <input type="password" value={formWachtwoord} onChange={e => setFormWachtwoord(e.target.value)}
                placeholder="Min. 8 tekens, 1 hoofdletter, 1 cijfer" />
              <WachtwoordHint wachtwoord={formWachtwoord} />
            </div>
            <div className="form-group">
              <label>Rol</label>
              <select value={formRol} onChange={e => setFormRol(e.target.value as 'admin' | 'aannemer' | 'vakman' | 'medewerker')}>
                <option value="vakman">Vakman</option>
                <option value="aannemer">Aannemer</option>
                <option value="admin">Beheerder</option>
              </select>
            </div>
            <div className="form-group">
              <label>Bedrijf</label>
              <select value={formBedrijf} onChange={e => setFormBedrijf(e.target.value)}>
                <option value="">Kies een bedrijf…</option>
                {[...new Set(gebruikers.map(g => g.bedrijf).filter(Boolean))].sort().map(b => (
                  <option key={b} value={b}>{b}</option>
                ))}
                <option value="__anders__">+ Nieuw bedrijf toevoegen</option>
              </select>
            </div>
            {formBedrijf === '__anders__' && (
              <div className="form-group">
                <label>Naam nieuw bedrijf</label>
                <input type="text" value={formBedrijfAnders} onChange={e => setFormBedrijfAnders(e.target.value)}
                  placeholder="bijv. Bakker Loodgieters BV" autoFocus />
              </div>
            )}
            {formFout && <div className="error-message">{formFout}</div>}
            <div className="modal-actions">
              <button className="secondary" onClick={() => setModalOpen(false)}>Annuleren</button>
              <button className="primary" onClick={maakAan}>Account aanmaken</button>
            </div>
          </div>
        </div>
      )}

      {/* Wachtwoord reset modal */}
      {wachtwoordModal && (
        <div className="modal-overlay" onClick={() => setWachtwoordModal(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Wachtwoord wijzigen</h3>
            <p style={{ fontSize: 14, color: 'var(--text-sub)', marginBottom: 16 }}>
              Nieuw wachtwoord instellen voor <strong>{wachtwoordModal.naam}</strong>
            </p>
            <div className="form-group">
              <label>Nieuw wachtwoord</label>
              <input type="password" value={nieuwWachtwoord}
                onChange={e => setNieuwWachtwoord(e.target.value)}
                placeholder="Min. 8 tekens, 1 hoofdletter, 1 cijfer"
                autoFocus />
              <WachtwoordHint wachtwoord={nieuwWachtwoord} />
            </div>
            {wachtwoordFout && <div className="error-message">{wachtwoordFout}</div>}
            <div className="modal-actions">
              <button className="secondary" onClick={() => setWachtwoordModal(null)}>Annuleren</button>
              <button className="primary" onClick={resetWachtwoord} disabled={!nieuwWachtwoord}>
                Opslaan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Gebruikers
