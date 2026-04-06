import { useState, useEffect, useRef, useCallback } from 'react'
import { MessageCircle, Send, Search, Users, HardHat, ChevronDown, ChevronRight, Bot, Sparkles, Building2 } from 'lucide-react'
import { useAuth, authHeaders } from '../hooks/useAuth'

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatGebruiker {
  id: string
  naam: string
  rol: string
  bedrijf: string
  isAI?: boolean
  isGroep?: boolean
}

interface Groep {
  id: string
  naam: string
  leden: number
  is_eigen_bedrijf: boolean
  type?: 'bedrijf' | 'custom'
}

interface GroepBericht {
  id: string
  van_id: string
  van_naam: string
  tekst: string
  tijdstip: string
}

interface Bericht {
  id: string
  van_id: string
  naar_id: string
  tekst: string
  gelezen: boolean
  tijdstip: string
}

interface AiBericht {
  id: string
  gebruiker_id: string
  rol: 'user' | 'ai'
  tekst: string
  tijdstip: string
}

// ─── AI Assistent contact (vast bovenaan) ────────────────────────────────────

const AI_CONTACT: ChatGebruiker = {
  id: 'ai-assistent',
  naam: 'Opti Intel AI',
  rol: 'ai',
  bedrijf: 'Projectassistent',
  isAI: true,
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function rolLabel(rol: string): string {
  if (rol === 'admin' || rol === 'aannemer') return 'Aannemer'
  if (rol === 'vakman') return 'Vakman'
  if (rol === 'ai') return 'AI Assistent'
  return 'Medewerker'
}

function rolGroep(rol: string): 'aannemers' | 'vakmensen' {
  return rol === 'admin' || rol === 'aannemer' ? 'aannemers' : 'vakmensen'
}

function formatTijdstip(iso: string): string {
  const d = new Date(iso)
  const nu = new Date()
  const gisteren = new Date(nu)
  gisteren.setDate(nu.getDate() - 1)
  const tijd = d.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })
  if (d.toDateString() === nu.toDateString()) return tijd
  if (d.toDateString() === gisteren.toDateString()) return `Gisteren ${tijd}`
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) + ` ${tijd}`
}

function initialen(naam: string): string {
  return naam.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
}

// ─── Avatar ──────────────────────────────────────────────────────────────────

function Avatar({ naam, rol, size = 36 }: { naam: string; rol: string; size?: number }) {
  if (rol === 'ai') {
    return (
      <div style={{
        width: size, height: size, borderRadius: '50%',
        background: 'linear-gradient(135deg, #6b5aad, #3aa8c1)',
        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Bot size={size * 0.5} />
      </div>
    )
  }
  if (rol === 'groep') {
    return (
      <div style={{
        width: size, height: size, borderRadius: '50%',
        background: 'var(--teal)',
        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Building2 size={size * 0.5} />
      </div>
    )
  }
  const bg = (rol === 'admin' || rol === 'aannemer') ? 'var(--navy-light)' : 'var(--teal)'
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: bg, color: '#fff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size * 0.35, fontWeight: 700, flexShrink: 0,
    }}>
      {initialen(naam)}
    </div>
  )
}

// ─── ContactRij ───────────────────────────────────────────────────────────────

function ContactRij({ contact, actief, ongelezen, onClick }: {
  contact: ChatGebruiker
  actief: boolean
  ongelezen: number
  onClick: () => void
}) {
  const isAI = contact.isAI
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', padding: '10px 16px', display: 'flex', alignItems: 'center',
        gap: 10,
        background: actief
          ? (isAI ? 'rgba(107,90,173,0.1)' : 'var(--blue-bg)')
          : 'transparent',
        border: 'none',
        borderLeft: actief
          ? (isAI ? '3px solid #6b5aad' : '3px solid var(--teal)')
          : '3px solid transparent',
        cursor: 'pointer', textAlign: 'left', transition: 'background 0.1s',
      }}
    >
      <Avatar naam={contact.naam} rol={contact.rol} size={36} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontWeight: ongelezen > 0 ? 700 : 500, fontSize: 13, color: 'var(--text)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          {contact.naam}
          {isAI && <Sparkles size={11} color="#6b5aad" />}
        </div>
        <div style={{
          fontSize: 11, color: isAI ? '#6b5aad' : 'var(--text-muted)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          fontWeight: isAI ? 500 : 400,
        }}>
          {contact.bedrijf || rolLabel(contact.rol)}
        </div>
      </div>
      {ongelezen > 0 && (
        <span style={{
          background: 'var(--teal)', color: '#fff',
          borderRadius: 10, fontSize: 11, fontWeight: 700, padding: '2px 7px', flexShrink: 0,
        }}>
          {ongelezen}
        </span>
      )}
    </button>
  )
}

// ─── Hoofdcomponent ──────────────────────────────────────────────────────────

export default function Chat() {
  const { gebruiker } = useAuth()
  const [contacten, setContacten] = useState<ChatGebruiker[]>([])
  const [groepen, setGroepen] = useState<Groep[]>([])
  const [actieveContact, setActieveContact] = useState<ChatGebruiker | null>(null)
  const [berichten, setBerichten] = useState<Bericht[]>([])
  const [aiBerichten, setAiBerichten] = useState<AiBericht[]>([])
  const [groepBerichten, setGroepBerichten] = useState<GroepBericht[]>([])
  const [ongelezen, setOngelezen] = useState<Record<string, number>>({})
  const [invoer, setInvoer] = useState('')
  const [zoekterm, setZoekterm] = useState('')
  const [laden, setLaden] = useState(false)
  const [aiLaden, setAiLaden] = useState(false)
  const [verzenden, setVerzenden] = useState(false)
  const [aannemersOpen, setAannemersOpen] = useState(true)
  const [vakmensOpen, setVakmensOpen] = useState(true)
  const [groepenOpen, setGroepenOpen] = useState(true)
  const [nieuweGroepOpen, setNieuweGroepOpen] = useState(false)
  const [nieuweGroepNaam, setNieuweGroepNaam] = useState('')
  const [geselecteerdeLedenIds, setGeselecteerdeLedenIds] = useState<Set<string>>(new Set())
  const [nieuweGroepFout, setNieuweGroepFout] = useState('')
  const [nieuweGroepLaden, setNieuweGroepLaden] = useState(false)
  const berichtenRef = useRef<HTMLDivElement>(null)
  const invoerRef = useRef<HTMLInputElement>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const contactRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const vorigeOngelezenRef = useRef<Record<string, number>>({})
  const contactenRef = useRef<ChatGebruiker[]>([])

  // ── Browser notificaties toestaan ───────────────────────────────────────
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  function stuurNotificatie(naam: string, tekst: string) {
    if (!('Notification' in window)) return
    if (Notification.permission !== 'granted') return
    if (document.visibilityState === 'visible') return // app is open en actief
    new Notification(`💬 Nieuw bericht van ${naam}`, {
      body: tekst.length > 80 ? tekst.slice(0, 80) + '…' : tekst,
      icon: '/opti-intel-logo.svg',
      tag: `chat-${naam}`, // voorkomt dubbele meldingen
    })
  }

  // ── Contacten + groepen ophalen + auto-refresh ──────────────────────────
  useEffect(() => {
    haalContacten()
    haalGroepen()
    haalOngelezen()
    contactRefreshRef.current = setInterval(() => {
      haalContacten()
      haalGroepen()
      haalOngelezen()
    }, 30_000)
    return () => {
      if (contactRefreshRef.current) clearInterval(contactRefreshRef.current)
    }
  }, [])

  async function haalGroepen() {
    try {
      const res = await fetch('/api/ingestion/chat/groepen', { headers: authHeaders() })
      if (res.ok) setGroepen(await res.json())
    } catch { /* stil falen */ }
  }

  async function haalContacten() {
    try {
      const res = await fetch('/api/ingestion/chat/gebruikers', { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        setContacten(data)
        contactenRef.current = data
      }
    } catch { /* stil falen */ }
  }

  async function haalOngelezen() {
    try {
      const res = await fetch('/api/ingestion/chat/ongelezen', { headers: authHeaders() })
      if (res.ok) {
        const nieuw: Record<string, number> = await res.json()
        // Vergelijk met vorige stand → stuur notificatie bij nieuwe berichten
        Object.entries(nieuw).forEach(([vanId, aantal]) => {
          const oud = vorigeOngelezenRef.current[vanId] ?? 0
          if (aantal > oud) {
            const afzender = contactenRef.current.find(c => c.id === vanId)
            if (afzender) stuurNotificatie(afzender.naam, `${aantal - oud} nieuw bericht${aantal - oud > 1 ? 'en' : ''}`)
          }
        })
        vorigeOngelezenRef.current = nieuw
        setOngelezen(nieuw)
      }
    } catch { /* stil falen */ }
  }

  // ── AI berichten ophalen ────────────────────────────────────────────────
  async function haalAiBerichten() {
    try {
      const res = await fetch('/api/ingestion/chat/ai/berichten', { headers: authHeaders() })
      if (res.ok) setAiBerichten(await res.json())
    } catch { /* stil falen */ }
  }

  // ── Groep berichten ophalen ──────────────────────────────────────────────
  async function haalGroepBerichten(groepNaam: string) {
    try {
      const res = await fetch(`/api/ingestion/chat/groepen/${encodeURIComponent(groepNaam)}/berichten`, { headers: authHeaders() })
      if (res.ok) setGroepBerichten(await res.json())
    } catch { /* stil falen */ }
  }

  // ── Reguliere berichten ophalen + polling ───────────────────────────────
  const haalBerichten = useCallback(async (contactId: string) => {
    try {
      const res = await fetch(`/api/ingestion/chat/berichten/${contactId}`, { headers: authHeaders() })
      if (res.ok) {
        setBerichten(await res.json())
        setOngelezen(prev => { const n = { ...prev }; delete n[contactId]; return n })
      }
    } catch { /* stil falen */ }
  }, [])

  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current)
    if (!actieveContact) return

    if (actieveContact.isAI) {
      setLaden(true)
      haalAiBerichten().finally(() => setLaden(false))
      return
    }

    if (actieveContact.isGroep) {
      setLaden(true)
      haalGroepBerichten(actieveContact.id).finally(() => setLaden(false))
      pollingRef.current = setInterval(() => haalGroepBerichten(actieveContact.id), 3_000)
      return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
    }

    setLaden(true)
    haalBerichten(actieveContact.id).finally(() => setLaden(false))
    pollingRef.current = setInterval(() => haalBerichten(actieveContact.id), 3_000)
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [actieveContact, haalBerichten])

  // ── Scroll naar beneden bij nieuwe berichten ─────────────────────────────
  useEffect(() => {
    if (berichtenRef.current) {
      berichtenRef.current.scrollTop = berichtenRef.current.scrollHeight
    }
  }, [berichten, aiBerichten, groepBerichten])

  // ── Contact selecteren ───────────────────────────────────────────────────
  function selecteerContact(contact: ChatGebruiker) {
    setActieveContact(contact)
    setBerichten([])
    setAiBerichten([])
    setGroepBerichten([])
    setTimeout(() => invoerRef.current?.focus(), 100)
  }

  // ── Bericht versturen ────────────────────────────────────────────────────
  async function stuurBericht(e: React.FormEvent) {
    e.preventDefault()
    if (!invoer.trim() || !actieveContact || verzenden) return
    const tekst = invoer.trim()
    setInvoer('')

    if (actieveContact.isAI) {
      // AI chat
      setAiLaden(true)
      // Voeg gebruikersvraag direct toe aan de lijst voor snelle feedback
      const tijdelijkVraag: AiBericht = {
        id: `tmp-${Date.now()}`,
        gebruiker_id: gebruiker?.id ?? '',
        rol: 'user',
        tekst,
        tijdstip: new Date().toISOString(),
      }
      setAiBerichten(prev => [...prev, tijdelijkVraag])
      try {
        const res = await fetch('/api/ingestion/chat/ai', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ tekst }),
        })
        if (res.ok) {
          const data = await res.json()
          const aiReactie: AiBericht = {
            id: `ai-${Date.now()}`,
            gebruiker_id: 'ai',
            rol: 'ai',
            tekst: data.antwoord,
            tijdstip: data.tijdstip,
          }
          setAiBerichten(prev => [...prev, aiReactie])
        }
      } catch { /* stil falen */ } finally {
        setAiLaden(false)
      }
      return
    }

    // Groep chat
    if (actieveContact.isGroep) {
      setVerzenden(true)
      try {
        const res = await fetch(`/api/ingestion/chat/groepen/${encodeURIComponent(actieveContact.id)}/berichten`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ tekst }),
        })
        if (res.ok) { const nieuw = await res.json(); setGroepBerichten(prev => [...prev, nieuw]) }
      } catch { /* stil falen */ } finally {
        setVerzenden(false)
      }
      return
    }

    // Reguliere chat
    setVerzenden(true)
    try {
      const res = await fetch('/api/ingestion/chat/berichten', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ naar_id: actieveContact.id, tekst }),
      })
      if (res.ok) { const nieuw = await res.json(); setBerichten(prev => [...prev, nieuw]) }
    } catch { /* stil falen */ } finally {
      setVerzenden(false)
    }
  }

  // ── Nieuwe groep aanmaken ────────────────────────────────────────────────
  async function maakGroepAan() {
    if (!nieuweGroepNaam.trim()) { setNieuweGroepFout('Vul een groepsnaam in'); return }
    setNieuweGroepFout('')
    setNieuweGroepLaden(true)
    try {
      const res = await fetch('/api/ingestion/chat/groepen/aanmaken', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ naam: nieuweGroepNaam.trim(), leden: [...geselecteerdeLedenIds] }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setNieuweGroepFout(err.detail ?? 'Aanmaken mislukt')
        return
      }
      const nieuw: Groep = await res.json()
      setGroepen(prev => [...prev, nieuw])
      setNieuweGroepOpen(false)
      setNieuweGroepNaam('')
      setGeselecteerdeLedenIds(new Set())
    } catch { setNieuweGroepFout('Verbindingsfout') }
    finally { setNieuweGroepLaden(false) }
  }

  function toggleLid(id: string) {
    setGeselecteerdeLedenIds(prev => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  // ── Filter + groepeer contacten ──────────────────────────────────────────
  const gefilterd = contacten.filter(c =>
    c.naam.toLowerCase().includes(zoekterm.toLowerCase()) ||
    c.bedrijf.toLowerCase().includes(zoekterm.toLowerCase())
  )
  const aannemers = gefilterd.filter(c => rolGroep(c.rol) === 'aannemers')
  const vakmensen = gefilterd.filter(c => rolGroep(c.rol) === 'vakmensen')
  const totaalOngelezen = Object.values(ongelezen).reduce((a, b) => a + b, 0)

  const groepKnop = (label: string, icon: React.ReactNode, open: boolean, toggle: () => void) => (
    <button onClick={toggle} style={{
      width: '100%', padding: '8px 16px', display: 'flex', alignItems: 'center',
      gap: 6, background: 'none', border: 'none', cursor: 'pointer',
      color: 'var(--text-muted)', fontSize: 11, fontWeight: 600,
      textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>
      {icon}{label}
      <span style={{ marginLeft: 'auto' }}>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </span>
    </button>
  )

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden', background: 'var(--bg)' }}>

      {/* ── Contactenlijst ───────────────────────────────────────────── */}
      <div style={{
        width: 272, minWidth: 272, background: 'var(--bg-white)',
        borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <MessageCircle size={18} color="var(--teal)" />
            <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>Berichten</span>
            {totaalOngelezen > 0 && (
              <span style={{
                marginLeft: 'auto', background: 'var(--teal)', color: '#fff',
                borderRadius: 10, fontSize: 11, fontWeight: 700, padding: '1px 7px',
              }}>
                {totaalOngelezen}
              </span>
            )}
          </div>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{
              position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)',
              color: 'var(--text-muted)', pointerEvents: 'none',
            }} />
            <input
              type="text"
              placeholder="Zoek persoon..."
              value={zoekterm}
              onChange={e => setZoekterm(e.target.value)}
              style={{
                width: '100%', padding: '7px 10px 7px 30px',
                border: '1px solid var(--border)', borderRadius: 8,
                fontSize: 13, background: 'var(--bg)', color: 'var(--text)',
                outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Contactenlijst */}
        <div style={{ flex: 1, overflowY: 'auto' }}>

          {/* AI Assistent — altijd bovenaan */}
          {(!zoekterm || 'opti intel ai'.includes(zoekterm.toLowerCase())) && (
            <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: 4, marginBottom: 4 }}>
              <ContactRij
                contact={AI_CONTACT}
                actief={actieveContact?.id === 'ai-assistent'}
                ongelezen={0}
                onClick={() => selecteerContact(AI_CONTACT)}
              />
            </div>
          )}

          {/* Groepschats */}
          <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: 4, marginBottom: 4 }}>
            {/* Header met + knop */}
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <button onClick={() => setGroepenOpen(v => !v)} style={{
                flex: 1, padding: '8px 10px 8px 16px', display: 'flex', alignItems: 'center',
                gap: 6, background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-muted)', fontSize: 11, fontWeight: 600,
                textTransform: 'uppercase', letterSpacing: '0.06em',
              }}>
                <Building2 size={12} />
                Groepschats {groepen.length > 0 ? `(${groepen.length})` : ''}
                <span style={{ marginLeft: 'auto' }}>
                  {groepenOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </span>
              </button>
              <button
                title="Nieuwe groep aanmaken"
                onClick={() => { setNieuweGroepOpen(true); setNieuweGroepFout('') }}
                style={{
                  width: 28, height: 28, marginRight: 8, borderRadius: 6,
                  border: '1px dashed var(--border)', background: 'none',
                  cursor: 'pointer', color: 'var(--teal)', fontSize: 16, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                +
              </button>
            </div>
            {groepenOpen && groepen.length === 0 && (
              <div style={{ padding: '6px 16px 8px', fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                Nog geen groepen — maak er een aan
              </div>
            )}
            {groepenOpen && groepen.map(g => {
              const groepContact: ChatGebruiker = {
                id: g.naam,
                naam: g.naam,
                rol: 'groep',
                bedrijf: `${g.leden} ${g.leden === 1 ? 'lid' : 'leden'}${g.type === 'custom' ? ' · Aangepast' : ''}`,
                isGroep: true,
              }
              return (
                <ContactRij
                  key={g.naam}
                  contact={groepContact}
                  actief={actieveContact?.isGroep === true && actieveContact?.id === g.naam}
                  ongelezen={0}
                  onClick={() => selecteerContact(groepContact)}
                />
              )
            })}
          </div>

          {/* Aannemers */}
          {aannemers.length > 0 && (
            <div>
              {groepKnop(`Aannemers (${aannemers.length})`, <HardHat size={12} />, aannemersOpen, () => setAannemersOpen(v => !v))}
              {aannemersOpen && aannemers.map(c => (
                <ContactRij key={c.id} contact={c} actief={actieveContact?.id === c.id}
                  ongelezen={ongelezen[c.id] ?? 0} onClick={() => selecteerContact(c)} />
              ))}
            </div>
          )}

          {/* Vakmensen */}
          {vakmensen.length > 0 && (
            <div>
              {groepKnop(`Vakmensen (${vakmensen.length})`, <Users size={12} />, vakmensOpen, () => setVakmensOpen(v => !v))}
              {vakmensOpen && vakmensen.map(c => (
                <ContactRij key={c.id} contact={c} actief={actieveContact?.id === c.id}
                  ongelezen={ongelezen[c.id] ?? 0} onClick={() => selecteerContact(c)} />
              ))}
            </div>
          )}

          {gefilterd.length === 0 && zoekterm && (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              Geen personen gevonden
            </div>
          )}
        </div>
      </div>

      {/* ── Chatvenster ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {!actieveContact ? (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--text-muted)',
          }}>
            <MessageCircle size={52} strokeWidth={1} color="var(--border)" />
            <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-sub)' }}>Selecteer een persoon</p>
            <p style={{ fontSize: 13 }}>Berichten zijn alleen zichtbaar voor jou en de ontvanger</p>
          </div>
        ) : (
          <>
            {/* Gesprekheader */}
            <div style={{
              padding: '12px 20px', background: 'var(--bg-white)',
              borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <Avatar naam={actieveContact.naam} rol={actieveContact.rol} size={38} />
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  {actieveContact.naam}
                  {actieveContact.isAI && <Sparkles size={14} color="#6b5aad" />}
                </div>
                <div style={{ fontSize: 12, color: actieveContact.isAI ? '#6b5aad' : actieveContact.isGroep ? 'var(--teal)' : 'var(--text-muted)' }}>
                  {actieveContact.isAI
                    ? 'Vraag me naar taken, status en deadlines'
                    : actieveContact.isGroep
                    ? `Groepschat · ${actieveContact.bedrijf}`
                    : `${rolLabel(actieveContact.rol)}${actieveContact.bedrijf ? ` · ${actieveContact.bedrijf}` : ''}`}
                </div>
              </div>
            </div>

            {/* Berichten */}
            <div ref={berichtenRef} style={{
              flex: 1, overflowY: 'auto', padding: '20px',
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              {laden && (actieveContact.isAI ? aiBerichten : actieveContact.isGroep ? groepBerichten : berichten).length === 0 && (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Laden…</div>
              )}

              {/* AI berichten */}
              {actieveContact.isAI && (
                <>
                  {aiBerichten.length === 0 && !laden && (
                    <div style={{
                      margin: '40px auto', maxWidth: 340, textAlign: 'center',
                      background: 'var(--bg-white)', border: '1px solid var(--border)',
                      borderRadius: 12, padding: 24,
                    }}>
                      <Bot size={36} color="#6b5aad" style={{ marginBottom: 12 }} />
                      <p style={{ fontWeight: 600, color: 'var(--text)', marginBottom: 8 }}>Opti Intel AI-assistent</p>
                      <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                        Vraag me naar projectstatus, taken of deadlines. Ik kijk direct in de database!
                      </p>
                    </div>
                  )}
                  {aiBerichten.map((b) => {
                    const isEigen = b.rol === 'user'
                    return (
                      <div key={b.id} style={{
                        display: 'flex', flexDirection: isEigen ? 'row-reverse' : 'row',
                        alignItems: 'flex-end', gap: 8, marginTop: 10,
                      }}>
                        <div style={{ width: 28, flexShrink: 0 }}>
                          {!isEigen && <Avatar naam="AI" rol="ai" size={28} />}
                        </div>
                        <div style={{ maxWidth: '70%', display: 'flex', flexDirection: 'column', alignItems: isEigen ? 'flex-end' : 'flex-start' }}>
                          <div style={{
                            padding: '9px 13px',
                            borderRadius: isEigen ? '14px 4px 14px 14px' : '4px 14px 14px 14px',
                            background: isEigen ? 'var(--navy-light)' : 'linear-gradient(135deg, rgba(107,90,173,0.08), rgba(58,168,193,0.08))',
                            color: isEigen ? '#fff' : 'var(--text)',
                            fontSize: 14, lineHeight: 1.5,
                            border: isEigen ? 'none' : '1px solid rgba(107,90,173,0.2)',
                            wordBreak: 'break-word', whiteSpace: 'pre-wrap',
                          }}>
                            {b.tekst}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, padding: '0 2px' }}>
                            {formatTijdstip(b.tijdstip)}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  {aiLaden && (
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, marginTop: 10 }}>
                      <Avatar naam="AI" rol="ai" size={28} />
                      <div style={{
                        padding: '10px 16px', borderRadius: '4px 14px 14px 14px',
                        background: 'rgba(107,90,173,0.08)', border: '1px solid rgba(107,90,173,0.2)',
                        fontSize: 14, color: 'var(--text-muted)', fontStyle: 'italic',
                      }}>
                        Aan het nadenken…
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Groep berichten */}
              {actieveContact.isGroep && (
                <>
                  {!laden && groepBerichten.length === 0 && (
                    <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, marginTop: 40 }}>
                      Nog geen berichten — stuur als eerste!
                    </div>
                  )}
                  {groepBerichten.map((b, i) => {
                    const isEigen = b.van_id === gebruiker?.id
                    const vorigZelfde = i > 0 && groepBerichten[i - 1].van_id === b.van_id
                    const volgendZelfde = i < groepBerichten.length - 1 && groepBerichten[i + 1].van_id === b.van_id
                    return (
                      <div key={b.id} style={{
                        display: 'flex', flexDirection: isEigen ? 'row-reverse' : 'row',
                        alignItems: 'flex-end', gap: 8, marginTop: vorigZelfde ? 2 : 14,
                      }}>
                        <div style={{ width: 28, flexShrink: 0 }}>
                          {!volgendZelfde && !isEigen && (
                            <Avatar naam={b.van_naam} rol="vakman" size={28} />
                          )}
                        </div>
                        <div style={{ maxWidth: '65%', display: 'flex', flexDirection: 'column', alignItems: isEigen ? 'flex-end' : 'flex-start' }}>
                          {!vorigZelfde && !isEigen && (
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2, padding: '0 2px' }}>
                              {b.van_naam}
                            </div>
                          )}
                          <div style={{
                            padding: '9px 13px',
                            borderRadius: isEigen
                              ? (vorigZelfde ? '14px 4px 4px 14px' : '14px 4px 14px 14px')
                              : (vorigZelfde ? '4px 14px 14px 4px' : '4px 14px 14px 14px'),
                            background: isEigen ? 'var(--navy-light)' : 'var(--bg-white)',
                            color: isEigen ? '#fff' : 'var(--text)',
                            fontSize: 14, lineHeight: 1.45,
                            boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
                            border: isEigen ? 'none' : '1px solid var(--border)',
                            wordBreak: 'break-word',
                          }}>
                            {b.tekst}
                          </div>
                          {!volgendZelfde && (
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, padding: '0 2px' }}>
                              {formatTijdstip(b.tijdstip)}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </>
              )}

              {/* Reguliere berichten */}
              {!actieveContact.isAI && !actieveContact.isGroep && (
                <>
                  {!laden && berichten.length === 0 && (
                    <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, marginTop: 40 }}>
                      Nog geen berichten — stuur als eerste!
                    </div>
                  )}
                  {berichten.map((b, i) => {
                    const isEigen = b.van_id === gebruiker?.id
                    const vorigZelfde = i > 0 && berichten[i - 1].van_id === b.van_id
                    const volgendZelfde = i < berichten.length - 1 && berichten[i + 1].van_id === b.van_id
                    return (
                      <div key={b.id} style={{
                        display: 'flex', flexDirection: isEigen ? 'row-reverse' : 'row',
                        alignItems: 'flex-end', gap: 8, marginTop: vorigZelfde ? 2 : 14,
                      }}>
                        <div style={{ width: 28, flexShrink: 0 }}>
                          {!volgendZelfde && !isEigen && (
                            <Avatar naam={actieveContact.naam} rol={actieveContact.rol} size={28} />
                          )}
                        </div>
                        <div style={{ maxWidth: '65%', display: 'flex', flexDirection: 'column', alignItems: isEigen ? 'flex-end' : 'flex-start' }}>
                          <div style={{
                            padding: '9px 13px',
                            borderRadius: isEigen
                              ? (vorigZelfde ? '14px 4px 4px 14px' : '14px 4px 14px 14px')
                              : (vorigZelfde ? '4px 14px 14px 4px' : '4px 14px 14px 14px'),
                            background: isEigen ? 'var(--navy-light)' : 'var(--bg-white)',
                            color: isEigen ? '#fff' : 'var(--text)',
                            fontSize: 14, lineHeight: 1.45,
                            boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
                            border: isEigen ? 'none' : '1px solid var(--border)',
                            wordBreak: 'break-word',
                          }}>
                            {b.tekst}
                          </div>
                          {!volgendZelfde && (
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, padding: '0 2px' }}>
                              {formatTijdstip(b.tijdstip)}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </>
              )}

            </div>

            {/* Invoer */}
            <form onSubmit={stuurBericht} style={{
              padding: '12px 20px', background: 'var(--bg-white)',
              borderTop: '1px solid var(--border)',
              display: 'flex', gap: 10, alignItems: 'center',
            }}>
              <input
                ref={invoerRef}
                type="text"
                value={invoer}
                onChange={e => setInvoer(e.target.value)}
                placeholder={actieveContact.isAI
                  ? 'Vraag iets over je project…'
                  : actieveContact.isGroep
                  ? `Bericht in ${actieveContact.naam}…`
                  : `Bericht naar ${actieveContact.naam}…`}
                disabled={verzenden || aiLaden}
                style={{
                  flex: 1, padding: '10px 14px',
                  border: `1px solid ${actieveContact.isAI ? 'rgba(107,90,173,0.3)' : 'var(--border)'}`,
                  borderRadius: 22,
                  fontSize: 14, background: 'var(--bg)', color: 'var(--text)',
                  outline: 'none',
                }}
              />
              <button type="submit" disabled={!invoer.trim() || verzenden || aiLaden} style={{
                width: 40, height: 40, borderRadius: '50%', border: 'none',
                background: invoer.trim()
                  ? (actieveContact.isAI ? '#6b5aad' : 'var(--teal)')
                  : 'var(--border)',

                color: '#fff', cursor: invoer.trim() ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s', flexShrink: 0,
              }}>
                <Send size={16} />
              </button>
            </form>
          </>
        )}
      </div>

      {/* ── Nieuwe groep modal ────────────────────────────────────────── */}
      {nieuweGroepOpen && (
        <div
          onClick={() => setNieuweGroepOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
            zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--bg-white)', borderRadius: 14, padding: 28,
              width: 440, maxWidth: '90vw', maxHeight: '80vh',
              display: 'flex', flexDirection: 'column', gap: 16,
              boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Building2 size={18} color="var(--teal)" />
              Nieuwe groep aanmaken
            </div>

            {/* Groepsnaam */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-sub)', display: 'block', marginBottom: 6 }}>
                Groepsnaam *
              </label>
              <input
                type="text"
                autoFocus
                value={nieuweGroepNaam}
                onChange={e => setNieuweGroepNaam(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && maakGroepAan()}
                placeholder="bijv. Projectteam Oost, Planning 2026…"
                style={{
                  width: '100%', padding: '9px 12px', boxSizing: 'border-box',
                  border: '1px solid var(--border)', borderRadius: 8,
                  fontSize: 14, background: 'var(--bg)', color: 'var(--text)', outline: 'none',
                }}
              />
            </div>

            {/* Leden selecteren */}
            <div style={{ flex: 1, minHeight: 0 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-sub)', display: 'block', marginBottom: 6 }}>
                Leden toevoegen
                {geselecteerdeLedenIds.size > 0 && (
                  <span style={{ marginLeft: 6, color: 'var(--teal)' }}>({geselecteerdeLedenIds.size} geselecteerd)</span>
                )}
              </label>
              <div style={{
                border: '1px solid var(--border)', borderRadius: 8,
                overflowY: 'auto', maxHeight: 220,
              }}>
                {contacten.length === 0 && (
                  <div style={{ padding: 12, fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' }}>
                    Geen contacten beschikbaar
                  </div>
                )}
                {contacten.map(c => (
                  <label key={c.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 12px', cursor: 'pointer',
                    background: geselecteerdeLedenIds.has(c.id) ? 'var(--blue-bg)' : 'transparent',
                    borderBottom: '1px solid var(--border)',
                  }}>
                    <input
                      type="checkbox"
                      checked={geselecteerdeLedenIds.has(c.id)}
                      onChange={() => toggleLid(c.id)}
                      style={{ accentColor: 'var(--teal)', width: 15, height: 15, flexShrink: 0 }}
                    />
                    <Avatar naam={c.naam} rol={c.rol} size={26} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{c.naam}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.bedrijf || rolLabel(c.rol)}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {nieuweGroepFout && (
              <div style={{ fontSize: 13, color: 'var(--red)', background: 'var(--red-bg)', padding: '8px 12px', borderRadius: 8 }}>
                {nieuweGroepFout}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setNieuweGroepOpen(false)}
                style={{
                  padding: '9px 18px', border: '1px solid var(--border)', borderRadius: 8,
                  background: 'none', cursor: 'pointer', fontSize: 14, color: 'var(--text)',
                }}>
                Annuleren
              </button>
              <button
                onClick={maakGroepAan}
                disabled={!nieuweGroepNaam.trim() || nieuweGroepLaden}
                style={{
                  padding: '9px 18px', border: 'none', borderRadius: 8,
                  background: nieuweGroepNaam.trim() ? 'var(--teal)' : 'var(--border)',
                  color: '#fff', cursor: nieuweGroepNaam.trim() ? 'pointer' : 'default',
                  fontSize: 14, fontWeight: 600,
                }}>
                {nieuweGroepLaden ? 'Aanmaken…' : 'Groep aanmaken'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
