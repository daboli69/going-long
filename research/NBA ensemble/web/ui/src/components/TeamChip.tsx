import { cn, inkOn } from "../lib";

export function TeamChip({ abbr, color, size = "md" }: { abbr: string; color: string; size?: "sm" | "md" }) {
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center rounded font-display font-extrabold", size === "md" ? "h-12 w-14 text-base" : "h-9 w-11 text-sm")}
      style={{ background: color, color: inkOn(color) }}
      aria-label={abbr}
    >
      {abbr}
    </span>
  );
}
