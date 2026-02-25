import { useState, useEffect, useCallback } from 'react'
import { type PlanningTaak, type Taak, type TaakStatus, planningApi, loadTakenFromStorage } from '../hooks/useApi'

// Reference date for calculating Gantt offsets (project start)
const PROJECT_START = new Date('2026-03-01')

function dateToDayOffset(dateStr: string): number {
  if (!dateStr) return 0
  const d = new Date(dateStr)
  const diff = d.getTime() - PROJECT_START.getTime()
  return Math.max(0, Math.round(diff / (1000 * 60 * 60 * 24)))
}

function taakToPlanningTaak(taak: Taak): PlanningTaak {
  const start = dateToDayOffset(taak.startdatum)
  const end = taak.einddatum ? dateToDayOffset(taak.einddatum) : start + 1
  const duur = Math.max(1, end - start)
  return {
    id: taak.id,
    naam: taak.naam,
    start,
    duur,
    status: taak.status,
    afhankelijkheden: [],
  }
}

function loadPlanningTaken(): PlanningTaak[] {
  const taken = loadTakenFromStorage()
  if (taken.length === 0) return defaultTaken
  return taken.map(taakToPlanningTaak)
}

const defaultTaken: PlanningTaak[] = [
  { id: '1', naam: 'Fundering', start: 0, duur: 14, status: 'klaar', afhankelijkheden: [] },
  { id: '2', naam: 'Ruwbouw', start: 14, duur: 26, status: 'bezig', afhankelijkheden: ['1'] },
  { id: '3', naam: 'Dakwerken', start: 40, duur: 14, status: 'gepland', afhankelijkheden: ['2'] },
  { id: '4', naam: 'Elektriciteit', start: 44, duur: 16, status: 'gepland', afhankelijkheden: ['2'] },
  { id: '5', naam: 'Loodgieterij', start: 49, duur: 15, status: 'gepland', afhankelijkheden: ['2'] },
  { id: '6', naam: 'Afwerking', start: 65, duur: 24, status: 'gepland', afhankelijkheden: ['3', '4', '5'] },
]

const statusColors: Record<TaakStatus, string> = {
  gepland: 'var(--accent-purple)',
  bezig: 'var(--accent-blue)',
  klaar: 'var(--accent-green)',
}

type ViewMode = 'week' | 'maand'

function Planning() {
  const [taken, setTaken] = useState<PlanningTaak[]>(loadPlanningTaken)
  const [viewMode, setViewMode] = useState<ViewMode>('week')
  const [optimizing, setOptimizing] = useState(false)

  // Re-read from localStorage when the page regains focus (e.g. after using Chat)
  const refreshFromStorage = useCallback(() => {
    setTaken(loadPlanningTaken())
  }, [])

  useEffect(() => {
    window.addEventListener('focus', refreshFromStorage)
    // Also listen for storage events from other tabs
    window.addEventListener('storage', refreshFromStorage)
    return () => {
      window.removeEventListener('focus', refreshFromStorage)
      window.removeEventListener('storage', refreshFromStorage)
    }
  }, [refreshFromStorage])

  const dayWidth = viewMode === 'week' ? 40 : 20
  const totalDays = taken.length > 0
    ? Math.max(...taken.map(t => t.start + t.duur)) + 10
    : 100
  const totalWidth = totalDays * dayWidth

  // Generate headers
  const headers: { label: string; width: number }[] = []
  if (viewMode === 'week') {
    for (let d = 0; d < totalDays; d += 7) {
      headers.push({ label: `W${Math.floor(d / 7) + 1}`, width: 7 * dayWidth })
    }
  } else {
    for (let d = 0; d < totalDays; d += 30) {
      headers.push({ label: `M${Math.floor(d / 30) + 1}`, width: 30 * dayWidth })
    }
  }

  // Build dependency lines
  function getDependencyLines() {
    const lines: { x1: number; y1: number; x2: number; y2: number }[] = []
    const taskIndex = new Map(taken.map((t, i) => [t.id, i]))

    for (const taak of taken) {
      const toIdx = taskIndex.get(taak.id)
      if (toIdx === undefined) continue

      for (const depId of taak.afhankelijkheden) {
        const fromIdx = taskIndex.get(depId)
        if (fromIdx === undefined) continue

        const fromTask = taken[fromIdx]
        const x1 = (fromTask.start + fromTask.duur) * dayWidth
        const y1 = fromIdx * 40 + 20
        const x2 = taak.start * dayWidth
        const y2 = toIdx * 40 + 20

        lines.push({ x1, y1, x2, y2 })
      }
    }
    return lines
  }

  async function handleOptimize() {
    setOptimizing(true)
    try {
      const result = await planningApi.schema(taken)
      if (result && typeof result === 'object') {
        const optimized = (result as { tasks?: PlanningTaak[] }).tasks
        if (Array.isArray(optimized)) {
          setTaken(optimized)
        }
      }
    } catch {
      // Solver unavailable — keep current data
    } finally {
      setOptimizing(false)
    }
  }

  const depLines = getDependencyLines()

  // "Today" line on the Gantt
  const todayOffset = dateToDayOffset(new Date().toISOString().slice(0, 10))

  return (
    <div>
      <div className="page-header">
        <h2>Planning</h2>
        <p>Gantt-overzicht van het bouwproject — start: 1 maart 2026</p>
      </div>

      <div className="flex items-center gap-16 mb-24">
        <div className="tabs" style={{ marginBottom: 0 }}>
          <button className={`tab ${viewMode === 'week' ? 'active' : ''}`} onClick={() => setViewMode('week')}>
            Week
          </button>
          <button className={`tab ${viewMode === 'maand' ? 'active' : ''}`} onClick={() => setViewMode('maand')}>
            Maand
          </button>
        </div>
        <button className="secondary" onClick={refreshFromStorage}>Vernieuwen</button>
        <button className="primary" onClick={handleOptimize} disabled={optimizing}>
          {optimizing ? 'Bezig...' : 'Optimaliseer'}
        </button>
      </div>

      <div className="card">
        <div className="gantt-container">
          {/* Header */}
          <div className="gantt-header">
            <div className="gantt-header-label">Taak</div>
            <div className="gantt-header-timeline" style={{ width: totalWidth }}>
              {headers.map((h, i) => (
                <span key={i} style={{ width: h.width }}>{h.label}</span>
              ))}
            </div>
          </div>

          {/* Rows with SVG overlay */}
          <div style={{ position: 'relative' }}>
            {taken.map(taak => (
              <div key={taak.id} className="gantt-row">
                <div className="gantt-row-label">{taak.naam}</div>
                <div className="gantt-row-timeline" style={{ width: totalWidth }}>
                  <div
                    className={`gantt-bar ${taak.status}`}
                    style={{
                      left: taak.start * dayWidth,
                      width: taak.duur * dayWidth,
                    }}
                  >
                    {taak.duur * dayWidth > 60 ? `${taak.duur}d` : ''}
                  </div>
                </div>
              </div>
            ))}

            {/* Today line */}
            {todayOffset > 0 && todayOffset < totalDays && (
              <div
                className="gantt-today"
                style={{ left: 180 + todayOffset * dayWidth }}
              />
            )}

            {/* SVG dependency arrows */}
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 180,
                width: totalWidth,
                height: taken.length * 40,
                pointerEvents: 'none',
              }}
            >
              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="8"
                  markerHeight="6"
                  refX="8"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 8 3, 0 6" fill="var(--text-muted)" />
                </marker>
              </defs>
              {depLines.map((line, i) => (
                <line
                  key={i}
                  x1={line.x1}
                  y1={line.y1}
                  x2={line.x2}
                  y2={line.y2}
                  stroke="var(--text-muted)"
                  strokeWidth="1.5"
                  strokeDasharray="4 2"
                  markerEnd="url(#arrowhead)"
                />
              ))}
            </svg>
          </div>
        </div>

        {/* Legend */}
        <div className="gantt-legend">
          {(Object.entries(statusColors) as [TaakStatus, string][]).map(([status, color]) => (
            <div key={status} className="gantt-legend-item">
              <div className="gantt-legend-color" style={{ backgroundColor: color }} />
              <span>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Planning
