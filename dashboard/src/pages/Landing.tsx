import { MessageSquare, Link2, Bell, ArrowRight, Mail } from 'lucide-react'
import logo from '../assets/logo.svg'

/**
 * Publieke landingspagina voor bezoekers zonder account.
 * Wordt alleen getoond in de browser; de geïnstalleerde webapp
 * (beginscherm) en ingelogde gebruikers slaan deze pagina over.
 */
function Landing({ onInloggen }: { onInloggen: () => void }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>

      {/* Topbalk */}
      <header style={{
        background: 'var(--navy)', padding: '14px 24px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src={logo} alt="Opti-Intel" style={{ height: 30, display: 'block' }} />
          <span style={{ fontSize: 17, fontWeight: 700, color: '#fff', letterSpacing: 0.2 }}>Opti-Intel</span>
        </div>
        <button
          onClick={onInloggen}
          style={{
            background: '#fff', color: 'var(--navy)', border: 'none', borderRadius: 6,
            padding: '9px 18px', fontSize: 14, fontWeight: 700, cursor: 'pointer',
          }}
        >
          Inloggen
        </button>
      </header>

      {/* Hero */}
      <section style={{ padding: '64px 24px 48px', textAlign: 'center', maxWidth: 760, margin: '0 auto' }}>
        <img src={logo} alt="" style={{ height: 72, display: 'block', margin: '0 auto 24px' }} />
        <h1 style={{ fontSize: 'clamp(26px, 5vw, 40px)', fontWeight: 800, color: 'var(--text)', lineHeight: 1.2, marginBottom: 16 }}>
          Bouwplanning die zichzelf bijwerkt
        </h1>
        <p style={{ fontSize: 17, color: 'var(--text-sub)', lineHeight: 1.6, maxWidth: 560, margin: '0 auto 28px' }}>
          Eén appje van de bouwplaats — "de tegels komen pas maandag" — en Opti-Intel
          past de hele planning aan. Iedereen die geraakt wordt, krijgt direct een
          melding op zijn telefoon.
        </p>
        <button
          onClick={onInloggen}
          style={{
            background: 'var(--navy)', color: '#fff', border: 'none', borderRadius: 8,
            padding: '13px 28px', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 8,
          }}
        >
          Naar de app <ArrowRight size={16} />
        </button>
      </section>

      {/* Kernpunten */}
      <section style={{
        maxWidth: 960, margin: '0 auto', padding: '0 24px 56px',
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16,
      }}>
        {[
          {
            Icoon: MessageSquare, titel: 'Melden via chat',
            tekst: 'Vakmensen sturen een gewoon berichtje. De AI herkent wie, wat en wanneer — en zet het om in een planningsvoorstel.',
          },
          {
            Icoon: Link2, titel: 'Schuift automatisch door',
            tekst: 'Loopt het tegelen uit, dan schuiven het voegen en alles daarna vanzelf mee. Weekends worden overgeslagen.',
          },
          {
            Icoon: Bell, titel: 'Iedereen direct op de hoogte',
            tekst: 'Elke betrokkene krijgt een pushmelding op zijn telefoon zodra zijn planning verandert. Geen belrondes meer.',
          },
        ].map(k => (
          <div key={k.titel} className="card" style={{ marginBottom: 0, textAlign: 'left' }}>
            <k.Icoon size={22} style={{ color: 'var(--navy)', marginBottom: 10 }} />
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>{k.titel}</div>
            <div style={{ fontSize: 13.5, color: 'var(--text-sub)', lineHeight: 1.6 }}>{k.tekst}</div>
          </div>
        ))}
      </section>

      {/* Footer */}
      <footer style={{
        marginTop: 'auto', borderTop: '1px solid var(--border)', background: 'var(--bg-white)',
        padding: '20px 24px', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', gap: 12, flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          © {new Date().getFullYear()} Opti-Intel · Opti Corporation
        </span>
        <a
          href="mailto:info@benwa-intelligence.com"
          style={{
            fontSize: 13, color: 'var(--navy)', textDecoration: 'none', fontWeight: 600,
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}
        >
          <Mail size={14} /> Neem contact op
        </a>
      </footer>
    </div>
  )
}

export default Landing
