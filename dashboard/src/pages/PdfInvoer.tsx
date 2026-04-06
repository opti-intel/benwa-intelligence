import { useState, useRef, useCallback } from 'react'
import { Taak } from '../hooks/useApi'
import { authHeaders } from '../hooks/useAuth'

interface PdfResultaat {
  totaal_gevonden: number
  taken_aangemaakt: number
  taken: Taak[]
  ruwe_tekst_preview: string
}

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

export default function PdfInvoer() {
  const [status, setStatus] = useState<UploadStatus>('idle')
  const [resultaat, setResultaat] = useState<PdfResultaat | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const uploadFile = useCallback(async (file: File) => {
    if (file.type !== 'application/pdf') {
      setError('Alleen PDF-bestanden zijn toegestaan.')
      return
    }

    setStatus('uploading')
    setError(null)
    setResultaat(null)
    setFileName(file.name)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/ingestion/ingest/pdf', {
        method: 'POST',
        headers: { ...authHeaders() },
        body: formData,
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Upload mislukt: ${text}`)
      }

      const data: PdfResultaat = await res.json()
      setResultaat(data)
      setStatus('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Onbekende fout')
      setStatus('error')
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragActive(false)
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const resetUpload = useCallback(() => {
    setStatus('idle')
    setResultaat(null)
    setError(null)
    setFileName(null)
    if (inputRef.current) inputRef.current.value = ''
  }, [])

  const statusLabel = (s: string) => {
    switch (s) {
      case 'gepland': return 'Gepland'
      case 'bezig': return 'Bezig'
      case 'klaar': return 'Klaar'
      default: return s
    }
  }

  const statusClass = (s: string) => {
    switch (s) {
      case 'gepland': return 'info'
      case 'bezig': return 'warning'
      case 'klaar': return 'success'
      default: return 'pending'
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>PDF Invoer</h2>
        <p>Upload een bouwplanning PDF om automatisch taken te extraheren</p>
      </div>

      {/* Upload area */}
      {status === 'idle' || status === 'error' ? (
        <div
          className={`pdf-dropzone ${dragActive ? 'pdf-dropzone-active' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          <div className="pdf-dropzone-icon">^</div>
          <div className="pdf-dropzone-title">
            Sleep een PDF hierheen of klik om te uploaden
          </div>
          <div className="pdf-dropzone-subtitle">
            Ondersteund: bouwplanning documenten (.pdf)
          </div>
        </div>
      ) : null}

      {/* Uploading state */}
      {status === 'uploading' && (
        <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
          <div className="loading">PDF verwerken: {fileName}</div>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>
            Tekst extraheren en taken herkennen...
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-message" style={{ marginTop: '16px' }}>
          {error}
          <button className="secondary" style={{ marginLeft: '12px', padding: '4px 12px', fontSize: '12px' }} onClick={resetUpload}>
            Opnieuw proberen
          </button>
        </div>
      )}

      {/* Results */}
      {status === 'success' && resultaat && (
        <div style={{ marginTop: '24px' }}>
          {/* Summary banner */}
          <div className="pdf-success-banner">
            <div className="pdf-success-icon">V</div>
            <div>
              <div className="pdf-success-title">
                We hebben {resultaat.totaal_gevonden} taken gevonden en {resultaat.taken_aangemaakt} toegevoegd aan je planning
              </div>
              <div className="pdf-success-subtitle">
                Bestand: {fileName}
              </div>
            </div>
          </div>

          {/* Task list */}
          <div className="card" style={{ marginTop: '16px' }}>
            <div className="card-header">
              <h3>Geextraheerde taken</h3>
              <button className="secondary" onClick={resetUpload} style={{ padding: '6px 14px', fontSize: '13px' }}>
                Nieuwe upload
              </button>
            </div>

            {resultaat.taken.length > 0 ? (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Taak</th>
                      <th>Startdatum</th>
                      <th>Einddatum</th>
                      <th>Toegewezen aan</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultaat.taken.map((taak) => (
                      <tr key={taak.id}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{taak.naam}</div>
                          {taak.beschrijving && (
                            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                              {taak.beschrijving}
                            </div>
                          )}
                        </td>
                        <td className="mono">{taak.startdatum || '—'}</td>
                        <td className="mono">{taak.einddatum || '—'}</td>
                        <td>{taak.toegewezen_aan || '—'}</td>
                        <td>
                          <span className={`status-badge ${statusClass(taak.status)}`}>
                            {statusLabel(taak.status)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                Geen taken gevonden in dit document
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
