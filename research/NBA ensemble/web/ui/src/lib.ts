import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
export const pct = (x: number | null | undefined, digits = 0) => (x === null || x === undefined || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`);
export const num = (x: number | null | undefined, digits = 1) => (x === null || x === undefined || Number.isNaN(x) ? "—" : x.toFixed(digits));
export const etTime = (iso: string) => new Date(iso).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
export const etStamp = (iso: string) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }) + " ET";
export const dayLabel = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });

// Team colors arrive as plain hex. Two rival colors can be near twins (maroon vs red) and a near-black team vanishes on the dark page,
// so the pair is nudged apart for display only; the stored colors are never changed.
const toRgb = (hex: string): [number, number, number] => {
  const h = hex.replace("#", "");
  const f = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.padEnd(6, "0");
  return [parseInt(f.slice(0, 2), 16), parseInt(f.slice(2, 4), 16), parseInt(f.slice(4, 6), 16)];
};
const toHex = (c: number[]) => "#" + c.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
const mix = (hex: string, target: string, t: number) => {
  const a = toRgb(hex), b = toRgb(target);
  return toHex(a.map((v, i) => v + (b[i] - v) * t));
};
const lum = (hex: string) => {
  const [r, g, b] = toRgb(hex).map((v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a: string, b: string) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
const distance = (a: string, b: string) => { const [p, q] = [toRgb(a), toRgb(b)]; return Math.hypot((p[0] - q[0]) * 0.9, (p[1] - q[1]) * 1.2, (p[2] - q[2]) * 0.8); };

/** Readable text color (white or near-black) for a team-colored block. */
export const inkOn = (bg: string) => (ratio(bg, "#ffffff") >= ratio(bg, "#0b0c0e") ? "#ffffff" : "#0b0c0e");

export function pairColors(away: string, home: string) {
  const lift = (c: string) => (lum(c) < 0.02 ? mix(c, "#ffffff", 0.24) : c);
  const a = lift(away);
  const base = lift(home);
  let h = base;
  // Move the home color away from the away color in lightness, only as far as needed.
  const target = lum(base) >= lum(a) ? "#ffffff" : "#000000";
  for (let t = 0.1; t <= 0.7 && distance(a, h) < 120; t += 0.1) h = mix(base, target, t);
  return { away: a, home: h, awayInk: inkOn(a), homeInk: inkOn(h) };
}
