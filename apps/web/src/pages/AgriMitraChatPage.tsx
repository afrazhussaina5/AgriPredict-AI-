import { useState, useRef, useEffect } from 'react'
import { Badge, Button, Card } from '../components/ui'
import { navigate } from '../router'
import { useLocationContext } from '../context/LocationContext'
import { useAuth } from '../auth/context'
import { queryAgriMitraAgent } from '../agent/agriMitraBrain'
import { useTranslation } from '../i18n/useTranslation'

type Message = {
  id: string
  sender: 'user' | 'assistant'
  text: string
  timestamp: string
  suggestedActions?: { label: string; to: string }[]
}

export function AgriMitraChatPage() {
  const { activeHub, setActiveHubId } = useLocationContext()
  const { user } = useAuth()
  const { locale } = useTranslation()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'm1',
      sender: 'assistant',
      text: `Namaste! I am AgriMitra AI (कृषि मित्र), your comprehensive agricultural intelligence agent, currently synced for ${activeHub.name} (${activeHub.district}, ${activeHub.state}).\n\nI can assist with real-time APMC prices, 10-day neural price forecasts, Store vs. Sell calculations, truck freight rates, WDRA cold storage loans, or government subsidies like PM-Kisan & PMFBY.\n\nAsk me anything in English, Hindi, or Telugu!`,
      timestamp: 'Just now',
      suggestedActions: [
        { label: '📈 10-Day Price Forecast', to: '/forecast' },
        { label: '⚖️ Mandi Profit Comparison', to: '/compare' },
        { label: '🏛️ Eligible Govt Schemes', to: '/schemes' },
        { label: '🚛 Book Transport', to: '/services' },
      ],
    },
  ])

  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  function handleSend(userText?: string) {
    const textToSend = userText || input
    if (!textToSend.trim()) return

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    if (!userText) setInput('')
    setIsTyping(true)

    setTimeout(() => {
      const agentRes = queryAgriMitraAgent(textToSend, {
        activeHub,
        userRole: user?.roles[0],
        currentLocale: locale as 'en' | 'hi' | 'te',
      })

      if (agentRes.actionToExecute?.type === 'change_location') {
        setActiveHubId(agentRes.actionToExecute.target)
      }

      const botReply =
        agentRes.reply[locale as 'en' | 'hi' | 'te'] || agentRes.reply.en

      const botMsg: Message = {
        id: `a-${Date.now()}`,
        sender: 'assistant',
        text: botReply,
        timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        suggestedActions: agentRes.suggestedActions,
      }

      setMessages((prev) => [...prev, botMsg])
      setIsTyping(false)
    }, 500)
  }

  return (
    <div className="container anim-fade-in" style={{ maxWidth: 880, paddingBottom: 'var(--space-8)' }}>
      {/* Header */}
      <div className="page-header mb-4">
        <div className="flex-between flex-wrap flex-gap-2">
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
              <Badge tone="success" className="badge--pulse">
                <span className="pulse-dot" /> Autonomous Agent Active
              </Badge>
              <Badge tone="gold">📍 {activeHub.name}</Badge>
            </div>
            <h1 className="text-title-xl">AgriMitra AI Master Farming Agent</h1>
            <p className="text-body-md muted mt-1">
              Multilingual agricultural reasoning engine covering prices, forecasts, storage, logistics, schemes &amp; trades.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <Button variant="secondary" onClick={() => navigate('/forecast')}>
              📈 10-Day ML Curve
            </Button>
            <Button variant="primary" onClick={() => navigate('/compare')}>
              ⚖️ Mandi Compare
            </Button>
          </div>
        </div>
      </div>

      {/* Quick Prompt Pills */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          overflowX: 'auto',
          paddingBottom: 'var(--space-3)',
          marginBottom: 'var(--space-3)',
        }}
      >
        {[
          `Should I store or sell ${activeHub.dominantCrop} today?`,
          `What are freight rates from ${activeHub.district} to terminal mandis?`,
          `How can I get 70% bank loan with e-NWR warehouse receipt?`,
          `Check eligibility for PM-Kisan & PMFBY in ${activeHub.state}`,
          `Switch active location to Guntur APMC (ఆంధ్రప్రదేశ్)`,
        ].map((prompt, i) => (
          <button
            key={i}
            type="button"
            className="filter-pill"
            style={{ whiteSpace: 'nowrap', cursor: 'pointer' }}
            onClick={() => handleSend(prompt)}
          >
            💬 {prompt}
          </button>
        ))}
      </div>

      {/* Chat Container Card */}
      <Card>
        <div
          style={{
            minHeight: 440,
            maxHeight: 580,
            overflowY: 'auto',
            padding: 'var(--space-3)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-4)',
          }}
        >
          {messages.map((m) => (
            <div
              key={m.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: m.sender === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <div
                style={{
                  maxWidth: '85%',
                  padding: 'var(--space-3) var(--space-4)',
                  borderRadius:
                    m.sender === 'user'
                      ? 'var(--radius-lg) var(--radius-lg) 2px var(--radius-lg)'
                      : 'var(--radius-lg) var(--radius-lg) var(--radius-lg) 2px',
                  background:
                    m.sender === 'user'
                      ? 'var(--color-primary)'
                      : 'var(--color-surface-alt)',
                  color: m.sender === 'user' ? '#FFFFFF' : 'var(--color-text)',
                  boxShadow: 'var(--shadow-sm)',
                  lineHeight: 1.6,
                  fontSize: 'var(--font-size-md)',
                  whiteSpace: 'pre-line',
                }}
              >
                {m.text}
              </div>

              {/* Action buttons suggested by bot */}
              {m.suggestedActions && m.suggestedActions.length > 0 && (
                <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
                  {m.suggestedActions.map((act, i) => (
                    <button
                      key={i}
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={() => navigate(act.to)}
                    >
                      {act.label} →
                    </button>
                  ))}
                </div>
              )}

              <span
                style={{
                  fontSize: '10px',
                  color: 'var(--color-text-muted)',
                  marginTop: '4px',
                }}
              >
                {m.timestamp}
              </span>
            </div>
          ))}

          {isTyping && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
              <span className="pulse-dot" style={{ background: 'var(--color-primary)' }} />
              AgriMitra AI reasoning through agricultural telemetry &amp; market data...
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          style={{
            display: 'flex',
            gap: 'var(--space-2)',
            marginTop: 'var(--space-4)',
            paddingTop: 'var(--space-3)',
            borderTop: '1px solid var(--color-border-subtle)',
          }}
        >
          <input
            type="text"
            className="input"
            placeholder="Type your question in Hindi, Telugu or English (e.g., कब बेचें, स्टोर करें या गाड़ी बुक करें?)..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            style={{ flex: 1 }}
          />
          <Button type="submit" variant="primary">
            Ask Agent ↵
          </Button>
        </form>
      </Card>
    </div>
  )
}
