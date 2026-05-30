"""
Realistic demo data for dividend-paying stocks with options.
Used as fallback when the external API (yfinance) is unavailable.
Data is approximated from real market values for illustration.
"""
from datetime import datetime, timedelta

DEMO_STOCKS = {
    "KO": {
        "ticker": "KO",
        "name": "The Coca-Cola Company",
        "price": 63.20,
        "exchange": "NYSE",
        "annual_div_per_share": 1.94,
        "div_yield_pct": 3.07,
        "sector": "Consumer Staples",
        "market_cap": 272_000_000_000,
    },
    "JNJ": {
        "ticker": "JNJ",
        "name": "Johnson & Johnson",
        "price": 157.40,
        "exchange": "NYSE",
        "annual_div_per_share": 4.96,
        "div_yield_pct": 3.15,
        "sector": "Healthcare",
        "market_cap": 379_000_000_000,
    },
    "VZ": {
        "ticker": "VZ",
        "name": "Verizon Communications Inc.",
        "price": 41.30,
        "exchange": "NYSE",
        "annual_div_per_share": 2.66,
        "div_yield_pct": 6.44,
        "sector": "Communication Services",
        "market_cap": 173_000_000_000,
    },
    "T": {
        "ticker": "T",
        "name": "AT&T Inc.",
        "price": 22.80,
        "exchange": "NYSE",
        "annual_div_per_share": 1.11,
        "div_yield_pct": 4.87,
        "sector": "Communication Services",
        "market_cap": 163_000_000_000,
    },
    "MO": {
        "ticker": "MO",
        "name": "Altria Group, Inc.",
        "price": 53.70,
        "exchange": "NYSE",
        "annual_div_per_share": 3.92,
        "div_yield_pct": 7.30,
        "sector": "Consumer Staples",
        "market_cap": 92_000_000_000,
    },
    "XOM": {
        "ticker": "XOM",
        "name": "Exxon Mobil Corporation",
        "price": 112.50,
        "exchange": "NYSE",
        "annual_div_per_share": 3.80,
        "div_yield_pct": 3.38,
        "sector": "Energy",
        "market_cap": 490_000_000_000,
    },
    "PFE": {
        "ticker": "PFE",
        "name": "Pfizer Inc.",
        "price": 27.60,
        "exchange": "NYSE",
        "annual_div_per_share": 1.68,
        "div_yield_pct": 6.09,
        "sector": "Healthcare",
        "market_cap": 156_000_000_000,
    },
    "AAPL": {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "price": 211.50,
        "exchange": "NASDAQ",
        "annual_div_per_share": 1.00,
        "div_yield_pct": 0.47,
        "sector": "Technology",
        "market_cap": 3_180_000_000_000,
    },
    "MSFT": {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "price": 415.80,
        "exchange": "NASDAQ",
        "annual_div_per_share": 3.32,
        "div_yield_pct": 0.80,
        "sector": "Technology",
        "market_cap": 3_090_000_000_000,
    },
}

# Volatility-informed put premium multipliers (IV approximation per ticker)
IV_APPROX = {
    "KO": 0.18, "JNJ": 0.20, "VZ": 0.22, "T": 0.25, "MO": 0.24,
    "XOM": 0.28, "PFE": 0.30, "AAPL": 0.32, "MSFT": 0.28,
}


def _bs_put_approx(S: float, K: float, T: float, sigma: float, r: float = 0.05) -> float:
    """Simplified ATM put premium approximation using Black-Scholes."""
    import math
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    def N(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    put = K * math.exp(-r * T) * N(-d2) - S * N(-d1)
    return max(put, 0.01)


def get_demo_options(stock: dict, shares: int) -> list:
    """Generate realistic put options using BS approximation."""
    ticker = stock["ticker"]
    price = stock["price"]
    sigma = IV_APPROX.get(ticker, 0.25)
    contracts = max(1, shares // 100)

    today = datetime.today().date()
    results = []

    expirations_days = [30, 60, 90, 120, 180, 270, 365]
    strike_configs = [
        ("ATM (100%)", 1.00),
        ("OTM 5% (95%)", 0.95),
        ("OTM 10% (90%)", 0.90),
    ]

    for days in expirations_days:
        exp_date = today + timedelta(days=days)
        # Round to nearest Friday
        days_to_friday = (4 - exp_date.weekday()) % 7
        exp_date = exp_date + timedelta(days=days_to_friday)
        exp_str = exp_date.strftime("%Y-%m-%d")
        T = days / 365.0

        for label, pct in strike_configs:
            strike = round(price * pct, 0)
            premium = _bs_put_approx(price, strike, T, sigma)
            # Add bid-ask spread
            bid = round(premium * 0.92, 4)
            ask = round(premium * 1.08, 4)
            mid = round((bid + ask) / 2, 4)

            ann_premium = round(premium * (365 / days), 4)
            total_cost = round(mid * contracts * 100, 2)

            # Fake but realistic volume
            import random
            random.seed(hash(f"{ticker}{days}{label}"))
            volume = random.randint(50, 5000) if days < 180 else random.randint(10, 800)

            results.append({
                "expiration": exp_str,
                "days_to_exp": days,
                "strike_label": label,
                "strike": float(strike),
                "strike_pct": round(pct * 100, 1),
                "premium_per_share": mid,
                "annualized_premium_per_share": ann_premium,
                "total_put_cost": total_cost,
                "contracts_needed": contracts,
                "volume": volume,
                "open_interest": volume * 3,
                "bid": bid,
                "ask": ask,
            })

    return results
