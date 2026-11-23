import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type AgriculturalHub = {
  id: string
  name: string
  nameHi: string
  nameTe: string
  state: string
  district: string
  primaryMandi: string
  tag: string
  icon: string
  dominantCrop: string
  soilType: string
  avgRainfallMm: number
}

export const AGRICULTURAL_HUBS: AgriculturalHub[] = [
  {
    id: 'nashik',
    name: 'Nashik (Lasalgaon)',
    nameHi: 'नासिक (लासलगांव)',
    nameTe: 'నాసిక్ (లాసల్‌గావ్)',
    state: 'Maharashtra',
    district: 'Nashik',
    primaryMandi: 'Lasalgaon APMC',
    tag: '🧅 Onion & Grape Capital',
    icon: '🧅',
    dominantCrop: 'Onion',
    soilType: 'Black Cotton & Red Sandy Loam',
    avgRainfallMm: 720,
  },
  {
    id: 'guntur',
    name: 'Guntur APMC Yard',
    nameHi: 'गुंटूर APMC यार्ड',
    nameTe: 'గుంటూరు మార్కెట్ యార్డ్',
    state: 'Andhra Pradesh',
    district: 'Guntur',
    primaryMandi: 'Guntur APMC Yard',
    tag: '🌶️ Asia\'s Largest Chilli Hub',
    icon: '🌶️',
    dominantCrop: 'Green Chilli',
    soilType: 'Heavy Black Clay & Alluvial',
    avgRainfallMm: 860,
  },
  {
    id: 'warangal',
    name: 'Warangal Cotton Hub',
    nameHi: 'वारंगल कपास मंडी',
    nameTe: 'వరంగల్ ఎనుమాముల మార్కెట్',
    state: 'Telangana',
    district: 'Warangal',
    primaryMandi: 'Warangal APMC',
    tag: '☁️ Cotton, Chilli & Maize Hub',
    icon: '☁️',
    dominantCrop: 'Cotton',
    soilType: 'Red Chalkas & Deep Black',
    avgRainfallMm: 990,
  },
  {
    id: 'khanna',
    name: 'Khanna Grain Market',
    nameHi: 'खन्ना अनाज मंडी',
    nameTe: 'ఖన్నా ధాన్యం మార్కెట్',
    state: 'Punjab',
    district: 'Ludhiana',
    primaryMandi: 'Khanna Grain Market',
    tag: '🌾 Asia\'s Largest Wheat Market',
    icon: '🌾',
    dominantCrop: 'Wheat',
    soilType: 'Rich Indo-Gangetic Alluvium',
    avgRainfallMm: 680,
  },
  {
    id: 'agra',
    name: 'Agra Potato & Grain Hub',
    nameHi: 'आगरा आलू व अनाज मंडी',
    nameTe: 'ఆగ్రా బంగాళాదుంప మార్కెట్',
    state: 'Uttar Pradesh',
    district: 'Agra',
    primaryMandi: 'Agra APMC',
    tag: '🥔 Leading Potato & Mustard Belt',
    icon: '🥔',
    dominantCrop: 'Potato',
    soilType: 'Alluvial Loam',
    avgRainfallMm: 650,
  },
  {
    id: 'kolar',
    name: 'Kolar Tomato Terminal',
    nameHi: 'कोलार टमाटर मंडी',
    nameTe: 'కోలార్ టమాటా మార్కెట్',
    state: 'Karnataka',
    district: 'Kolar',
    primaryMandi: 'Kolar APMC',
    tag: '🍅 South India Tomato Capital',
    icon: '🍅',
    dominantCrop: 'Tomato',
    soilType: 'Red Sandy Loam',
    avgRainfallMm: 740,
  },
  {
    id: 'indore',
    name: 'Indore Mandi',
    nameHi: 'इंदौर कृषि उपज मंडी',
    nameTe: 'ఇండోర్ మార్కెట్',
    state: 'Madhya Pradesh',
    district: 'Indore',
    primaryMandi: 'Indore APMC',
    tag: '🌱 Soybean & Malwa Wheat Hub',
    icon: '🌱',
    dominantCrop: 'Soybean',
    soilType: 'Medium to Deep Black',
    avgRainfallMm: 950,
  },
  {
    id: 'pune',
    name: 'Narayangaon (Pune)',
    nameHi: 'नारायणगांव (पुणे)',
    nameTe: 'నారాయణగావ్ (పుణె)',
    state: 'Maharashtra',
    district: 'Pune',
    primaryMandi: 'Narayangaon APMC',
    tag: '🍅 Vegetable & Tomato Hub',
    icon: '🥦',
    dominantCrop: 'Tomato',
    soilType: 'Medium Black Basaltic',
    avgRainfallMm: 710,
  },
]

type LocationContextValue = {
  activeHub: AgriculturalHub
  setActiveHubId: (id: string) => void
  hubs: AgriculturalHub[]
}

const LocationContext = createContext<LocationContextValue | null>(null)

const STORAGE_KEY = 'agripredict_selected_hub'

export function LocationProvider({ children }: { children: ReactNode }) {
  const [activeHubId, setActiveHubId] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved && AGRICULTURAL_HUBS.some((h) => h.id === saved)) {
        return saved
      }
    } catch {
      // ignore localStorage errors
    }
    return 'nashik'
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, activeHubId)
    } catch {
      // ignore localStorage errors
    }
  }, [activeHubId])

  const activeHub = AGRICULTURAL_HUBS.find((h) => h.id === activeHubId) || AGRICULTURAL_HUBS[0]

  return (
    <LocationContext.Provider
      value={{
        activeHub,
        setActiveHubId,
        hubs: AGRICULTURAL_HUBS,
      }}
    >
      {children}
    </LocationContext.Provider>
  )
}

export function useLocationContext(): LocationContextValue {
  const ctx = useContext(LocationContext)
  if (!ctx) {
    throw new Error('useLocationContext must be used within a LocationProvider')
  }
  return ctx
}
