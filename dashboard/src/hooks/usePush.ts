import { useState, useEffect, useCallback } from 'react'
import { pushApi } from './useApi'

export type PushStatus = 'niet-ondersteund' | 'uit' | 'aan' | 'geweigerd' | 'bezig'

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(b64)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

/**
 * Push-meldingen op dit apparaat aan/uit zetten.
 *
 * Let op voor iPhone: daar werkt push alleen als de app via
 * "Zet op beginscherm" is geïnstalleerd (iOS 16.4+).
 */
export function usePush() {
  const [status, setStatus] = useState<PushStatus>('bezig')

  // Bepaal de huidige stand bij het laden
  useEffect(() => {
    ;(async () => {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        setStatus('niet-ondersteund')
        return
      }
      if (Notification.permission === 'denied') {
        setStatus('geweigerd')
        return
      }
      try {
        const reg = await navigator.serviceWorker.ready
        const bestaand = await reg.pushManager.getSubscription()
        setStatus(bestaand ? 'aan' : 'uit')
      } catch {
        setStatus('uit')
      }
    })()
  }, [])

  const zetAan = useCallback(async () => {
    setStatus('bezig')
    try {
      const toestemming = await Notification.requestPermission()
      if (toestemming !== 'granted') {
        setStatus(toestemming === 'denied' ? 'geweigerd' : 'uit')
        return
      }
      const { publieke_sleutel } = await pushApi.publiekeSleutel()
      if (!publieke_sleutel) {
        alert('Push is nog niet geconfigureerd op de server (VAPID-sleutels ontbreken).')
        setStatus('uit')
        return
      }
      const reg = await navigator.serviceWorker.ready
      const abonnement = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publieke_sleutel),
      })
      const json = abonnement.toJSON()
      await pushApi.abonneer({
        endpoint: json.endpoint || '',
        keys: { p256dh: json.keys?.p256dh || '', auth: json.keys?.auth || '' },
      })
      setStatus('aan')
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Meldingen aanzetten mislukt')
      setStatus('uit')
    }
  }, [])

  const zetUit = useCallback(async () => {
    setStatus('bezig')
    try {
      const reg = await navigator.serviceWorker.ready
      const abonnement = await reg.pushManager.getSubscription()
      if (abonnement) {
        await pushApi.afmelden(abonnement.endpoint).catch(() => {})
        await abonnement.unsubscribe()
      }
    } finally {
      setStatus('uit')
    }
  }, [])

  return { status, zetAan, zetUit }
}
