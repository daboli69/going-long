import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cva, type VariantProps } from "class-variance-authority";
import { CircleCheck, Info, TriangleAlert } from "lucide-react";
import * as React from "react";
import { cn } from "../../lib";

export const Card = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("rounded-md bg-surface p-4 sm:p-5", className)} {...props} />
);

export const PanelTitle = ({ children, hint }: { children: React.ReactNode; hint?: React.ReactNode }) => (
  <div className="mb-3">
    <h2 className="text-lg font-bold leading-tight">{children}</h2>
    {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
  </div>
);

const badge = cva("inline-flex min-h-6 items-center rounded px-2 text-sm font-semibold", {
  variants: { tone: { neutral: "bg-surface2 text-muted", red: "bg-bad-bg text-bad-fg", amber: "bg-warn-bg text-warn-fg", green: "bg-ok-bg text-ok-fg" } },
  defaultVariants: { tone: "neutral" },
});
export const Badge = ({ tone, className, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) => (
  <span className={cn(badge({ tone }), className)} {...props} />
);

export const Tabs = TabsPrimitive.Root;
// Bottom bar on a phone (thumb reach), plain text tabs on a wide screen.
export const TabsList = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) => (
  <TabsPrimitive.List
    className={cn("fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 bg-surface pb-[env(safe-area-inset-bottom)] md:static md:flex md:gap-1 md:bg-transparent md:pb-0 md:shadow-[inset_0_-1px_0_#2c333d]", className)}
    {...props}
  />
);
export const TabsTrigger = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) => (
  <TabsPrimitive.Trigger
    className={cn(
      "flex h-14 flex-col items-center justify-center gap-1 text-[0.8125rem] font-semibold text-muted transition-colors hover:text-ink",
      "data-[state=active]:text-ink data-[state=active]:shadow-[inset_0_3px_0_#fff]",
      "md:h-12 md:flex-row md:gap-2 md:px-4 md:text-base md:data-[state=active]:shadow-[inset_0_-3px_0_#fff]",
      className,
    )}
    {...props}
  />
);
export const TabsContent = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) => (
  <TabsPrimitive.Content className={cn("mt-5 focus-visible:outline-none", className)} {...props} />
);

const calloutIcon = { green: CircleCheck, amber: TriangleAlert, blue: Info };
const calloutStyle = { green: "bg-ok-bg text-ok-fg", amber: "bg-warn-bg text-warn-fg", blue: "bg-info-bg text-info-fg" };
export const Callout = ({ tone = "green", children }: { tone?: "green" | "amber" | "blue"; children: React.ReactNode }) => {
  const Icon = calloutIcon[tone];
  return (
    <div className={cn("flex gap-3 rounded-md px-4 py-3 text-base leading-relaxed", calloutStyle[tone])} role={tone === "amber" ? "alert" : "status"}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="text-ink">{children}</div>
    </div>
  );
};

export const Segmented = <T extends string>({ options, value, onChange, label }: { options: T[]; value: T; onChange: (v: T) => void; label: string }) => (
  <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
    {options.map((option) => (
      <button
        key={option}
        role="radio"
        aria-checked={value === option}
        onClick={() => onChange(option)}
        className={cn("min-h-11 rounded px-4 text-base font-semibold transition-colors", value === option ? "bg-ink text-bg" : "bg-surface2 text-muted hover:text-ink")}
      >
        {option}
      </button>
    ))}
  </div>
);
