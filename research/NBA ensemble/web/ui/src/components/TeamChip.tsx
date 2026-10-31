import { cn } from "../lib";

export function TeamChip({ abbr, color, size = "md" }: { abbr: string; color: string; size?: "sm" | "md" }) {
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full font-extrabold text-white", size === "md" ? "h-12 w-12 text-sm" : "h-7 w-7 text-[10px]")}
      style={{ background: color }}
      aria-label={abbr}
    >
      {abbr}
    </span>
  );
}
