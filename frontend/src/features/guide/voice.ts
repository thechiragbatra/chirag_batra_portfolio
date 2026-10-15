// Voice for the AI guide, using the browser's own speech APIs (no service, no cost):
// speech recognition for asking, speech synthesis for reading answers aloud. Both are
// feature-detected; where a browser lacks them the controls are simply not shown.

import { useCallback, useEffect, useRef, useState } from 'react'
import { speakable } from './speech'

// Minimal typings: speech recognition is not in TypeScript's DOM library.
interface RecognitionResult {
  isFinal: boolean
  0: { transcript: string }
}
interface RecognitionEvent {
  resultIndex: number
  results: ArrayLike<RecognitionResult>
}
interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: RecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
  start(): void
  stop(): void
  abort(): void
}
type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export const canListen = () => recognitionCtor() !== null
export const canSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window

/**
 * Push-to-talk: start() listens, showing the words as they are heard (onInterim), and
 * calls onFinal with the whole utterance when the speaker pauses.
 */
export function useSpeechInput(onInterim: (text: string) => void, onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const recRef = useRef<Recognition | null>(null)
  const handlers = useRef({ onInterim, onFinal })
  useEffect(() => {
    handlers.current = { onInterim, onFinal }
  }, [onInterim, onFinal])

  useEffect(() => () => recRef.current?.abort(), [])

  const start = useCallback(() => {
    const Ctor = recognitionCtor()
    if (!Ctor || recRef.current) return
    const rec = new Ctor()
    rec.lang = navigator.language || 'en-US'
    rec.interimResults = true
    rec.continuous = false
    let finalText = ''
    rec.onresult = (event) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) finalText += result[0].transcript
        else interim += result[0].transcript
      }
      handlers.current.onInterim((finalText + interim).trim())
    }
    rec.onerror = (event) => {
      setError(event.error === 'not-allowed' ? 'Microphone access was blocked.' : 'Could not hear that. Try again?')
    }
    rec.onend = () => {
      recRef.current = null
      setListening(false)
      if (finalText.trim()) handlers.current.onFinal(finalText.trim())
    }
    recRef.current = rec
    setError(null)
    setListening(true)
    rec.start()
  }, [])

  const stop = useCallback(() => recRef.current?.stop(), [])
  return { listening, error, start, stop }
}

export function speak(text: string) {
  if (!canSpeak()) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(speakable(text))
  utterance.lang = navigator.language || 'en-US'
  utterance.rate = 1.05
  window.speechSynthesis.speak(utterance)
}

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel()
}
