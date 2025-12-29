import logging
import re
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Product:
    name: str
    category: str
    section: str
    base_price: float
    final_price: float
    tax_rate: float
    aliexpress_link: str
    description: str = ""
    sound_signature: str = ""
    availability: str = ""
    review_link: str = ""
    
    @property
    def product_id(self) -> Optional[str]:
        if not self.aliexpress_link:
            return None
        match = re.search(r'/item/(\d+)\.html', self.aliexpress_link)
        if match:
            return match.group(1)
        return None


class GoogleSheetsReader:
    
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.base_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export"
    
    def _get_csv_url(self, sheet_name: str = None, gid: int = None) -> str:
        url = f"{self.base_url}?format=csv"
        if gid is not None:
            url += f"&gid={gid}"
        return url
    
    def _parse_price(self, price_str: str) -> float:
        if not price_str or price_str == "-":
            return 0.0
        
        # Skip URLs (YouTube links, etc.)
        if price_str.strip().startswith("http://") or price_str.strip().startswith("https://"):
            return 0.0
        
        try:
            cleaned = price_str.replace("R$", "").replace(" ", "").strip()
            
            # Skip if it looks like a URL after cleaning
            if cleaned.startswith("http") or "youtu" in cleaned.lower() or "www." in cleaned.lower():
                return 0.0
            
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            
            return float(cleaned)
        except (ValueError, AttributeError):
            # Only log warning if it's not obviously a URL
            if not (price_str.strip().startswith("http") or "youtu" in price_str.lower()):
                logger.warning(f"Could not parse price: {price_str}")
            return 0.0
    
    def _parse_tax_rate(self, tax_str: str) -> float:
        if not tax_str or tax_str == "-":
            return 0.0
        try:
            cleaned = tax_str.replace("%", "").replace(",", ".").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return 0.0
    
    def _fetch_sheet_csv(self, gid: int) -> str:
        url = self._get_csv_url(gid=gid)
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/csv,*/*'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            response.encoding = 'utf-8'
            content = response.text
            
            if content.strip().startswith('<!DOCTYPE') or content.strip().startswith('<html'):
                logger.error(f"Got HTML response instead of CSV for gid={gid}. Spreadsheet may not be publicly accessible.")
                return ""
            
            return content
        except requests.RequestException as e:
            logger.error(f"Failed to fetch sheet (gid={gid}): {e}")
            return ""
    
    def _parse_csv_content(self, csv_content: str, category: str) -> List[Product]:
        products = []
        lines = csv_content.strip().split("\n")
        
        current_section = "default"
        header_indices = {}
        expecting_header = False
        
        for line in lines:
            cells = self._parse_csv_line(line)
            
            if not cells or all(not c.strip() for c in cells):
                continue
            
            first_cell = cells[0].strip().lower() if cells else ""
            
            if first_cell and not first_cell.startswith("produto"):
                non_empty = sum(1 for c in cells if c.strip())
                if non_empty <= 3 and first_cell not in ["", "-"]:
                    has_price = any("r$" in c.lower() or re.match(r'^\d+[.,]?\d*$', c.strip()) for c in cells[1:6] if c.strip())
                    has_link = any("aliexpress" in c.lower() or "http" in c.lower() for c in cells if c.strip())
                    
                    if not has_price and not has_link:
                        current_section = cells[0].strip()
                        expecting_header = True
                        logger.debug(f"Found section: {current_section}")
                        continue
            
            if first_cell == "produto":
                header_indices = {}
                for idx, cell in enumerate(cells):
                    cell_lower = cell.strip().lower()
                    if cell_lower == "produto":
                        header_indices["name"] = idx
                    elif cell_lower == "assinatura sonora":
                        header_indices["sound_signature"] = idx
                    elif cell_lower == "disponibilidade":
                        header_indices["availability"] = idx
                    elif cell_lower == "preço base" or cell_lower == "preco base":
                        header_indices["base_price"] = idx
                    elif cell_lower == "impostos":
                        header_indices["tax"] = idx
                    elif cell_lower == "preço final" or cell_lower == "preco final":
                        header_indices["final_price"] = idx
                    elif cell_lower == "review":
                        header_indices["review"] = idx
                    elif cell_lower == "link":
                        header_indices["link"] = idx
                    elif cell_lower == "descrição" or cell_lower == "descricao":
                        header_indices["description"] = idx
                
                expecting_header = False
                continue
            
            if not header_indices:
                continue
            
            try:
                name_idx = header_indices.get("name", 0)
                name = cells[name_idx].strip() if name_idx < len(cells) else ""
                
                if not name or name.lower() == "produto":
                    continue
                
                link_idx = header_indices.get("link", 7)
                link = cells[link_idx].strip() if link_idx < len(cells) else ""
                
                if not link or "aliexpress" not in link.lower():
                    continue
                
                base_price_idx = header_indices.get("base_price", 3)
                base_price_str = cells[base_price_idx].strip() if base_price_idx < len(cells) else "0"
                base_price = self._parse_price(base_price_str)
                
                final_price_idx = header_indices.get("final_price", 5)
                final_price_str = cells[final_price_idx].strip() if final_price_idx < len(cells) else "0"
                final_price = self._parse_price(final_price_str)
                
                tax_idx = header_indices.get("tax", 4)
                tax_str = cells[tax_idx].strip() if tax_idx < len(cells) else "0"
                tax_rate = self._parse_tax_rate(tax_str)
                
                sound_idx = header_indices.get("sound_signature", 1)
                sound_signature = cells[sound_idx].strip() if sound_idx < len(cells) else ""
                
                avail_idx = header_indices.get("availability", 2)
                availability = cells[avail_idx].strip() if avail_idx < len(cells) else ""
                
                review_idx = header_indices.get("review", 6)
                review_link = cells[review_idx].strip() if review_idx < len(cells) else ""
                
                desc_idx = header_indices.get("description", 8)
                description = cells[desc_idx].strip() if desc_idx < len(cells) else ""
                
                product = Product(
                    name=name,
                    category=category,
                    section=current_section,
                    base_price=base_price,
                    final_price=final_price,
                    tax_rate=tax_rate,
                    aliexpress_link=link,
                    description=description,
                    sound_signature=sound_signature,
                    availability=availability,
                    review_link=review_link
                )
                
                products.append(product)
                logger.debug(f"Parsed product: {name} - R${base_price} - {link}")
                
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                continue
        
        return products
    
    def _parse_csv_line(self, line: str) -> List[str]:
        import csv
        from io import StringIO
        
        try:
            reader = csv.reader(StringIO(line))
            for row in reader:
                return row
        except:
            return line.split(",")
        
        return []
    
    def get_all_products(self, sheet_gids: Dict[str, int] = None) -> List[Product]:
        if sheet_gids is None:
            sheet_gids = {
                "EARPHONES": 0,  
            }
        
        all_products = []
        
        for sheet_name, gid in sheet_gids.items():
            logger.info(f"Fetching products from sheet: {sheet_name} (gid={gid})")
            csv_content = self._fetch_sheet_csv(gid)
            
            if csv_content:
                products = self._parse_csv_content(csv_content, category=sheet_name)
                all_products.extend(products)
                logger.info(f"Found {len(products)} products in {sheet_name}")
            else:
                logger.warning(f"No content retrieved from sheet: {sheet_name}")
        
        logger.info(f"Total products fetched: {len(all_products)}")
        return all_products
    
    def get_products_with_aliexpress_links(self, sheet_gids: Dict[str, int] = None) -> List[Product]:
        all_products = self.get_all_products(sheet_gids)
        return [p for p in all_products if p.aliexpress_link and "aliexpress" in p.aliexpress_link.lower()]


def get_spreadsheet_id_from_url(url: str) -> Optional[str]:
   
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')
    
    reader = GoogleSheetsReader(SPREADSHEET_ID)
    
    sheet_gids = {
        "EARPHONES": 0,
    }
    
    products = reader.get_products_with_aliexpress_links(sheet_gids)
    
    print(f"\nFound {len(products)} products with AliExpress links:")
    for p in products[:5]:
        print(f"  - {p.name}: R${p.base_price:.2f} -> R${p.final_price:.2f}")
        print(f"    Link: {p.aliexpress_link}")

