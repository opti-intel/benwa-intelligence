import { useState, useEffect, useCallback } from 'react'
import { authHeaders } from './useAuth'

interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useApi<T>(url: string, options?: { skip?: boolean }) {
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: !options?.skip,
    error: null,
  })

  const fetchData = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    try {
      const res = await fetch(url)
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const data = await res.json()
      setState({ data, loading: false, error: null })
    } catch (err) {
      setState({
        data: null,
        loading: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      })
    }
  }, [url])

  useEffect(() => {
    if (!options?.skip) {
      fetchData()
    }
  }, [fetchData, options?.skip])

  return { ...state, refetch: fetchData }
}

export async function apiPost<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

// Service health check
export interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'down'
  latency?: number
  version?: string
}

export async function checkServiceHealth(baseUrl: string): Promise<ServiceHealth> {
  const start = Date.now()
  try {
    const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(5000) })
    const latency = Date.now() - start
    if (res.ok) {
      const data = await res.json().catch(() => ({}))
      return { status: 'healthy', latency, version: data.version }
    }
    return { status: 'degraded', latency }
  } catch {
    return { status: 'down' }
  }
}

// --- Domain Types ---

export type TaakStatus = 'gepland' | 'bezig' | 'klaar'

export interface Taak {
  id: string
  naam: string
  beschrijving: string
  status: TaakStatus
  startdatum: string
  einddatum: string
  toegewezen_aan: string
}

export type ResourceType = 'persoon' | 'apparatuur'

export interface Resource {
  id: string
  naam: string
  type: ResourceType
  beschikbaarheid: boolean
  toegewezen_taken: string[]
}

export interface ChatBericht {
  id: string
  rol: 'gebruiker' | 'systeem'
  tekst: string
  tijdstip: string
  taakAangemaakt?: Taak
}

export interface ExtractedTask {
  naam: string
  beschrijving: string
  startdatum: string | null
  einddatum: string | null
  toegewezen_aan: string
  locatie: string
  taak_type: string
}

export interface ChatContext {
  datum?: string | null
  tijd?: string | null
  persoon?: string
  locatie?: string
  taak_type?: string
  activiteit?: string
}

export interface ChatParseResponse {
  antwoord: string
  taak: ExtractedTask | null
  heeft_taak: boolean
  onvolledig: ChatContext | null
}

export interface PlanningTaak {
  id: string
  naam: string
  start: number
  duur: number
  status: TaakStatus
  afhankelijkheden: string[]
}

export interface ValidationResult {
  valid: boolean
  validators: {
    name: string
    passed: boolean
    confidence: number
    message?: string
    reasoning?: string
    issues?: string[]
  }[]
}

// --- API Objects ---

export const chatApi = {
  verstuur: (bericht: string, projectId: string, context?: ChatContext | null) =>
    apiPost<ChatParseResponse>('/api/airlock/chat', {
      message: bericht,
      project_id: projectId,
      context: context || null,
    }),
}

export async function apiPut<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export async function apiDelete(url: string): Promise<void> {
  const res = await fetch(url, { method: 'DELETE', headers: authHeaders() })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
}

export async function apiPatch<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export const takenApi = {
  lijst: () => apiGet<Taak[]>('/api/ingestion/tasks'),
  aanmaken: (taak: Omit<Taak, 'id'> & { id?: string }) =>
    apiPost<Taak>('/api/ingestion/tasks', taak),
  bijwerken: (id: string, taak: Omit<Taak, 'id'>) =>
    apiPut<Taak>(`/api/ingestion/tasks/${id}`, taak),
  verwijderen: (id: string) =>
    apiDelete(`/api/ingestion/tasks/${id}`),
}

export const resourcesApi = {
  lijst: () => apiGet<Resource[]>('/api/beliefs/beliefs?entity_type=resource'),
  aanmaken: (resource: Omit<Resource, 'id'>) =>
    apiPost('/api/beliefs/beliefs', resource),
}

export const planningApi = {
  schema: (taken: PlanningTaak[]) =>
    apiPost('/api/solver/solve/schedule', { tasks: taken }),
}

