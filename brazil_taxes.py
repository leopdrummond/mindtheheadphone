
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

load_dotenv()


USD_TO_BRL_RATE = float(os.getenv('USD_TO_BRL_RATE', '5.0'))


def calculate_brazilian_tax(usd_price: float) -> float:
    
    if usd_price <= 0:
        return 0.0
    
    if usd_price <= 50.0:
        tax = usd_price * 0.44
    else:
        tax = (usd_price * 0.92) - 20.0
        if tax < 0:
            tax = 0.0
    
    return tax


def calculate_final_price_brl(
    usd_price: float,
    usd_to_brl_rate: float = None
) -> Tuple[float, float, float]:
   
    if usd_to_brl_rate is None:
        usd_to_brl_rate = USD_TO_BRL_RATE
    
    tax_usd = calculate_brazilian_tax(usd_price)
    
    base_price_brl = usd_price * usd_to_brl_rate
    tax_brl = tax_usd * usd_to_brl_rate
    
    final_price_brl = base_price_brl + tax_brl
    
    return final_price_brl, tax_brl, base_price_brl


def format_brl_price(price: float) -> str:
   
    formatted = f"{price:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def get_exchange_rate(use_api: bool = False) -> float:
   
    if use_api:
        try:
            import requests
            response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = data.get('rates', {}).get('BRL')
                if rate:
                    logger.info(f"Fetched USD to BRL rate from API: {rate}")
                    return float(rate)
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rate from API: {e}, using default")
    
    global USD_TO_BRL_RATE
    USD_TO_BRL_RATE = float(os.getenv('USD_TO_BRL_RATE', '5.0'))
    return USD_TO_BRL_RATE


def update_exchange_rate(new_rate: float):
   
    global USD_TO_BRL_RATE
    USD_TO_BRL_RATE = new_rate
    logger.info(f"Updated USD to BRL exchange rate: {new_rate}")


if __name__ == "__main__":
   
    test_prices = [30.0, 50.0, 75.0, 100.0]
    
    print("Brazilian Tax Calculation Test")
    print("=" * 50)
    
    for price_usd in test_prices:
        tax_usd = calculate_brazilian_tax(price_usd)
        final_brl, tax_brl, base_brl = calculate_final_price_brl(price_usd)
        
        print(f"\nPrice: ${price_usd:.2f} USD")
        print(f"  Tax: ${tax_usd:.2f} USD ({tax_usd/price_usd*100:.1f}%)")
        print(f"  Base BRL: {format_brl_price(base_brl)}")
        print(f"  Tax BRL: {format_brl_price(tax_brl)}")
        print(f"  Final BRL: {format_brl_price(final_brl)}")

