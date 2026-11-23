import { useState, useEffect } from 'react'
import {
  fetchAgriculturalWeather,
  type AgriculturalWeather,
} from '../api/client'
import { Badge } from './ui'
import { useTranslation } from '../i18n/useTranslation'
import { useLocationContext } from '../context/LocationContext'

export function WeatherWidget({
  compact = false,
  onLocationChange,
}: {
  compact?: boolean
  onLocationChange?: (district: string, state: string) => void
}) {
  const { locale } = useTranslation()
  const { activeHub } = useLocationContext()
  const [weather, setWeather] = useState<AgriculturalWeather | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchAgriculturalWeather(activeHub.district, activeHub.state)
      .then((data) => {
        setWeather(data)
        if (onLocationChange) {
          onLocationChange(activeHub.district, activeHub.state)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [activeHub.district, activeHub.state, onLocationChange])

  const advisoryText =
    weather?.advisory[locale as 'en' | 'hi' | 'te'] || weather?.advisory.en || ''

  if (compact && weather) {
    return (
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          background: 'var(--color-surface-alt)',
          border: '1px solid var(--color-border-subtle)',
          padding: '4px 12px',
          borderRadius: 'var(--radius-pill)',
          fontSize: 'var(--font-size-xs)',
        }}
      >
        <span style={{ fontSize: '15px' }}>
          {weather.precipitation_chance_pct > 30 ? '🌧️' : '⛅'}
        </span>
        <strong>{weather.location}</strong>:
        <span style={{ fontFamily: 'var(--font-mono-nums)', fontWeight: 600 }}>
          {weather.temp_c}°C
        </span>
        <span style={{ color: 'var(--color-text-muted)' }}>· Humidity: {weather.humidity_pct}%</span>
        <Badge tone={weather.precipitation_chance_pct > 30 ? 'warning' : 'success'}>
          Rain: {weather.precipitation_chance_pct}%
        </Badge>
      </div>
    )
  }

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, #153F35 0%, #1e4d41 100%)',
        color: '#FFFFFF',
        borderRadius: 'var(--radius-xl)',
        padding: 'var(--space-4) var(--space-5)',
        boxShadow: 'var(--shadow-md)',
        marginBottom: 'var(--space-6)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-2)',
          marginBottom: 'var(--space-3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: '22px' }}>⛅</span>
          <div>
            <strong style={{ fontSize: 'var(--font-size-md)' }}>
              Location Weather &amp; Agronomy Advisory
            </strong>
            <span style={{ fontSize: '11px', opacity: 0.8, display: 'block' }}>
              📍 {activeHub.name} ({activeHub.district}, {activeHub.state}) · {activeHub.tag}
            </span>
          </div>
        </div>

        <Badge tone={weather && weather.precipitation_chance_pct > 30 ? 'warning' : 'success'}>
          {weather ? `Rain Probability: ${weather.precipitation_chance_pct}%` : 'Loading...'}
        </Badge>
      </div>

      {loading ? (
        <div style={{ padding: 'var(--space-3)', textAlign: 'center', opacity: 0.8 }}>
          Fetching district satellite weather...
        </div>
      ) : weather ? (
        <div>
          {/* Main Weather Stats Row */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
              gap: 'var(--space-2)',
              marginBottom: 'var(--space-3)',
            }}
          >
            <div
              style={{
                background: 'rgba(255, 255, 255, 0.1)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '11px', opacity: 0.8 }}>Temp (तापमान)</div>
              <div className="num" style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>
                {weather.temp_c}°C
              </div>
            </div>

            <div
              style={{
                background: 'rgba(255, 255, 255, 0.1)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '11px', opacity: 0.8 }}>Humidity (नमी)</div>
              <div className="num" style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>
                {weather.humidity_pct}%
              </div>
            </div>

            <div
              style={{
                background: 'rgba(255, 255, 255, 0.1)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '11px', opacity: 0.8 }}>Wind (हवा की गति)</div>
              <div className="num" style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>
                {weather.wind_kph} <span style={{ fontSize: '10px' }}>km/h</span>
              </div>
            </div>

            <div
              style={{
                background: 'rgba(255, 255, 255, 0.1)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '11px', opacity: 0.8 }}>Harvest Suitability</div>
              <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, marginTop: '4px' }}>
                {weather.harvest_status.toUpperCase()}
              </div>
            </div>
          </div>

          {/* Agronomy Advisory Quote Box */}
          <div
            style={{
              background: 'rgba(233, 185, 73, 0.15)',
              borderLeft: '4px solid #E9B949',
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 'var(--font-size-sm)',
              lineHeight: 1.5,
              marginBottom: 'var(--space-3)',
            }}
          >
            <div style={{ fontWeight: 700, color: '#E9B949', marginBottom: '2px', fontSize: '11px' }}>
              🌾 {activeHub.district.toUpperCase()} KRISHI ADVISORY:
            </div>
            {advisoryText}
          </div>

          {/* 3-Day Forecast Strip */}
          <div
            style={{
              display: 'flex',
              gap: 'var(--space-2)',
              overflowX: 'auto',
              paddingTop: 'var(--space-1)',
            }}
          >
            {weather.daily_forecast.map((day, idx) => (
              <div
                key={idx}
                style={{
                  flex: 1,
                  minWidth: '90px',
                  background: 'rgba(0,0,0,0.2)',
                  borderRadius: 'var(--radius-md)',
                  padding: '6px 8px',
                  textAlign: 'center',
                  fontSize: '11px',
                }}
              >
                <div style={{ opacity: 0.7 }}>{day.day}</div>
                <div style={{ fontSize: '16px', margin: '2px 0' }}>
                  {day.rain_prob_pct > 30 ? '🌧️' : '⛅'}
                </div>
                <div style={{ fontWeight: 700 }}>{day.temp_c}°C</div>
                <div style={{ opacity: 0.8, fontSize: '10px' }}>Rain: {day.rain_prob_pct}%</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
