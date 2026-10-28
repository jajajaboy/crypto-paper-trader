const $ = s => document.querySelector(s);
const usd = x => x == null ? "-" : (Math.abs(x) >= 100 ? "$" + x.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})
  : Math.abs(x) >= 1 ? "$" + x.toFixed(4) : "$" + x.toFixed(5));
const money = x => "$" + x.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const pct = x => (x >= 0 ? "+" : "") + (x * 100).toFixed(2) + "%";
const cls = x => x >= 0 ? "pos" : "neg";
const coin = p => p.split("-")[0];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const tag = a => `<span class="tag ${a}">${a}</span>`;
const fill = (sel, rows) => { $(sel + " tbody").innerHTML = rows.join("") || `<tr><td colspan="9" class="muted">Nothing yet.</td></tr>`; };
const tradeRow = t => `<tr><td class="num">${esc(t.time)}</td><td>${coin(t.asset)}</td><td>${tag(t.side)}</td><td class="num">${usd(t.price)}</td>
  <td class="num">${t.qty.toLocaleString(undefined,{maximumFractionDigits:4})} ${coin(t.asset)}<br><span class="muted">${money(t.usd)}</span></td>
  <td class="num">${money(t.fee_usd)}</td><td class="reason">${esc(t.reason)}</td></tr>`;
const get = u => fetch(u + "?t=" + Date.now()).then(r => r.json());

get("data/portfolio.json").then(p => {
  $("#summary").innerHTML = [
    ["Total value", money(p.total_value)], ["P/L vs " + money(p.starting_cash_usd), `<span class="${cls(p.pnl)}">${(p.pnl>=0?"+":"-")+money(Math.abs(p.pnl))} (${pct(p.pnl_pct)})</span>`],
    ["Cash", money(p.cash)], ["Fees paid", money(p.fees_paid)], ["Trades", p.trades.length]
  ].map(([k, v]) => `<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
  fill("#holdings", p.holdings.map(h => `<tr><td>${coin(h.asset)}</td><td class="num">${h.qty.toLocaleString(undefined,{maximumFractionDigits:4})}</td>
    <td class="num">${usd(h.price)}</td><td class="num">${money(h.cash)}</td><td class="num">${money(h.value)}</td></tr>`));
  $("#updated").textContent = `Last updated ${p.last_updated} · started ${p.created} · ${p.ticks} hourly checks · data: ${p.data_source}`;
  fill("#tradetable", p.trades.map(tradeRow));
  fill("#dectable", p.decisions.map(d => `<tr><td class="num">${esc(d.time)}</td><td>${coin(d.asset)}</td><td>${tag(d.action)}</td>
    <td class="num">${usd(d.market_price)}</td><td class="num">${usd(d.sma_fast)}</td><td class="num">${usd(d.sma_slow)}</td><td class="reason">${esc(d.reason)}</td></tr>`));
  const q = p.params; $("#hf").textContent = q.fast_sma; $("#hs").textContent = q.slow_sma;
  $("#hfee").textContent = (q.fee_rate*100).toFixed(2)+"%"; $("#hslip").textContent = (q.slippage_rate*100).toFixed(2)+"%";
}).catch(e => { $("#summary").textContent = "Could not load portfolio data: " + e; });

get("data/backtest.json").then(b => {
  $("#btmeta").textContent = `${b.window_start} → ${b.window_end} · SMA ${b.params.fast_sma}/${b.params.slow_sma} on hourly candles · fee ${(b.params.fee_rate*100).toFixed(2)}% + slippage ${(b.params.slippage_rate*100).toFixed(2)}% per trade · start ${money(b.params.starting_cash_usd)} split evenly`;
  const row = (name, r, start) => `<tr><td><b>${name}</b></td><td class="num">${money(r.final)}</td><td class="num ${cls(r.ret)}">${pct(r.ret)}</td><td>${r.trades}</td>
    <td class="num">${r.wins}/${r.rts} (${r.rts ? Math.round(r.wins/r.rts*100) : 0}%)</td><td class="num">${money(r.fees)}</td><td class="num">${(r.mdd*100).toFixed(1)}%</td>
    <td class="num">${money(r.hold_final)}</td><td class="num ${cls(r.hold_ret)}">${pct(r.hold_ret)}</td><td class="num">${(r.hold_mdd*100).toFixed(1)}%</td></tr>`;
  fill("#bttable", b.assets.map(a => row(coin(a.product), a)).concat([row("Combined", b.combined)]));
  const c = b.combined;
  $("#btnote").innerHTML = `Fees ate <b>${money(c.fees)}</b>, ${(c.fees / c.start * 100).toFixed(1)}% of the ${money(c.start)} starting balance. The strategy ended at ${money(c.final)} (${pct(c.ret)}) vs ${money(c.hold_final)} (${pct(c.hold_ret)}) for buy-and-hold.`;
  $("#btcount").textContent = b.trades.length + " trades";
  fill("#bttrades", b.trades.map(tradeRow));
});
