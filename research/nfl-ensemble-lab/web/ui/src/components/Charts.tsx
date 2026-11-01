import type { Detail } from "../types";
import { pct } from "../lib";

// Hand-built charts: every one has a printed scale, so a reader never has to guess what a bar height means.
export function Axis({ ticks, x }: { ticks: [number, string][]; x: (v: number) => number }) {
  return (
    <div className="relative h-[18px] text-[13px] text-muted" aria-hidden>
      {ticks.map(([v, l]) => <span key={v} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${x(v)}%` }}>{l}</span>)}
    </div>
  );
}

export function Hist({ bins, color, exp, ticks, label }: { bins: { x: number; p: number }[]; color: (x: number) => string; exp: number; ticks: [number, string][]; label: string }) {
  const mx = Math.max(...bins.map((b) => b.p)), step = mx > 0.03 ? 0.01 : 0.005, top = Math.ceil(mx / step) * step + 1e-9;
  const ys: number[] = [];
  for (let t = 0; t <= top; t += step) ys.push(t);
  const x0 = bins[0].x, x1 = bins[bins.length - 1].x, X = (v: number) => ((v - x0) / (x1 - x0)) * 100;
  return (
    <div className="grid grid-cols-[2.6em_1fr] gap-x-2">
      <div className="relative text-[13px] text-muted" aria-hidden>
        {ys.map((t) => <span key={t} className="absolute right-0 -translate-y-1/2" style={{ top: `${100 - (t / top) * 100}%` }}>{(t * 100).toFixed((t * 100) % 1 ? 1 : 0)}%</span>)}
      </div>
      <div className="relative flex h-[160px] items-end gap-px sm:h-[180px]" role="img" aria-label={label}>
        {ys.slice(1).map((t) => <span key={t} className="absolute inset-x-0 h-px bg-raised" style={{ bottom: `${(t / top) * 100}%` }} />)}
        {bins.map((b) => <i key={b.x} className="relative z-[1] block flex-1" style={{ height: `${(b.p / top) * 100}%`, background: color(b.x) }} />)}
        <span className="absolute inset-y-0 z-[2] w-0.5 bg-accent" style={{ left: `${X(exp)}%` }} />
      </div>
      <div />
      <div className="relative h-[18px] text-[13px] text-muted" aria-hidden>
        {ticks.map(([v, l]) => <span key={v} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${X(v)}%` }}>{l}</span>)}
      </div>
    </div>
  );
}

export const tickEvery = (bins: { x: number }[], step: number): [number, string][] => {
  const out: [number, string][] = [];
  for (let v = Math.ceil(bins[0].x / step) * step; v <= bins[bins.length - 1].x; v += step) out.push([v, String(Math.abs(v))]);
  return out;
};

// Each forecast source as a dot on a shared percent scale, so disagreement is a distance you can see.
export function ForecastDots({ d }: { d: Detail }) {
  const src = d.sources ?? [];
  if (!src.length) return null;
  const ps = src.map((s) => s.p_home * 100), lo = Math.floor((Math.min(...ps) - 2) / 5) * 5, hi = Math.ceil((Math.max(...ps) + 2) / 5) * 5, X = (v: number) => ((v - lo) / (hi - lo)) * 100;
  const ticks: [number, string][] = [];
  for (let t = lo; t <= hi; t += 5) ticks.push([t, `${t}%`]);
  const hasMarket = src.some((s) => s.name.startsWith("Betting market"));
  return (
    <>
      <h2 className="text-xl leading-tight text-white">Forecasts</h2>
      <p className="mb-4 mt-1 text-[15px] text-muted">{d.home} win chance from each source{hasMarket ? ". Yellow dot: betting market." : "."}</p>
      <div className="grid grid-cols-[minmax(0,7em)_1fr_3em] items-center gap-x-4 gap-y-2 sm:grid-cols-[minmax(0,9.5em)_1fr_3em]">
        {src.map((s) => (
          <div key={s.name} className="contents">
            <div>{s.name}</div>
            <div className="relative h-6" aria-hidden>
              <span className="absolute inset-x-0 top-[11px] h-0.5 bg-raised" />
              <span className={`absolute top-[5px] -ml-[7px] h-3.5 w-3.5 rounded-full ${s.name.startsWith("Betting market") ? "bg-accent" : "bg-white"}`} style={{ left: `${X(s.p_home * 100)}%` }} />
            </div>
            <div className="text-right font-semibold">{pct(s.p_home)}</div>
          </div>
        ))}
        <div /><Axis ticks={ticks} x={X} /><div />
      </div>
      {d.agreement && <p className="mt-4 text-[15px] text-muted">The {src.length} sources sit {Math.round(d.agreement.gap_points)} points apart.</p>}
    </>
  );
}
