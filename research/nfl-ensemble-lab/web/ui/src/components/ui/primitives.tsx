import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../lib";

// Small building blocks written by hand so the app has no generated code to maintain. Surfaces are flat and square,
// separated by a tone step rather than borders or shadows.
export const Card = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("bg-panel p-5", className)} {...props} />
);

export const Label = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("text-[15px] text-muted", className)} {...props} />
);

const badge = cva("inline-flex shrink-0 items-center rounded-sm px-2 py-0.5 text-sm font-semibold", {
  variants: { tone: { neutral: "bg-line text-slate-300", red: "bg-red-950 text-red-300", amber: "bg-amber-950 text-amber-300", green: "bg-emerald-950 text-emerald-300" } },
  defaultVariants: { tone: "neutral" },
});
export const Badge = ({ tone, className, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) => (
  <span className={cn(badge({ tone }), className)} {...props} />
);

export const Tabs = TabsPrimitive.Root;
export const TabsList = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) => (
  <TabsPrimitive.List className={cn("flex gap-6 overflow-x-auto border-b-2 border-panel", className)} {...props} />
);
export const TabsTrigger = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) => (
  <TabsPrimitive.Trigger
    className={cn("-mb-0.5 min-h-[44px] shrink-0 focus-visible:outline-offset-[-3px] whitespace-nowrap border-b-[3px] border-transparent text-base text-muted transition-colors hover:text-white data-[state=active]:border-accent data-[state=active]:text-white", className)}
    {...props}
  />
);
export const TabsContent = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) => (
  <TabsPrimitive.Content className={cn("mt-5", className)} {...props} />
);

export const Callout = ({ tone = "green", children }: { tone?: "green" | "amber" | "blue"; children: React.ReactNode }) => (
  <div className={cn("px-5 py-3.5 text-[15px] leading-relaxed text-white", tone === "green" && "bg-[#18281e]", tone === "amber" && "bg-[#2b2510]", tone === "blue" && "bg-[#1a2230]")}>
    {children}
  </div>
);

export const Segmented = <T extends string>({ options, value, onChange, label }: { options: T[]; value: T; onChange: (v: T) => void; label: string }) => (
  <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-0.5">
    {options.map((option) => (
      <button
        key={option}
        role="radio"
        aria-checked={value === option}
        onClick={() => onChange(option)}
        className={cn("min-h-[44px] px-4 text-[15px] transition-colors", value === option ? "bg-white text-bg" : "bg-panel text-slate-300 hover:bg-line hover:text-white")}
      >
        {option}
      </button>
    ))}
  </div>
);
