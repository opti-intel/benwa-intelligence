import { useState, useRef, useEffect } from 'react'
import { type ChatBericht, type ChatContext, type Taak, chatApi, addTaakToStorage, takenApi } from '../hooks/useApi'

const PROJECT_ID = crypto.randomUUID()

function Chat() {
  const [berichten, setBerichten] = useState<ChatBericht[]>([
    {
      id: '0',
      rol: 'systeem',
      tekst: 'Hoi! Ik ben je bouwplannings-assistent. Vertel me wat er moet gebeuren op de werf en ik maak er automatisch een taak van.\n\nBijvoorbeeld: "Ik kom donderdag om 9u het sanitair plaatsen in blok A"',
      tijdstip: new Date().toISOString(),
    },
  ])
  const [invoer, setInvoer] = useState('')
  const [laden, setLaden] = useState(false)
  const [pendingContext, setPendingContext] = useState<ChatContext | null>(null)
  const berichtenRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (berichtenRef.current) {
      berichtenRef.current.scrollTop = berichtenRef.current.scrollHeight
    }
  }, [berichten, laden])

  async function verstuurBericht() {
    const tekst = invoer.trim()
    if (!tekst || laden) return

    const gebruikerBericht: ChatBericht = {
      id: crypto.randomUUID(),
      rol: 'gebruiker',
      tekst,
      tijdstip: new Date().toISOString(),
    }
    setBerichten(prev => [...prev, gebruikerBericht])
    setInvoer('')
    setLaden(true)

    try {
      // Send current context (if any) along with the message
      const result = await chatApi.verstuur(tekst, PROJECT_ID, pendingContext)

      let createdTaak: Taak | undefined

      // If a complete task was created, save it
      if (result.heeft_taak && result.taak) {
        const t = result.taak
        createdTaak = {
          id: crypto.randomUUID(),
          naam: t.naam,
          beschrijving: [t.beschrijving, t.locatie ? `Locatie: ${t.locatie}` : ''].filter(Boolean).join(' — '),
          status: 'gepland',
          startdatum: t.startdatum || '',
          einddatum: t.einddatum || t.startdatum || '',
          toegewezen_aan: t.toegewezen_aan,
        }
        addTaakToStorage(createdTaak)
        takenApi.aanmaken(createdTaak).catch(() => {})
        // Task complete — clear context
        setPendingContext(null)
      } else if (result.onvolledig) {
        // Info missing — store partial context for next message
        setPendingContext(result.onvolledig)
      } else {
        // No task and no partial (greeting, question, etc.) — clear context
        setPendingContext(null)
      }

      const systeemBericht: ChatBericht = {
        id: crypto.randomUUID(),
        rol: 'systeem',
        tekst: result.antwoord,
        tijdstip: new Date().toISOString(),
        taakAangemaakt: createdTaak,
      }
      setBerichten(prev => [...prev, systeemBericht])
    } catch (err) {
      const errorBericht: ChatBericht = {
        id: crypto.randomUUID(),
        rol: 'systeem',
        tekst: `Fout bij verbinding met de server: ${err instanceof Error ? err.message : 'Onbekende fout'}`,
        tijdstip: new Date().toISOString(),
      }
      setBerichten(prev => [...prev, errorBericht])
    } finally {
      setLaden(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      verstuurBericht()
    }
  }

  function formatTijd(iso: string) {
    return new Date(iso).toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })
  }

  function formatDate(d: string) {
    if (!d) return ''
    return new Date(d).toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long' })
  }

  // Dynamic placeholder based on what the backend is asking for next
  let placeholder = 'Vertel wat er moet gebeuren op de werf...'
  if (pendingContext) {
    if (!pendingContext.locatie) {
      placeholder = 'Locatie? bijv. "badkamer", "blok A", "2e verdieping"'
    } else if (!pendingContext.datum) {
      placeholder = 'Datum? bijv. "zaterdag", "28 februari"'
    } else if (!pendingContext.tijd) {
      placeholder = 'Tijd? bijv. "9u", "14:30"'
    } else if (!pendingContext.persoon) {
      placeholder = 'Wie? bijv. "Jan", "de loodgieter"'
    }
  }

  return (
    <div className="chat-container">
      <div className="page-header">
        <h2>Chat</h2>
        <p>Vertel wat er moet gebeuren — ik maak de taken aan</p>
      </div>

      <div className="chat-berichten" ref={berichtenRef}>
        {berichten.map(b => (
          <div key={b.id}>
            <div
              className={`chat-bericht ${b.rol === 'gebruiker' ? 'chat-bericht-gebruiker' : 'chat-bericht-systeem'}`}
            >
              <div>{b.tekst}</div>
              <div style={{ fontSize: 11, marginTop: 4, opacity: 0.6 }}>{formatTijd(b.tijdstip)}</div>
            </div>
            {b.taakAangemaakt && (
              <div className="chat-taak-card">
                <div className="chat-taak-card-header">
                  <span className="chat-taak-card-icon">+</span>
                  <span>Taak aangemaakt</span>
                </div>
                <div className="chat-taak-card-naam">{b.taakAangemaakt.naam}</div>
                {b.taakAangemaakt.startdatum && (
                  <div className="chat-taak-card-detail">{formatDate(b.taakAangemaakt.startdatum)}</div>
                )}
                {b.taakAangemaakt.toegewezen_aan && (
                  <div className="chat-taak-card-detail">{b.taakAangemaakt.toegewezen_aan}</div>
                )}
              </div>
            )}
          </div>
        ))}
        {laden && <div className="chat-typing">Bezig met nadenken...</div>}
      </div>

      <div className="chat-invoer">
        {pendingContext && (
          <button
            className="secondary"
            style={{ flexShrink: 0, padding: '10px 12px', fontSize: 12 }}
            onClick={() => {
              // Skip the missing field — force task creation with what we have
              setPendingContext(null)
              // Re-send with a skip signal by creating a "sla over" message
              setInvoer('sla over')
            }}
            title="Taak aanmaken zonder ontbrekende info"
          >
            Sla over
          </button>
        )}
        <input
          type="text"
          value={invoer}
          onChange={e => setInvoer(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={laden}
        />
        <button className="primary" onClick={verstuurBericht} disabled={laden || !invoer.trim()}>
          Verstuur
        </button>
      </div>
    </div>
  )
}

export default Chat
