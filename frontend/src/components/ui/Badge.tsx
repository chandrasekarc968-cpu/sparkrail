import React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'outline' | 'neutral' | 'engineering' | 'ohe' | 'snt' | 'frozen';
  size?: 'sm' | 'default';
}

export function Badge({ className, variant = "default", size = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border font-semibold tracking-wide transition-colors whitespace-nowrap select-none",
        {
          "px-2 py-0.5 text-xs": size === 'default',
          "px-1.5 py-0.2 text-[10px]": size === 'sm',
        },
        {
          "border-transparent bg-neutral-800 text-neutral-50": variant === "default",
          "border-op-green/30 bg-op-green/15 text-op-green-dark": variant === "success",
          "border-op-amber/40 bg-op-amber/15 text-op-amber-dark": variant === "warning",
          "border-op-red/30 bg-op-red/15 text-op-red-dark": variant === "danger",
          "border-op-blue/30 bg-op-blue/15 text-op-blue-dark": variant === "info",
          "border-neutral-300 bg-neutral-100 text-neutral-800": variant === "neutral",
          "border-neutral-300 bg-white text-neutral-800": variant === "outline",
          // Railway departments
          "border-red-300 bg-red-50 text-red-800 font-mono": variant === "engineering",
          "border-blue-300 bg-blue-50 text-blue-800 font-mono": variant === "ohe",
          "border-amber-400 bg-amber-50 text-amber-900 font-mono": variant === "snt",
          // Frozen week treatment
          "border-amber-500/50 bg-amber-100/60 text-amber-950 pattern-frozen-week font-mono": variant === "frozen",
        },
        className
      )}
      {...props}
    />
  );
}
