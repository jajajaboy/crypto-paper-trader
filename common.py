"""Shared helpers: config, public price data (Coinbase Exchange, no auth), SMA strategy, fills."""
import json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
CB_URL = "https://api.exchange.coinbase.com/products/{p}/candles?granularity={g}&start={s}&end={e}"
KRAKEN_PAIRS = {"BTC-USD": "XBTUSD", "ETH-USD": "ETHUSD", "DOGE-USD": "XDGUSD", "XRP-USD": "XRPUSD",
                "ADA-USD": "ADAUSD", "XLM-USD": "XLMUSD", "HBAR-USD": "HBARUSD"}


def load_config():
    return json.loads((HERE / "config.json").read_text())


def local(ts, cfg):
    return datetime.fromtimestamp(ts, ZoneInfo(cfg["timezone"])).strftime("%Y-%m-%d %H:%M %Z")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "crypto-paper-bot/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1 + attempt)
                continue
            raise
        except urllib.error.URLError:
            time.sleep(1 + attempt)
    raise RuntimeError(f"failed to fetch {url}")


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_candles_coinbase(product, start_ts, end_ts, gran):
    """Returns sorted list of (time, open, high, low, close, volume). Paginates 300 candles/request."""
    out = {}
    chunk = 300 * gran
    s = start_ts
    while s < end_ts:
        e = min(s + chunk, end_ts)
        rows = _get(CB_URL.format(p=product, g=gran, s=_iso(s), e=_iso(e)))
        for t, lo, hi, op, cl, vol in rows:  # Coinbase order: time, low, high, open, close, volume
            out[int(t)] = (int(t), float(op), float(hi), float(lo), float(cl), float(vol))
        s = e
        time.sleep(0.35)  # stay well under public rate limits
    return [out[k] for k in sorted(out)]


def fetch_candles_kraken(product, start_ts, gran):
    """Fallback. Kraken only returns the most recent 720 candles."""
    url = f"https://api.kraken.com/0/public/OHLC?pair={KRAKEN_PAIRS[product]}&interval={gran // 60}&since={start_ts}"
    data = _get(url)
    if data.get("error"):
        raise RuntimeError(data["error"])
    rows = next(v for k, v in data["result"].items() if k != "last")
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])) for r in rows]


def fetch_candles(product, start_ts, end_ts, gran):
    try:
        return fetch_candles_coinbase(product, start_ts, end_ts, gran), "Coinbase Exchange public API"
    except Exception as ex:
        print(f"[warn] Coinbase failed for {product} ({ex}); falling back to Kraken")
        return fetch_candles_kraken(product, start_ts, gran), "Kraken public API (fallback)"


def closed_only(candles, gran, now=None):
    """Drop the still-forming current candle."""
    now = now or time.time()
    return [c for c in candles if c[0] + gran <= now]


def sma(values, n):
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def target_long(fast, slow):
    """Long-only regime: hold the coin while fast SMA > slow SMA, otherwise hold cash.
    This is equivalent to 'buy on bullish cross, sell on bearish cross', but robust to a missed tick."""
    if fast is None or slow is None:
        return None
    return fast > slow


def buy_fill(cash, price, cfg):
    """Spend all cash. Returns (qty, fill_price, fee_usd)."""
    fill = price * (1 + cfg["slippage_rate"])
    fee = cash * cfg["fee_rate"]
    qty = (cash - fee) / fill
    return qty, fill, fee


def sell_fill(qty, price, cfg):
    """Sell all qty. Returns (cash_received, fill_price, fee_usd)."""
    fill = price * (1 - cfg["slippage_rate"])
    gross = qty * fill
    fee = gross * cfg["fee_rate"]
    return gross - fee, fill, fee


def fmt_px(x):
    """Price formatting that works for both $80,000 and $0.08 coins."""
    return f"${x:,.2f}" if x >= 100 else f"${x:,.5f}"


def coin_name(product):
    return product.split("-")[0]


def reason_text(product, action, fast, slow, cfg, had_position):
    """Plain-English explanation of a decision."""
    c, nf, ns = coin_name(product), cfg["fast_sma"], cfg["slow_sma"]
    if fast is None or slow is None:
        return f"Held {c}: not enough price history yet to compute the {nf}- and {ns}-hour averages."
    fa, sa = f"{nf}-hour average ({fmt_px(fast)})", f"{ns}-hour average ({fmt_px(slow)})"
    if action == "BUY":
        return f"Bought {c}: the {fa} is above the {sa}, signaling an uptrend, so the bot moved this coin's cash into {c}."
    if action == "SELL":
        return f"Sold {c}: the {fa} dropped below the {sa}, signaling a downtrend, so the bot moved back to cash."
    if fast > slow:
        return f"Held {c}: the {fa} is still above the {sa}; uptrend continues, so the bot keeps holding {c}." if had_position \
            else f"Held {c}: uptrend signal but no cash left for this coin."
    return f"Stayed in cash for {c}: the {fa} is below the {sa}, so there is no uptrend to buy into." if not had_position \
        else f"Held {c}: downtrend signal but nothing to sell."
