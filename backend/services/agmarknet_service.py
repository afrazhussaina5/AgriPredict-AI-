# AgriPredict AI - Agmarknet Official Portal API Service
"""
Real-time mandi price data from Agmarknet Official Portal.
Fetches live daily mandi prices for Andhra Pradesh and other states.
"""

import os
import re
import logging
import asyncio
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("agmarknet_service")

# Agmarknet Official Portal URLs
AGMARKNET_BASE_URL = "https://agmarknet.gov.in"
AGMARKNET_SEARCH_URL = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
AGMARKNET_REPORT_URL = "https://agmarknet.gov.in/PriceAndArrival/CommodityWiseDailyReport.aspx"

# State codes for Agmarknet (Andhra Pradesh = AP)
STATE_CODES = {
    "Andhra Pradesh": "AP",
    "Telangana": "TG",
    "Tamil Nadu": "TN",
    "Karnataka": "KA",
    "Kerala": "KL",
    "Maharashtra": "MH",
    "Gujarat": "GJ",
    "Madhya Pradesh": "MP",
    "Uttar Pradesh": "UP",
    "Rajasthan": "RJ",
    "West Bengal": "WB",
    "Bihar": "BR",
    "Odisha": "OR",
    "Punjab": "PB",
    "Haryana": "HR",
    "Chhattisgarh": "CG",
    "Jharkhand": "JH",
    "Assam": "AS",
    "Delhi": "DL",
    "Jammu and Kashmir": "JK",
    "Himachal Pradesh": "HP",
    "Uttarakhand": "UK",
    "Goa": "GA",
    "Tripura": "TR",
    "Manipur": "MN",
    "Meghalaya": "ML",
    "Mizoram": "MZ",
    "Nagaland": "NL",
    "Arunachal Pradesh": "AR",
    "Sikkim": "SK",
}

# Commodity name mapping (Agmarknet names -> our internal IDs)
COMMODITY_NAME_MAP = {
    "onion": ["Onion", "Onion (Red)", "Onion (White)"],
    "tomato": ["Tomato", "Tomato (Hybrid)", "Tomato (Local)"],
    "potato": ["Potato", "Potato (Chipsona)", "Potato (Jyoti)"],
    "garlic": ["Garlic", "Garlic (Desi)", "Garlic (Ooty)"],
    "ginger": ["Ginger", "Ginger (Fresh)", "Ginger (Dry)"],
    "potato": ["Potato", "Potato (Kufri)", "Potato (Jyoti)"],
    "wheat": ["Wheat", "Wheat (Dara)", "Wheat (Lokwan)", "Wheat (Sharbati)"],
    "paddy": ["Paddy", "Paddy (Common)", "Paddy (Grade A)", "Paddy (Basmati)"],
    "maize": ["Maize", "Maize (Yellow)", "Maize (White)"],
    "chana_gram": ["Gram", "Gram (Desi)", "Gram (Kabuli)"],
    "arhar_tur": ["Arhar/Tur", "Tur", "Tur (Red)"],
    "moong": ["Moong", "Moong (Green)", "Moong (Yellow)"],
    "soybean": ["Soybean", "Soybean (Yellow)", "Soybean (Black)"],
    "groundnut": ["Groundnut", "Groundnut (Pod)", "Groundnut (Kernel)"],
    "cotton": ["Cotton", "Cotton (Kapah)", "Cotton (Lint)"],
    "chilli": ["Chilli", "Chilli (Dry)", "Chilli (Green)", "Chilli (Byadgi)", "Chilli (Guntur)"],
    "turmeric": ["Turmeric", "Turmeric (Finger)", "Turmeric (Bulb)"],
    "cumin_jeera": ["Cumin/Jeera", "Jeera", "Cumin"],
    "mustard": ["Mustard", "Mustard (Black)", "Mustard (Yellow)"],
    "garlic": ["Garlic"],
    "ginger": ["Ginger"],
    "cotton": ["Cotton"],
    "sugarcane": ["Sugarcane"],
    "banana": ["Banana", "Banana (Green)", "Banana (Ripe)"],
    "apple": ["Apple"],
    "mango": ["Mango"],
    "orange": ["Orange", "Orange (Mosambi)", "Orange (Kinnow)"],
    "grapes": ["Grapes"],
    "pomegranate": ["Pomegranate"],
}

# Reverse mapping for API commodity names
AGMARKNET_COMMODITY_TO_ID = {}
for internal_id, names in COMMODITY_NAME_MAP.items():
    for name in names:
        AGMARKNET_COMMODITY_TO_ID[name.lower().strip()] = internal_id


@dataclass
class MandiPriceRecord:
    """Normalized mandi price record from Agmarknet"""
    state: str
    district: str
    market: str
    commodity: str
    variety: str
    grade: str
    arrival_date: date
    min_price: float
    max_price: float
    modal_price: float
    arrival_quantity: Optional[float] = None
    source: str = "agmarknet"
    source_url: str = ""
    fetched_at: datetime = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "district": self.district,
            "market": self.market,
            "commodity": self.commodity,
            "variety": self.variety,
            "grade": self.grade,
            "arrival_date": self.arrival_date.isoformat(),
            "min_price": self.min_price,
            "max_price": self.max_price,
            "modal_price": self.modal_price,
            "arrival_quantity": self.arrival_quantity,
            "source": self.source,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at.isoformat(),
        }


class AgmarknetService:
    """
    Service to fetch real-time mandi prices from Agmarknet Official Portal.
    Uses web scraping since Agmarknet doesn't provide a public JSON API.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        self._state_cache = {}
        self._commodity_cache = {}
    
    def _get_state_code(self, state_name: str) -> Optional[str]:
        """Get Agmarknet state code from state name"""
        state_normalized = state_name.strip().lower()
        for name, code in STATE_CODES.items():
            if name.lower() == state_normalized:
                return code
        return None
    
    def _normalize_commodity_name(self, agmarknet_name: str) -> str:
        """Map Agmarknet commodity name to internal ID"""
        name_lower = agmarknet_name.lower().strip()
        # Direct match
        if name_lower in AGMARKNET_COMMODITY_TO_ID:
            return AGMARKNET_COMMODITY_TO_ID[name_lower]
        # Partial match
        for agm_name, internal_id in AGMARKNET_COMMODITY_TO_ID.items():
            if agm_name in name_lower or name_lower in agm_name:
                return internal_id
        # Fallback: slugify
        return agmarknet_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
    
    async def fetch_latest_prices(
        self,
        state: str = "Andhra Pradesh",
        district: Optional[str] = None,
        commodity: Optional[str] = None,
        arrival_date: Optional[date] = None,
    ) -> List[MandiPriceRecord]:
        """
        Fetch latest mandi prices from Agmarknet for a given state.
        Scrapes the Agmarknet daily price report page.
        """
        state_code = self._get_state_code(state)
        if not state_code:
            logger.warning(f"Unknown state code for: {state}")
            return []
        
        # Default to latest date (yesterday's data usually available)
        if arrival_date is None:
            arrival_date = date.today() - timedelta(days=1)
        
        # Build URL for Agmarknet daily price report
        # Format: https://agmarknet.gov.in/PriceAndArrival/CommodityWiseDailyReport.aspx
        # Parameters: State, District, Commodity, Date
        
        records = []
        
        try:
            # Use the commodity-wise daily report page
            params = {
                "TxnType": "D",
                "State": state_code,
                "District": self._get_district_code(state_code, district) if district else "ALL",
                "Commodity": self._get_commodity_code(commodity) if commodity else "ALL",
                "Market": "ALL",
                "Date": arrival_date.strftime("%d-%b-%Y"),
            }
            
            # Try multiple possible Agmarknet report URLs
            urls_to_try = [
                "https://agmarknet.gov.in/PriceAndArrival/CommodityWiseDailyReport.aspx",
                "https://agmarknet.gov.in/PriceAndArrival/CommodityDailyReport.aspx",
                "https://agmarknet.gov.in/SearchCmmMkt.aspx",
            ]
            
            for url in urls_to_try:
                try:
                    records = await self._fetch_from_url(url, params)
                    if records:
                        logger.info(f"Successfully fetched {len(records)} records from {url}")
                        return records
                except Exception as e:
                    logger.warning(f"Failed to fetch from {url}: {e}")
                    continue
            
            # If all URLs fail, try the search page approach
            return await self._fetch_via_search_page(state_code, commodity, arrival_date)
            
        except Exception as e:
            logger.error(f"Error fetching Agmarknet data: {e}")
            return []
    
    async def _fetch_from_url(self, url: str, params: dict) -> List[MandiPriceRecord]:
        """Fetch and parse data from a specific Agmarknet URL"""
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the price table
            # Agmarknet typically uses tables with class 'table' or specific IDs
            tables = soup.find_all('table')
            
            records = []
            for table in tables:
                # Look for price data tables
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Check if this is a price table by checking headers
                headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
                header_text = ' '.join(headers)
                
                if any(keyword in header_text for keyword in ['price', 'modal', 'arrival', 'market', 'commodity', 'mandi']):
                    records.extend(self._parse_price_table(table))
            
            return records
            
        except Exception as e:
            logger.error(f"Error fetching from {url}: {e}")
            return []
    
    def _parse_price_table(self, table) -> List[MandiPriceRecord]:
        """Parse a price table from Agmarknet HTML"""
        records = []
        rows = table.find_all('tr')
        
        if len(rows) < 2:
            return records
        
        # Get header mapping
        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
        
        # Map column indices
        col_map = {}
        for idx, header in enumerate(headers):
            header_lower = header.lower()
            if 'state' in header_lower:
                col_map['state'] = idx
            elif 'district' in header_lower:
                col_map['district'] = idx
            elif 'market' in header_lower or 'mandi' in header_lower:
                col_map['market'] = idx
            elif 'commodity' in header_lower or 'crop' in header_lower:
                col_map['commodity'] = idx
            elif 'variety' in header_lower:
                col_map['variety'] = idx
            elif 'grade' in header_lower:
                col_map['grade'] = idx
            elif 'arrival' in header_lower and 'date' in header_lower:
                col_map['arrival_date'] = idx
            elif 'min' in header_lower and 'price' in header_lower:
                col_map['min_price'] = idx
            elif 'max' in header_lower and 'price' in header_lower:
                col_map['max_price'] = idx
            elif 'modal' in header_lower and 'price' in header_lower:
                col_map['modal_price'] = idx
            elif 'arrival' in header_lower and 'quantity' in header_lower:
                col_map['arrival_quantity'] = idx
        
        # Parse data rows
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < len(col_map):
                continue
            
            try:
                record = MandiPriceRecord(
                    state=cells[col_map.get('state', 0)].get_text(strip=True) if col_map.get('state') is not None else "",
                    district=cells[col_map.get('district', 1)].get_text(strip=True) if col_map.get('district') is not None else "",
                    market=cells[col_map.get('market', 2)].get_text(strip=True) if col_map.get('market') is not None else "",
                    commodity=cells[col_map.get('commodity', 3)].get_text(strip=True) if col_map.get('commodity') is not None else "",
                    variety=cells[col_map.get('variety', 4)].get_text(strip=True) if col_map.get('variety') is not None else "FAQ",
                    grade=cells[col_map.get('grade', 5)].get_text(strip=True) if col_map.get('grade') is not None else "FAQ",
                    arrival_date=self._parse_date(cells[col_map.get('arrival_date', 6)].get_text(strip=True)) if col_map.get('arrival_date') is not None else date.today(),
                    min_price=self._parse_price(cells[col_map.get('min_price', 7)].get_text(strip=True)) if col_map.get('min_price') is not None else 0,
                    max_price=self._parse_price(cells[col_map.get('max_price', 8)].get_text(strip=True)) if col_map.get('max_price') is not None else 0,
                    modal_price=self._parse_price(cells[col_map.get('modal_price', 9)].get_text(strip=True)) if col_map.get('modal_price') is not None else 0,
                    arrival_quantity=self._parse_float(cells[col_map.get('arrival_quantity', 10)].get_text(strip=True)) if col_map.get('arrival_quantity') is not None else None,
                )
                
                # Validate required fields
                if record.modal_price > 0 and record.market and record.commodity:
                    record.commodity = self._normalize_commodity_name(record.commodity)
                    records.append(record)
                    
            except Exception as e:
                logger.debug(f"Error parsing row: {e}")
                continue
        
        return records
    
    def _parse_date(self, date_str: str) -> date:
        """Parse date string from Agmarknet format"""
        date_str = date_str.strip()
        formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d-%b-%Y",
            "%d-%b-%y",
            "%Y-%m-%d",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return date.today()
    
    def _parse_price(self, price_str: str) -> float:
        """Parse price string to float"""
        if not price_str:
            return 0.0
        # Remove currency symbols, commas, spaces
        cleaned = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
    
    def _parse_float(self, val_str: str) -> Optional[float]:
        """Parse float from string"""
        if not val_str:
            return None
        cleaned = re.sub(r'[^\d.]', '', val_str.replace(',', ''))
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    
    def _get_district_code(self, state_code: str, district: str) -> str:
        """Get district code for Agmarknet (simplified)"""
        # Agmarknet uses district names directly in many cases
        return district if district else "ALL"
    
    def _get_commodity_code(self, commodity: str) -> str:
        """Get Agmarknet commodity code"""
        commodity_lower = commodity.lower().strip()
        # Map internal ID to Agmarknet commodity code
        commodity_codes = {
            "onion": "ONION",
            "tomato": "TOMATO",
            "potato": "POTATO",
            "onion": "ONION",
            "wheat": "WHEAT",
            "paddy": "PADDY",
            "maize": "MAIZE",
            "chana_gram": "GRAM",
            "arhar_tur": "ARHAR",
            "moong": "MOONG",
            "soybean": "SOYABEAN",
            "groundnut": "GROUNDNUT",
            "cotton": "COTTON",
            "chilli": "CHILLI",
            "turmeric": "TURMERIC",
            "cumin_jeera": "JEERA",
            "mustard": "MUSTARD",
            "garlic": "GARLIC",
            "ginger": "GINGER",
            "cotton": "COTTON",
            "sugarcane": "SUGARCANE",
            "banana": "BANANA",
            "apple": "APPLE",
        }
        return commodity_codes.get(commodity_lower, commodity.upper())
    
    async def _fetch_via_search_page(self, state_code: str, commodity: Optional[str], arrival_date: date) -> List[MandiPriceRecord]:
        """Alternative: Use Agmarknet search page"""
        try:
            # Try the search page with form submission
            search_url = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
            
            # First get the page to get viewstate
            resp = self.session.get(search_url, timeout=30)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Find form fields
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})
            viewstategenerator = soup.find(id='__VIEWSTATEGENERATOR')
            eventvalidation = soup.find(id='__EVENTVALIDATION')
            
            # This is complex - for now return empty and rely on other methods
            return []
            
        except Exception as e:
            logger.error(f"Search page fetch failed: {e}")
            return []


# Global instance
_agmarknet_service = None

def get_agmarknet_service() -> AgmarknetService:
    global _agmarknet_service
    if _agmarknet_service is None:
        _agmarknet_service = AgmarknetService()
    return _agmarknet_service