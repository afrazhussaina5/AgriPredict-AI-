import { useState, useEffect, useRef } from 'react'
import { Badge, Button } from './ui'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'
import { useAuth } from '../auth/context'
import { queryAgriMitraAgent, type AgentResponse } from '../agent/agriMitraBrain'

type LocaleChoice = 'hi' | 'te' | 'en'

interface SpeechRecognitionEvent extends Event {
  results: {
    [index: number]: {
      [index: number]: {
        transcript: string
      }
    }
  }
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: Event) => void) | null
  onend: (() => void) | null
}

export function FloatingVoiceAssistant() {
  const { activeHub, setActiveHubId } = useLocationContext()
  const { user } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [locale, setLocale] = useState<LocaleChoice>('hi')
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [spokenText, setSpokenText] = useState('')
  const [currentResponse, setCurrentResponse] = useState<AgentResponse | null>(null)

  const recognitionRef = useRef<ISpeechRecognition | null>(null)

  // Initialize Speech Recognition if supported
  useEffect(() => {
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: new () => ISpeechRecognition }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => ISpeechRecognition }).webkitSpeechRecognition

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = false

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const transcript = event.results[0][0].transcript
        setSpokenText(transcript)
        handleUserQuery(transcript, locale)
        setIsListening(false)
      }

      recognition.onerror = () => {
        setIsListening(false)
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current = recognition
    }
  }, [locale, activeHub, user])

  // Text to Speech
  const speakAloud = (text: string, langChoice: LocaleChoice) => {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = langChoice === 'hi' ? 'hi-IN' : langChoice === 'te' ? 'te-IN' : 'en-IN'
    utterance.rate = 0.95 // Slightly slower for clear rural comprehension
    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)

    window.speechSynthesis.speak(utterance)
  }

  const startListening = () => {
    if (!recognitionRef.current) {
      // Fallback if browser doesn't support mic
      const sample =
        locale === 'hi'
          ? 'क्या प्याज का भाव बढ़ेगा या घटेगा? स्टोर करें या बेचें?'
          : locale === 'te'
            ? 'ఉల్లిపాయ ధర పెరుగుతుందా? నిల్వ చేయాలా లేదా అమ్మాలా?'
            : 'Will onion price increase? Should I store or sell?'
      setSpokenText(sample)
      handleUserQuery(sample, locale)
      return
    }

    try {
      recognitionRef.current.lang = locale === 'hi' ? 'hi-IN' : locale === 'te' ? 'te-IN' : 'en-IN'
      recognitionRef.current.start()
      setIsListening(true)
      setSpokenText('सुन रहे हैं... बोलिए (Listening...)')
    } catch {
      setIsListening(false)
    }
  }

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    setIsListening(false)
  }

  const handleUserQuery = (query: string, currentLocale: LocaleChoice) => {
    const res = queryAgriMitraAgent(query, {
      activeHub,
      userRole: user?.roles[0],
      currentLocale,
    })

    setCurrentResponse(res)

    if (res.actionToExecute?.type === 'change_location') {
      setActiveHubId(res.actionToExecute.target)
    }

    const toSpeak = res.spokenText[currentLocale] || res.spokenText.en
    speakAloud(toSpeak, currentLocale)
  }

  const displayedReply = currentResponse
    ? currentResponse.reply[locale] || currentResponse.reply.en
    : null

  return (
    <>
      {/* Floating Trigger Button */}
      <div
        style={{
          position: 'fixed',
          bottom: '1.5rem',
          right: '1.5rem',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          gap: 'var(--space-2)',
        }}
      >
        {!isOpen && (
          <div
            style={{
              background: '#153F35',
              color: '#FFFFFF',
              padding: '5px 14px',
              borderRadius: 'var(--radius-pill)',
              fontSize: '11px',
              fontWeight: 700,
              boxShadow: 'var(--shadow-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              animation: 'bounceSlow 2.5s infinite',
              border: '1px solid #E9B949',
            }}
          >
            <span style={{ color: '#E9B949' }}>🎙️</span> Bol Kar Puchiye (बोलिए)
          </div>
        )}

        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          aria-label="Open AgriMitra Multilingual Voice Assistant"
          style={{
            width: '62px',
            height: '62px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #153F35 0%, #26745A 100%)',
            border: '3px solid #E9B949',
            boxShadow: '0 8px 24px rgba(21, 63, 53, 0.40)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            fontSize: '28px',
            transition: 'var(--transition-normal)',
          }}
          className={isOpen ? '' : 'anim-float-pulse'}
        >
          {isOpen ? '✕' : '🎙️'}
        </button>
      </div>

      {/* Voice Assistant Modal Card */}
      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="AgriMitra Voice Assistant"
          className="anim-scale-in"
          style={{
            position: 'fixed',
            bottom: '6rem',
            right: '1.5rem',
            width: 'min(92vw, 420px)',
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-xl)',
            border: '2px solid var(--color-brand)',
            boxShadow: 'var(--shadow-xl)',
            zIndex: 9999,
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              background: 'linear-gradient(135deg, #153F35 0%, #26745A 100%)',
              color: '#FFFFFF',
              padding: 'var(--space-3) var(--space-4)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <span style={{ fontSize: '22px' }}>🤖</span>
                <strong style={{ fontSize: 'var(--font-size-md)' }}>AgriMitra AI Copilot</strong>
              </div>
              <p style={{ margin: 0, fontSize: '11px', opacity: 0.9 }}>
                📍 {activeHub.name} · बोलें या पूछें (Voice &amp; NLP Agent)
              </p>
            </div>

            {/* Language Switcher Buttons */}
            <div style={{ display: 'flex', gap: '4px' }}>
              {(['hi', 'te', 'en'] as LocaleChoice[]).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  onClick={() => setLocale(lang)}
                  style={{
                    padding: '3px 9px',
                    borderRadius: 'var(--radius-pill)',
                    fontSize: '11px',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: locale === lang ? '#E9B949' : 'rgba(255,255,255,0.2)',
                    color: locale === lang ? '#153F35' : '#FFFFFF',
                  }}
                >
                  {lang === 'hi' ? 'हिन्दी' : lang === 'te' ? 'తెలుగు' : 'EN'}
                </button>
              ))}
            </div>
          </div>

          {/* Interactive Mic Area */}
          <div style={{ padding: 'var(--space-4)', textAlign: 'center', maxHeight: '72vh', overflowY: 'auto' }}>
            <div
              style={{
                width: '74px',
                height: '74px',
                borderRadius: '50%',
                margin: '0 auto var(--space-3)',
                background: isListening
                  ? '#B91C1C'
                  : isSpeaking
                    ? '#E9B949'
                    : 'var(--color-surface-alt)',
                border: '3px solid var(--color-brand)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '32px',
                color: isListening || isSpeaking ? '#FFFFFF' : 'var(--color-brand)',
                cursor: 'pointer',
                boxShadow: isListening ? '0 0 0 10px rgba(185, 28, 28, 0.25)' : 'var(--shadow-sm)',
                transition: 'var(--transition-normal)',
              }}
              onClick={isListening ? stopListening : startListening}
            >
              {isListening ? '🛑' : isSpeaking ? '🔊' : '🎙️'}
            </div>

            <p style={{ fontSize: 'var(--font-size-xs)', fontWeight: 600, margin: '0 0 var(--space-2)' }}>
              {isListening
                ? '🔴 Listening... (बोलिए, हम सुन रहे हैं)'
                : isSpeaking
                  ? '🔊 Speaking Advice (उत्तर सुना रहे हैं)...'
                  : 'Tap Mic to Speak in Hindi / Telugu / English'}
            </p>

            {spokenText && (
              <div
                style={{
                  background: 'var(--color-surface-muted)',
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-3)',
                }}
              >
                <strong>You:</strong> &ldquo;{spokenText}&rdquo;
              </div>
            )}

            {/* Agent Response Box */}
            {displayedReply && (
              <div
                style={{
                  background: 'var(--color-surface-alt)',
                  border: '1px solid var(--color-border-subtle)',
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--radius-lg)',
                  fontSize: 'var(--font-size-sm)',
                  textAlign: 'left',
                  lineHeight: 1.5,
                  marginBottom: 'var(--space-3)',
                  whiteSpace: 'pre-line',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <Badge tone="success">AgriMitra AI Agent</Badge>
                  <button
                    type="button"
                    onClick={() => {
                      const toRepeat =
                        currentResponse?.spokenText[locale] || currentResponse?.spokenText.en || ''
                      speakAloud(toRepeat, locale)
                    }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: 'var(--color-brand)', fontWeight: 600 }}
                    title="Repeat speech"
                  >
                    🔊 Listen Again
                  </button>
                </div>
                <div style={{ color: 'var(--color-text)' }}>{displayedReply}</div>

                {/* Suggested Navigation Actions */}
                {currentResponse?.suggestedActions && currentResponse.suggestedActions.length > 0 && (
                  <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
                    {currentResponse.suggestedActions.map((act, i) => (
                      <Button
                        key={i}
                        variant="primary"
                        className="btn--sm"
                        onClick={() => {
                          setIsOpen(false)
                          navigate(act.to)
                        }}
                      >
                        {act.label} →
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Quick-Ask Chips */}
            <div style={{ textAlign: 'left', marginTop: 'var(--space-3)' }}>
              <span className="text-caption muted" style={{ display: 'block', marginBottom: '6px' }}>
                Quick agricultural prompts (सवाल टैप करें):
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {[
                  { text: '🧅 प्याज का भाव बढ़ेगा या घटेगा? स्टोर करें या बेचें?', lang: 'hi' },
                  { text: '🚛 नासिक मंडी के लिए ट्रक रेट क्या है?', lang: 'hi' },
                  { text: '🏛️ PM किसान और फसल बीमा योजना कैसे मिलेगी?', lang: 'hi' },
                  { text: '⛅ आज का मौसम और तुड़ाई सलाह क्या है?', lang: 'hi' },
                  { text: '📍 Switch location to Guntur APMC (ఆంధ్రప్రదేశ్)', lang: 'en' },
                ].map((chip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setSpokenText(chip.text)
                      handleUserQuery(chip.text, locale)
                    }}
                    style={{
                      textAlign: 'left',
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      padding: '6px 10px',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '11px',
                      cursor: 'pointer',
                      transition: 'var(--transition-fast)',
                      color: 'var(--color-text)',
                    }}
                  >
                    💬 {chip.text}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
