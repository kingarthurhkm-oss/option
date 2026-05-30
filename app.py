import os
from datetime import datetime

import yfinance as yf
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from demo_data import DEMO_STOCKS, get_demo_options

app = Flask(__name__)
CORS(app)

LIVE_DATA_AVAILABLE = None  # will be detected on first request


def _check_live_available() -> bool:
    global LIVE_DATA_AVAILABLE
    if LIVE_DATA_AVAILABLE is not None:
        return LIVE_DATA_AVAILABLE
    try:
        t = yf.Ticker("KO")
        hist = t.history(period="1d")
        LIVE_DATA_AVAILABLE = not hist.empty
    except Exception:
        LIVE_DATA_AVAILABLE = False
    return LIVE_DATA_AVAILABLE


def get_stock_info_live(ticker: str) -> dict | None:
    t = yf.Ticker(ticker)
    info = t.info
    hist = t.history(period="5d")

    price = None
    if not hist.empty:
        price = float(hist["Close"].iloc[-1])
    elif info.get("currentPrice"):
        price = float(info["currentPrice"])
    elif info.get("regularMarketPrice"):
        price = float(info["regularMarketPrice"])

    if price is None:
        return None

    div_per_share = float(info.get("dividendRate") or 0)
    div_yield = float(info.get("dividendYield") or 0)
    if div_per_share == 0 and div_yield > 0:
        div_per_share = price * div_yield

    exchange = info.get("exchange", "")
    exchange_map = {
        "NMS": "NASDAQ", "NYQ": "NYSE", "NGM": "NASDAQ",
        "NCM": "NASDAQ", "NasdaqGS": "NASDAQ", "NasdaqGM": "NASDAQ",
        "NasdaqCM": "NASDAQ", "NYSE": "NYSE",
    }

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName", ticker.upper()),
        "price": round(price, 2),
        "exchange": exchange_map.get(exchange, exchange),
        "annual_div_per_share": round(div_per_share, 4),
        "div_yield_pct": round(div_yield * 100, 4),
        "sector": info.get("sector", "N/A"),
        "market_cap": info.get("marketCap"),
    }


def get_put_options_live(ticker: str, stock_price: float, shares: int) -> list:
    t = yf.Ticker(ticker)
    expirations = t.options
    if not expirations:
        return []

    today = datetime.today().date()
    results = []
    contracts_needed = max(1, shares // 100)

    valid_exps = []
    for exp in expirations:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
        days = (exp_date - today).days
        if 20 <= days <= 400:
            valid_exps.append((exp, days))

    step = max(1, len(valid_exps) // 6)
    selected = valid_exps[::step][:8]

    for exp, days in selected:
        try:
            chain = t.option_chain(exp)
            puts = chain.puts
            if puts.empty:
                continue

            target_strikes = {
                "ATM (100%)": stock_price,
                "OTM 5% (95%)": stock_price * 0.95,
                "OTM 10% (90%)": stock_price * 0.90,
            }

            puts = puts[puts["ask"] > 0].copy()
            if puts.empty:
                continue

            for label, target_strike in target_strikes.items():
                idx = (puts["strike"] - target_strike).abs().idxmin()
                row = puts.loc[idx]

                strike = float(row["strike"])
                ask = float(row["ask"])
                bid = float(row.get("bid", ask))
                mid = (ask + bid) / 2
                premium_per_share = mid if ask > 0 and (ask - bid) / ask < 0.3 else ask

                results.append({
                    "expiration": exp,
                    "days_to_exp": days,
                    "strike_label": label,
                    "strike": round(strike, 2),
                    "strike_pct": round(strike / stock_price * 100, 1),
                    "premium_per_share": round(premium_per_share, 4),
                    "annualized_premium_per_share": round(premium_per_share * (365 / days), 4),
                    "total_put_cost": round(premium_per_share * contracts_needed * 100, 2),
                    "contracts_needed": contracts_needed,
                    "volume": int(row.get("volume") or 0),
                    "open_interest": int(row.get("openInterest") or 0),
                    "bid": round(bid, 4),
                    "ask": round(ask, 4),
                })
        except Exception:
            continue

    return results


def compute_spread_ratios(stock: dict, put_options: list, shares: int) -> list:
    annual_div = stock["annual_div_per_share"]
    price = stock["price"]
    enriched = []

    for opt in put_options:
        days = opt["days_to_exp"]
        period_div_per_share = annual_div * (days / 365)
        period_div_total = period_div_per_share * shares
        put_cost_per_share = opt["premium_per_share"]
        put_cost_total = opt["total_put_cost"]

        if put_cost_per_share > 0:
            spread_ratio = period_div_per_share / put_cost_per_share
            ann_spread_ratio = annual_div / opt["annualized_premium_per_share"]
        else:
            spread_ratio = None
            ann_spread_ratio = None

        net_cost = max(0, put_cost_per_share - period_div_per_share)
        net_cost_pct = (net_cost / price * 100) if price > 0 else 0

        enriched.append({
            **opt,
            "period_div_per_share": round(period_div_per_share, 4),
            "period_div_total": round(period_div_total, 2),
            "put_cost_total": round(put_cost_total, 2),
            "spread_ratio": round(spread_ratio, 4) if spread_ratio is not None else None,
            "annualized_spread_ratio": round(ann_spread_ratio, 4) if ann_spread_ratio is not None else None,
            "net_put_cost_per_share": round(net_cost, 4),
            "net_put_cost_pct": round(net_cost_pct, 4),
            "dividend_covers_pct": round(spread_ratio * 100, 1) if spread_ratio is not None else None,
        })

    return enriched


@app.route("/api/analyze", methods=["GET"])
def analyze():
    ticker = request.args.get("ticker", "").strip().upper()
    shares = request.args.get("shares", "100")
    try:
        shares = int(shares)
    except ValueError:
        return jsonify({"error": "shares must be an integer"}), 400

    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    if shares <= 0 or shares > 100000:
        return jsonify({"error": "shares must be between 1 and 100000"}), 400

    use_demo = not _check_live_available()
    is_demo_ticker = ticker in DEMO_STOCKS

    if use_demo:
        if not is_demo_ticker:
            return jsonify({
                "error": (
                    f"데모 모드: '{ticker}'는 지원되지 않습니다. "
                    f"사용 가능한 데모 티커: {', '.join(sorted(DEMO_STOCKS.keys()))}"
                ),
                "demo_mode": True,
            }), 404

        stock = DEMO_STOCKS[ticker].copy()
        puts = get_demo_options(stock, shares)
    else:
        try:
            stock = get_stock_info_live(ticker)
        except Exception as e:
            # Fallback to demo if live fails for a known ticker
            if is_demo_ticker:
                stock = DEMO_STOCKS[ticker].copy()
                puts = get_demo_options(stock, shares)
                enriched = compute_spread_ratios(stock, puts, shares)
                enriched.sort(key=lambda x: x.get("annualized_spread_ratio") or 0, reverse=True)
                return _build_response(stock, shares, enriched, demo_mode=True)
            return jsonify({"error": f"데이터 조회 실패: {str(e)}"}), 500

        if stock is None:
            return jsonify({"error": f"티커 '{ticker}'를 찾을 수 없거나 가격 데이터가 없습니다."}), 404

        if stock["annual_div_per_share"] == 0:
            return jsonify({
                "error": f"{ticker}은(는) 배당금을 지급하지 않습니다. 이 전략은 배당주에 적용됩니다.",
                "stock": stock,
            }), 400

        try:
            puts = get_put_options_live(ticker, stock["price"], shares)
        except Exception as e:
            return jsonify({"error": f"옵션 데이터 조회 실패: {str(e)}"}), 500

        if not puts:
            return jsonify({
                "error": f"{ticker}의 풋옵션을 찾을 수 없습니다. 옵션이 상장되지 않은 종목일 수 있습니다.",
                "stock": stock,
            }), 404

    enriched = compute_spread_ratios(stock, puts, shares)
    enriched.sort(key=lambda x: x.get("annualized_spread_ratio") or 0, reverse=True)
    return _build_response(stock, shares, enriched, demo_mode=use_demo)


def _build_response(stock: dict, shares: int, options: list, demo_mode: bool = False):
    best = options[0] if options else None
    return jsonify({
        "stock": stock,
        "shares": shares,
        "position_value": round(stock["price"] * shares, 2),
        "annual_div_total": round(stock["annual_div_per_share"] * shares, 2),
        "options": options,
        "best_option": best,
        "demo_mode": demo_mode,
    })


@app.route("/api/health", methods=["GET"])
def health():
    live = _check_live_available()
    return jsonify({
        "status": "ok",
        "live_data": live,
        "mode": "live" if live else "demo",
        "demo_tickers": sorted(DEMO_STOCKS.keys()) if not live else [],
    })


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(os.path.dirname(__file__), "index.html")


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
