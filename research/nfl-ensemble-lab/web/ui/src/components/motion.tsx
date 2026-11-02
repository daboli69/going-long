import { useEffect, useState } from "react";
import { animate, m, useMotionValue, useReducedMotion } from "motion/react";

// A number that counts to its new value (400 ms, ease-out) instead of jumping; shows the final value at once when reduced motion is on.
export function Num({ value, dec = 0, pct = false }: { value: number; dec?: number; pct?: boolean }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value);
  const fmt = (v: number) => (pct ? `${Math.round(v * 100)}%` : v.toFixed(dec));
  const [text, setText] = useState(fmt(value));
  useEffect(() => {
    if (reduce) { setText(fmt(value)); return; }
    const stop = animate(mv, value, { duration: 0.4, ease: "easeOut" });
    const off = mv.on("change", (v) => setText(fmt(v)));
    return () => { stop.stop(); off(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduce, dec, pct]);
  return <span>{text}</span>;
}

// Panel content that rises 6px and fades in when it mounts (a tab opening).
export const Rise = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <m.div className={className} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18, ease: "easeOut" }}>{children}</m.div>
);
