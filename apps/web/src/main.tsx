import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import './design/tokens.css'
import './design/components.css'
import './styles.css'

const container = document.getElementById('root')

if (!container) {
  throw new Error('Root container #root is missing from index.html')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
