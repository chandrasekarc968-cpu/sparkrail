import React from "react";
import { cn } from "../../lib/utils";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'ghost' | 'danger' | 'success' | 'amber';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', isLoading = false, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer",
          // Base touch target
          "min-h-[44px]",
          {
            'bg-accent-600 text-white hover:bg-accent-500 active:bg-accent-700 shadow-sm': variant === 'default',
            'border border-neutral-300 bg-white hover:bg-neutral-100 active:bg-neutral-200 text-neutral-900': variant === 'outline',
            'hover:bg-neutral-150 active:bg-neutral-200 text-neutral-700': variant === 'ghost',
            'bg-op-red text-white hover:bg-op-red-dark active:opacity-90 shadow-sm': variant === 'danger',
            'bg-op-green text-white hover:bg-op-green-dark active:opacity-90 shadow-sm': variant === 'success',
            'bg-amber-600 text-white hover:bg-amber-500 active:bg-amber-700 shadow-sm': variant === 'amber',
            'px-4 py-2': size === 'default',
            'px-3 py-1.5 text-xs min-h-[44px]': size === 'sm',
            'px-6 py-3 text-base': size === 'lg',
            'w-11 h-11 p-0 flex items-center justify-center': size === 'icon',
          },
          className
        )}
        {...props}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin shrink-0" />
            <span>{children}</span>
          </>
        ) : (
          children
        )}
      </button>
    );
  }
);
Button.displayName = "Button";
