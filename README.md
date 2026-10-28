# Crypto paper-trading bot (fake money only)

No exchange account, no API keys, no real orders. Prices come from the free public
Coinbase Exchange candles API (falls back to Kraken public OHLC if Coinbase fails).

Requires Python 3 + matplotlib (`pip install matplotlib`) for the chart only.

## Files
- `config.json`: everything you'd want to change (coins, SMA lengths, fees, slippage, starting balance, backtest length).
- `common.py`: data fetching, SMA math, simulated fills with fee + slippage.
- `backtest.py`: historical test. `python3 backtest.py` prints per-coin and combined results vs buy-and-hold, saves `backtest.png`.
- `tick.py`: one live paper step. `python3 tick.py` fetches latest hourly candles, buys/sells/holds each coin, updates `state.json`, prints a summary.
- `state.json`: the paper portfolio (cash, holdings per coin, full trade log with Chicago times, prices, fees).

## Strategy
Long-only SMA crossover on 1-hour candles: hold the coin while the fast SMA (default 20) is above the
slow SMA (default 50), otherwise hold cash. Signals use closed candles only; fills use the latest price
with slippage (0.05%) against you and a 0.6% fee per trade. The balance is split evenly across coins.

## Running on a schedule
Hourly via cron, a couple of minutes after the hour:
    2 * * * * cd /workspace/crypto-paper && python3 tick.py >> tick.log 2>&1

## Changing settings
Edit `config.json`, e.g. `"fast_sma": 50, "slow_sma": 200` or `"assets": ["DOGE-USD","XLM-USD","HBAR-USD"]`.
Re-run `python3 backtest.py`. To restart the paper portfolio with new settings, delete `state.json` and run `tick.py`.
Avoid trying dozens of settings until one looks good on the backtest: that's curve-fitting and usually fails live.

## Honest caveats
- First backtest (90 days to 2026-10-28, $100): strategy about -26% vs buy-and-hold about +17%; fees ate about $35.
  With zero fees the same signals would have made about +9%, so trading costs did most of the damage.
- Real Coinbase retail fees for small accounts can be higher than 0.6% (the lowest Advanced Trade tier is ~1.2% taker).
- Past results don't predict future ones. 90 days is a short sample.

## Public website (GitHub Pages)
The site in `docs/` (plain HTML/CSS/JS) renders `docs/data/portfolio.json` and `docs/data/backtest.json`.
Every decision (buys, sells and holds) is logged in `state.json` with the price, both averages and a plain-English reason.
- Update site data only: `python3 export_site.py`
- Run a tick and publish: `python3 tick.py && ./publish.sh` (or `PUBLISH=1 python3 tick.py`)
- `publish.sh` regenerates data, commits only if something changed, and pushes to `main`.
