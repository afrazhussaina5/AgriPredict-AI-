# AgriPredict AI — Smart Markets, Stronger Farmers 🌱📊

> **Production Agricultural Market Intelligence & 3-Way Selling Decision Platform**  
> Tailored for Indian Farmers, Commercial Transporters, Cold Storage Operators, and Institutional Buyers.

---

## 🌟 Overview

**AgriPredict AI** transforms agricultural market discovery in India. Instead of relying on headline mandi rates, it calculates **true net realization in hand** and provides actionable guidance on:
1. **WHEN to Sell (Timing & Price Trajectories):** 7–10 day ML-powered scenario projections comparing storage fees vs. expected price appreciation.
2. **WHERE to Sell (Mandi Net Return):** Itemized deduction calculation:
   $$\text{Net Return} = \text{Mandi Modal Price} - \text{Transport} - \text{Mandi Cess (1.5\%)} - \text{Labor/Handling}$$
3. **WHOM to Sell To (Ecosystem Connections):** Direct matching with verified institutional buyers (RTGS/NEFT settlement), WDRA cold storages (with e-NWR 70% bank credit), and local commercial trucks (Tata Ace, Mahindra Bolero, Eicher).

---

## 🚀 Key Features

* **🌾 Location Intelligence Hub:**
  * 8 major agricultural hubs pre-configured: *Nashik (Lasalgaon), Guntur, Warangal, Khanna, Agra, Kolar, Indore, Pune*.
  * Location changes dynamically adapt live spot rates, weather forecasts, buyer requirements, and transport depots.
* **💡 Crop Analysis & Decision Engine (`#/analyze`):**
  * Select crop, quantity (quintals), grade (Grade A / FAQ / Grade B), and transport radius.
  * Real-time comparison between **Hold & Store** vs. **Sell Immediately Today**.
* **🤖 AgriMitra Multilingual AI Assistant:**
  * Interactive NLP assistant speaking **Hindi, English, Hinglish, and Telugu**.
  * Speech-to-Text (STT) and Text-to-Speech (TTS) for voice-driven market guidance.
* **👥 4 Dedicated Stakeholder Workspaces:**
  * **Farmer:** Net realization math, APMC comparison, voluntary produce listing (`#/lots`).
  * **Transporter:** Fleet availability management, live farmer freight matching, diesel margin calculator.
  * **Cold Storage Operator:** Chamber telematics (temperature & humidity), WDRA e-NWR loan enablement, peak release broadcast alerts.
  * **Institutional Buyer:** Commercial procurement tenders and farmer bid inquiries.
* **🏛️ Government Subsidies & Schemes (`#/schemes`):**
  * Direct eligibility guidance for PM-Kisan (₹6,000/yr), PMFBY crop insurance, AIF infrastructure subventions, and KCC loan limits.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Vanilla CSS Design System, Code-Splitting (`React.lazy`) |
| **Backend API** | FastAPI (Python 3.12+), SQLite (`preview.db`) with 16,981 indexed Agmarknet records |
| **Data Engine** | Agmarknet APMC spot arrivals feed, Open-Meteo agricultural weather API |
| **AI Subsystem** | AgriMitra multilingual NLP engine with Web Speech API integration |

---

## 💻 Local Setup & Installation

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)

### 1. Clone the Repository
```bash
git clone https://github.com/afrazhussaina5/AgriPredict-AI-.git
cd AgriPredict-AI-
```

### 2. Backend Setup (FastAPI)
```bash
cd apps/api
python -m venv ../../.venv
../../.venv/Scripts/activate     # On Windows (or source ../../.venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*API will run at: `http://127.0.0.1:8000` (Docs at `http://127.0.0.1:8000/docs`)*

### 3. Frontend Setup (React + Vite)
```bash
cd apps/web
npm install
npm run dev
```
*Frontend will run at: `http://localhost:5173`*

---

## 🔑 Demo Role Logins (1-Click Instant Access)

Available directly on `http://localhost:5173/#/signin`:
* 👨‍🌾 **Farmer:** Ramesh Patil (`+919876500001`)
* 🚚 **Transporter:** Sunil Freight (`+919876500002`)
* 🏭 **Cold Storage Operator:** Sahyadri Agro Warehouse (`+919876500003`)
* 🤝 **Institutional Buyer:** Kisan Mart Procurement (`+919876500004`)

---

## 📜 License & Provenance
* Mandi spot data indexed from official Agmarknet APMC records.
* Developed for Bharat's agricultural ecosystem.
