"""Build the coverage matchup page: reports/covcard/covcard.html (self-contained, no network).

    .venv\\Scripts\\python.exe scripts\\covcard_render.py

Reads data/cache/covcard.json (written by `python -m lab.covcard`). Descriptive only; nothing is promoted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import covcard as cc  # noqa: E402
from lab.config import RAW_DIR  # noqa: E402

OUT = ROOT / "reports" / "covcard" / "covcard.html"
OVERRIDE = {"MIN": "00-0032950"}  # Murray is Out for MNF; Wentz is the reported starter
OVERRIDE_NOTE = {"MIN": "Wentz starts for Murray (Out, hamstring)"}

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coverage matchup</title>
<style>
:root{--bg:#fbfaf8;--panel:#ffffff;--ink:#1b1b1a;--ink2:#52514e;--ink3:#6b6a66;--line:#dedcd5;--grid:#ecebe5;--wr:#1c5fb0;--te:#b8470f;--rb:#107a55;--mark:#1b1b1a;--warn:#7a4a00;--warnbg:#fbf1dc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--panel:#1d1d1c;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#a09f98;--line:#383835;--grid:#2c2c2a;--mark:#f0efec;--warn:#f1d49b;--warnbg:#3a2f18}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:22px;font-weight:600;margin:0 0 4px}
h2{font-size:16px;font-weight:600;margin:28px 0 4px}
p{margin:0 0 8px}
.sub{color:var(--ink2);max-width:70ch}
.controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0 4px}
label{display:block;font-size:13px;color:var(--ink2);margin-bottom:4px}
select{width:100%;min-height:40px;padding:6px 8px;font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:6px;cursor:pointer}
select:focus-visible{outline:2px solid var(--wr);outline-offset:1px}
.note{font-size:13px;color:var(--warn);background:var(--warnbg);border-radius:6px;padding:8px 10px;margin:10px 0}
.hint{font-size:13px;color:var(--ink3)}
.row{display:grid;grid-template-columns:150px minmax(0,1fr) 150px;gap:12px;align-items:center;padding:6px 0;border-top:1px solid var(--grid)}
.row.head{border-top:0;font-size:12px;color:var(--ink3)}
.row .lbl{font-size:14px}
.row .lbl small{display:block;color:var(--ink3);font-size:12px}
.row .val{font-size:13px;color:var(--ink2);font-variant-numeric:tabular-nums}
.bar{display:flex;height:24px;border-radius:4px;overflow:hidden;background:var(--grid);gap:2px}
.bar i{display:flex;align-items:center;justify-content:center;color:#fff;font:600 12px/1 system-ui,sans-serif;font-style:normal;min-width:0;overflow:hidden}
.bar i.wr{background:var(--wr)}.bar i.te{background:var(--te)}.bar i.rb{background:var(--rb)}
.track{position:relative;height:18px;background:var(--grid);border-radius:4px}
.track b{position:absolute;left:0;top:0;bottom:0;background:var(--wr);border-radius:4px}
.track u{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--mark);text-decoration:none}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--ink2);margin:6px 0}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend s{display:inline-block;width:10px;height:10px;border-radius:2px;text-decoration:none}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 8px 7px 0;border-top:1px solid var(--grid);vertical-align:top}
th{font-size:12px;font-weight:500;color:var(--ink3);border-top:0}
td.read{color:var(--ink2);min-width:200px}
.pos{font-weight:600}
.up{color:var(--ink)}
ul.read{margin:8px 0 0;padding-left:20px}ul.read li{margin:3px 0}
.foot{margin-top:28px;font-size:13px;color:var(--ink3);max-width:80ch}
.foot p{margin:0 0 6px}
@media (max-width:640px){.row{grid-template-columns:1fr;gap:4px}.row.head{display:none}.row .val{margin-top:-2px}td.read{min-width:0}table,thead,tbody,tr,th,td{font-size:13px}}
</style>
</head>
<body>
<main>
<h1>Coverage matchup</h1>
<p class="sub">How a quarterback has fared against each coverage, and what the defense he faces runs and gives up by receiver position. Descriptive history, not a forecast or a pick.</p>

<div class="controls">
<div><label for="game">Game</label><select id="game"></select></div>
<div><label for="qb">Quarterback</label><select id="qb"></select></div>
<div><label for="def">Defense</label><select id="def"></select></div>
</div>
<div id="notes"></div>
<div id="out"></div>

<div class="foot">
<p><b>How it's computed.</b> Pass attempts only (sacks and scrambles excluded). Receiver position comes from the nflverse player table (RB includes FB); throws with no target or an unknown position are left out of the position shares. Explosive means a completion of 20 or more yards.</p>
<p><b>Coverage tags</b> come from nflverse participation data for 2022 to 2025. There is no 2026 file, so a defense's coverage mix is its 2025 mix and a quarterback's 2026 passes are not split by coverage. Defense position profiles use 2025 and 2026 to date.</p>
<p><b>Small samples are pulled toward the league.</b> A quarterback's share in a coverage is blended with the league share using <span id="k1"></span> targets of weight; his EPA uses <span id="k2"></span> attempts. A defense's coverage mix uses <span id="k3"></span> attempts of weight and its position rates use <span id="k4"></span> targets. These constants were fixed before looking at results.</p>
<p><b>The expected mix</b> multiplies the defense's coverage rates by the quarterback's position shares in each coverage. It assumes the defense plays its usual mix in this game and the quarterback keeps his habits. It does not know the game plan, injuries or who the receivers are.</p>
</div>
</main>
<script>
const D = __DATA__;
const SLATE = __SLATE__;
const COVS = ["COVER_1","COVER_2","COVER_3","COVER_4","OTHER"];
const CLAB = {COVER_1:"Cover 1",COVER_2:"Cover 2",COVER_3:"Cover 3",COVER_4:"Cover 4",OTHER:"Other (0, 6, 2-man, combo)"};
const POS = ["WR","TE","RB"];
const P = D.params;
document.getElementById("k1").textContent = P.K_QB_SHARE;
document.getElementById("k2").textContent = P.K_QB_EPA;
document.getElementById("k3").textContent = P.K_DEF_COV;
document.getElementById("k4").textContent = P.K_DEF_POS;

const sum = a => a.reduce((x,y)=>x+y,0);
const pct = (x,d=0) => (100*x).toFixed(d) + "%";
const sgn = (x,d=1) => (x>=0?"+":"−") + Math.abs(x).toFixed(d);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const LG = {};
COVS.forEach(c => {
  const g = D.league.cov[c], t = sum(POS.map(p=>g.tgt[p]));
  LG[c] = {share:Object.fromEntries(POS.map(p=>[p,g.tgt[p]/t])), epa:g.epa, att:g.att};
});

function qbShare(q, c){
  const g = q.cov[c], t = sum(POS.map(p=>g.tgt[p])), K = P.K_QB_SHARE;
  return Object.fromEntries(POS.map(p => [p, (g.tgt[p] + K*LG[c].share[p])/(t + K)]));
}
function qbEpa(q, c){
  const g = q.cov[c], K = P.K_QB_EPA;
  return ((g.att*(g.epa ?? 0)) + K*LG[c].epa)/(g.att + K);
}
function qbBase(q){
  const t = sum(POS.map(p=>sum(COVS.map(c=>q.cov[c].tgt[p]))));
  const out = {};
  POS.forEach(p => {
    const lg = sum(COVS.map(c=>D.league.cov[c].tgt[p]))/sum(POS.map(pp=>sum(COVS.map(c=>D.league.cov[c].tgt[pp]))));
    out[p] = (sum(COVS.map(c=>q.cov[c].tgt[p])) + P.K_QB_SHARE*lg)/(t + P.K_QB_SHARE);
  });
  return out;
}
function defCov(d, c){
  const K = P.K_DEF_COV, lg = D.def_league.cov[c] ?? 0;
  return (d.cov_n[c] + K*lg)/(d.tagged + K);
}
function defPos(d, p){
  const K = P.K_DEF_POS, L = D.def_league.pos[p], x = d.pos[p], T = d.tgt_known;
  return {n:x.tgt, share:(x.tgt + K*L.share)/(T + K),
          ypt:(x.yds + K*L.ypt)/(x.tgt + K), expl:(x.expl + K*L.expl)/(x.tgt + K),
          cmp:(x.cmp + K*L.cmp)/(x.tgt + K), epa:(x.epa + K*L.epa)/(x.tgt + K)};
}
function read(p, s, L, n){
  const dv = (s.share - L.share)*100, dy = s.ypt - L.ypt, de = (s.expl - L.expl)*100;
  const hv = dv >= 2, lv = dv <= -2, hy = dy >= 0.5 || de >= 1, ly = dy <= -0.5 && de <= 0.5, ex = de >= 1;
  let t = "Near league average on volume and yards.";
  if (hv && ly) t = "Lots of targets, few yards. Throws get caught short.";
  else if (hv && hy) t = "Targeted a lot and hurt on those throws.";
  else if (lv && ex) t = "Few targets, but chunk plays when they come.";
  else if (lv && ly) t = "Rarely targeted, and quiet when tested.";
  else if (lv) t = "Rarely targeted.";
  else if (hv) t = "Targeted more than usual, yards about average.";
  else if (ex) t = "Average volume, but gives up chunk plays.";
  else if (ly) t = "Average volume, holds yards down.";
  if (n < 100) t += " (Small sample.)";
  return t;
}

const state = {};
function fill(sel, items, val){
  sel.innerHTML = items.map(([v,t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join("");
  if (val !== undefined) sel.value = val;
}
const gameSel = document.getElementById("game"), qbSel = document.getElementById("qb"), defSel = document.getElementById("def");
fill(gameSel, [["custom","Custom (pick below)"]].concat(SLATE.map((g,i)=>[String(i), g.label])));
const qbList = Object.entries(D.qbs).filter(([id,q]) => q.att_tagged >= 20 || q.att_2026_untagged >= 20)
  .sort((a,b)=>b[1].att_tagged - a[1].att_tagged);
fill(qbSel, qbList.map(([id,q]) => [id, `${q.name} (${q.team}, ${q.att_tagged} tagged)`]));
fill(defSel, Object.keys(D.defs).sort().map(t => [t, t]));

function bar(shares, big){
  return `<div class="bar" role="img" aria-label="${POS.map(p=>p+" "+pct(shares[p])).join(", ")}">` +
    POS.map(p => `<i class="${p.toLowerCase()}" style="flex:${Math.max(shares[p],0.001)}">${shares[p] >= 0.1 ? pct(shares[p]) : ""}</i>`).join("") + `</div>`;
}

function render(){
  const q = D.qbs[qbSel.value], tm = defSel.value, d = D.defs[tm];
  const notes = [];
  if (state.note) notes.push(state.note);
  if (q.att_tagged < 100) notes.push(`${q.name} has only ${q.att_tagged} coverage-tagged attempts (2022 to 2025). His splits sit close to the league's by design.`);
  if (q.att_2026_untagged) notes.push(`${q.att_2026_untagged} of ${q.name}'s 2026 attempts have no coverage tag and are not in the splits.`);
  document.getElementById("notes").innerHTML = notes.map(n => `<div class="note">${esc(n)}</div>`).join("");

  const mix = Object.fromEntries(COVS.map(c => [c, defCov(d, c)]));
  const lgm = D.def_league.cov;
  const manRate = (d.man_n + P.K_DEF_COV*D.def_league.man)/(d.mz_n + P.K_DEF_COV);
  let html = `<h2>What ${esc(tm)} runs</h2><p class="hint">Share of pass plays by coverage, ${esc(tm)} 2025 (${d.tagged} tagged plays). The black tick is the league rate.</p>`;
  html += COVS.map(c => `<div class="row"><div class="lbl">${esc(CLAB[c])}</div>
    <div class="track" role="img" aria-label="${esc(CLAB[c])} ${pct(mix[c])}, league ${pct(lgm[c]||0)}"><b style="width:${(mix[c]*100/0.5*100/100).toFixed(1)}%"></b><u style="left:${((lgm[c]||0)*100/0.5).toFixed(1)}%"></u></div>
    <div class="val">${pct(mix[c])} <span>(league ${pct(lgm[c]||0)}, ${sgn((mix[c]-(lgm[c]||0))*100,0)} pts)</span></div></div>`).join("");
  html += `<p class="hint" style="margin-top:6px">Man coverage on ${pct(manRate)} of plays (league ${pct(D.def_league.man)}). Scale: 0 to 50%.</p>`;

  html += `<h2>${esc(q.name)} by coverage</h2><p class="hint">Where his targets go (WR, TE, RB) and his EPA per attempt. Small buckets are pulled toward the league. Seasons: ${Object.entries(q.by_season).map(([s,n])=>s+" ("+n+")").join(", ")}.</p>
    <div class="legend"><span><s style="background:var(--wr)"></s>WR</span><span><s style="background:var(--te)"></s>TE</span><span><s style="background:var(--rb)"></s>RB</span></div>
    <div class="row head"><div>Coverage (attempts)</div><div>Share of targets</div><div>EPA per attempt</div></div>`;
  html += COVS.map(c => {
    const g = q.cov[c], e = qbEpa(q, c);
    return `<div class="row"><div class="lbl">${esc(CLAB[c].split(" (")[0])}<small>${g.att} attempts</small></div><div>${bar(qbShare(q,c))}</div>
      <div class="val">${sgn(e,2)} <span>(raw ${g.att?sgn(g.epa,2):"n/a"})</span></div></div>`;
  }).join("");

  const base = qbBase(q);
  const exp = Object.fromEntries(POS.map(p => [p, sum(COVS.map(c => mix[c]*qbShare(q,c)[p]))]));
  const expEpa = sum(COVS.map(c => mix[c]*qbEpa(q,c)));
  const lgEpaMix = sum(COVS.map(c => (lgm[c]||0)*qbEpa(q,c)));
  const allow = Object.fromEntries(POS.map(p => [p, defPos(d,p).share]));
  html += `<h2>${esc(q.name)} against ${esc(tm)}</h2><p class="hint">Three views of the same question: where do the targets go?</p>
    <div class="row head"><div>View</div><div>Share of targets</div><div>EPA per attempt</div></div>
    <div class="row"><div class="lbl">His usual mix<small>all coverages</small></div><div>${bar(base)}</div><div class="val">${sgn(qbEpa2(q),2)}</div></div>
    <div class="row"><div class="lbl">Expected vs ${esc(tm)}<small>their coverage mix applied</small></div><div>${bar(exp)}</div><div class="val">${sgn(expEpa,2)} <span>(league-mix ${sgn(lgEpaMix,2)})</span></div></div>
    <div class="row"><div class="lbl">${esc(tm)} allows<small>to all QBs</small></div><div>${bar(allow)}</div><div class="val"></div></div>`;

  html += `<h2>${esc(tm)} by receiver position</h2><p class="hint">What they allow, 2025 and 2026 to date (${d.tgt_known} targets). Differences are against the league.</p>
    <table><thead><tr><th>Position</th><th>Share of targets</th><th>Yards per target</th><th>Explosive (20+)</th><th>EPA per target</th><th>Read</th></tr></thead><tbody>` +
    POS.map(p => {
      const s = defPos(d,p), L = D.def_league.pos[p];
      return `<tr><td class="pos">${p}<br><span class="hint">${s.n} targets</span></td>
        <td>${pct(s.share,1)}<br><span class="hint">${sgn((s.share-L.share)*100)} pts vs league</span></td>
        <td>${s.ypt.toFixed(1)}<br><span class="hint">${sgn(s.ypt-L.ypt)} vs league</span></td>
        <td>${pct(s.expl,1)}<br><span class="hint">${sgn((s.expl-L.expl)*100)} pts</span></td>
        <td>${sgn(s.epa,2)}<br><span class="hint">${sgn(s.epa-L.epa,2)}</span></td>
        <td class="read">${esc(read(p,s,L,s.n))}</td></tr>`;
    }).join("") + `</tbody></table>`;

  const bits = [];
  const cmax = COVS.slice().sort((a,b)=>(mix[b]-(lgm[b]||0))-(mix[a]-(lgm[a]||0)))[0];
  bits.push(`${tm} leans on ${CLAB[cmax].split(" (")[0]} (${pct(mix[cmax])}, ${sgn((mix[cmax]-(lgm[cmax]||0))*100,0)} pts vs league).`);
  const worst = COVS.slice().sort((a,b)=>qbEpa(q,a)-qbEpa(q,b));
  bits.push(`${q.name}'s weakest coverage by EPA is ${CLAB[worst[0]].split(" (")[0]} (${sgn(qbEpa(q,worst[0]),2)}), strongest is ${CLAB[worst[worst.length-1]].split(" (")[0]} (${sgn(qbEpa(q,worst[worst.length-1]),2)}), after pulling toward the league.`);
  const dTop = POS.slice().sort((a,b)=>(exp[b]-base[b])-(exp[a]-base[a]))[0];
  bits.push(`Against ${tm}'s mix, his ${dTop} share moves ${sgn((exp[dTop]-base[dTop])*100)} pts from his usual (${pct(base[dTop])} to ${pct(exp[dTop])}).`);
  html += `<h2>Summary</h2><ul class="read">${bits.map(b=>`<li>${esc(b)}</li>`).join("")}</ul>`;
  document.getElementById("out").innerHTML = html;
}
function qbEpa2(q){
  const t = q.all, K = P.K_QB_EPA, lg = D.league.all.epa;
  return (t.att*(t.epa ?? 0) + K*lg)/(t.att + K);
}
function applyGame(){
  const v = gameSel.value;
  if (v === "custom"){ state.note = null; return; }
  const g = SLATE[+v];
  state.note = g.note || null;
  qbSel.value = g.qb; defSel.value = g.def;
}
gameSel.addEventListener("change", () => { applyGame(); render(); });
qbSel.addEventListener("change", () => { gameSel.value = "custom"; state.note = null; render(); });
defSel.addEventListener("change", () => { gameSel.value = "custom"; state.note = null; render(); });
gameSel.value = "0"; applyGame(); render();
</script>
</body>
</html>
"""


def slate() -> list[dict]:
    st = cc.starters()
    g = pd.read_csv(RAW_DIR / "games.csv")
    names = {}

    def qb_for(team: str) -> str:
        return OVERRIDE.get(team) or st[team][0]

    rows = [{"label": "Week 9 MNF: BUF at MIN (Wentz for MIN)", "away": "BUF", "home": "MIN"}]
    wk = g[(g["season"] == 2026) & (g["week"] == 10)]
    for r in wk.itertuples():
        rows.append({"label": f"Week 10: {r.away_team} at {r.home_team}", "away": r.away_team, "home": r.home_team})
    out = []
    for r in rows:
        a, h = r["away"], r["home"]
        note = "Quarterback is the one with the most dropbacks in his team's latest game, unless noted. Check the injury report."
        if "Week 9" in r["label"]:
            note = "; ".join(OVERRIDE_NOTE[t] for t in (a, h) if t in OVERRIDE_NOTE)
        game = r["label"].split(": ", 1)
        out.append({"label": f"{game[0]}: {a} QB vs {h} D", "qb": qb_for(a), "def": h, "note": note})
        out.append({"label": f"{game[0]}: {h} QB vs {a} D", "qb": qb_for(h), "def": a, "note": note})
    return out


def main():
    data = json.loads(cc.OUT_JSON.read_text(encoding="utf-8"))
    sl = slate()
    for s in sl:
        if s["qb"] not in data["qbs"]:
            print("warning: no QB entry for", s["qb"], s["label"])
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"))).replace("__SLATE__", json.dumps(sl))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print("wrote", OUT, f"{OUT.stat().st_size/1e3:.0f} kB")


if __name__ == "__main__":
    main()
