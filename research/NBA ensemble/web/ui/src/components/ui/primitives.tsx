import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../lib";

// Small shadcn-style building blocks (cards, badges, tabs) written by hand so the app has no generated code to maintain.
export const Card = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("rounded-2xl border border-line bg-panel p-4", className)} {...props} />
);

const badge = cva("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", {
  variants: { tone: { neutral: "bg-line text-slate-300", red: "bg-red-950 text-red-300", amber: "bg-amber-950 text-amber-300", green: "bg-emerald-950 text-emerald-300" } },
  defaultVariants: { tone: "neutral" },
});
export const Badge = ({ tone, className, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) => (
  <span className={cn(badge({ tone }), className)} {...props} />
);

export const Tabs = TabsPrimitive.Root;
export const TabsList = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) => (
  <TabsPrimitive.List className={cn("inline-flex flex-wrap gap-1 rounded-xl border border-line bg-panel p-1", className)} {...props} />
);
export const TabsTrigger = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) => (
  <TabsPrimitive.Trigger
    className={cn("rounded-lg px-4 py-2 text-sm font-medium text-muted transition hover:text-white data-[state=active]:bg-emerald-950 data-[state=active]:text-accent data-[state=active]:ring-1 data-[state=active]:ring-accent", className)}
    {...props}
  />
);
export const TabsContent = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) => (
  <TabsPrimitive.Content className={cn("mt-4 focus:outline-none", className)} {...props} />
);

export const Callout = ({ tone = "green", children }: { tone?: "green" | "amber" | "blue"; children: React.ReactNode }) => (
  <div className={cn("rounded-lg border-l-4 bg-panel2 px-4 py-3 text-sm leading-relaxed", tone === "green" && "border-accent", tone === "amber" && "border-warn", tone === "blue" && "border-info")}>
    {children}
  </div>
);

export const Segmented = <T extends string>({ options, value, onChange, label }: { options: T[]; value: T; onChange: (v: T) => void; label: string }) => (
  <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
    {options.map((option) => (
      <button
        key={option}
        role="radio"
        aria-checked={value === option}
        onClick={() => onChange(option)}
        className={cn("rounded-full border px-3.5 py-1 text-sm transition", value === option ? "border-accent bg-emerald-950 text-accent" : "border-line bg-panel text-slate-300 hover:border-accent")}
      >
        {option}
      </button>
    ))}
  </div>
);
