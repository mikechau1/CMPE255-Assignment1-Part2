"use client";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Slot } from "@radix-ui/react-slot";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Check } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/*
 * Thin wrappers over Radix primitives. Radix supplies the behaviour that is
 * genuinely hard to get right — focus traps, typeahead, escape handling, ARIA
 * wiring — and these add only the project's visual language on top.
 */

// --- Button ---------------------------------------------------------------

const BUTTON_VARIANTS = {
  primary:
    "bg-accent text-accent-foreground shadow-sm hover:brightness-110 active:brightness-95",
  secondary:
    "bg-surface text-foreground ring-1 ring-border hover:bg-surface-muted active:bg-surface-muted",
  ghost: "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
  danger: "bg-danger text-white shadow-sm hover:brightness-110",
  subtle: "bg-surface-muted text-foreground hover:bg-border/60",
} as const;

const BUTTON_SIZES = {
  sm: "h-8 gap-1.5 px-2.5 text-[13px]",
  md: "h-9 gap-2 px-3.5 text-sm",
  lg: "h-11 gap-2 px-5 text-[15px]",
  icon: "size-8 justify-center",
  "icon-sm": "size-7 justify-center",
} as const;

export interface ButtonProps extends React.ComponentPropsWithoutRef<"button"> {
  variant?: keyof typeof BUTTON_VARIANTS;
  size?: keyof typeof BUTTON_SIZES;
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "secondary", size = "md", asChild, ...props },
  ref,
) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      ref={ref}
      className={cn(
        "inline-flex cursor-pointer items-center rounded-lg font-medium transition-[background-color,color,filter,box-shadow] duration-150",
        "disabled:pointer-events-none disabled:opacity-50",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    />
  );
});

// --- Inputs ---------------------------------------------------------------

export const Input = React.forwardRef<HTMLInputElement, React.ComponentPropsWithoutRef<"input">>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          "h-9 w-full rounded-lg bg-surface px-3 text-sm text-foreground ring-1 ring-border",
          "placeholder:text-subtle-foreground",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-60",
          className,
        )}
        {...props}
      />
    );
  },
);

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentPropsWithoutRef<"textarea">
>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn(
        "w-full resize-none rounded-lg bg-surface px-3 py-2 text-sm leading-relaxed text-foreground ring-1 ring-border",
        "placeholder:text-subtle-foreground",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      {...props}
    />
  );
});

// --- Checkbox -------------------------------------------------------------

export const Checkbox = React.forwardRef<
  React.ComponentRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(function Checkbox({ className, ...props }, ref) {
  return (
    <CheckboxPrimitive.Root
      ref={ref}
      className={cn(
        "group peer grid size-[18px] shrink-0 cursor-pointer place-items-center rounded-full",
        "ring-1 ring-border-strong transition-colors duration-150",
        "hover:ring-accent data-[state=checked]:bg-accent data-[state=checked]:ring-accent",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="animate-pop text-accent-foreground">
        <Check className="size-3" strokeWidth={3.5} />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
});

// --- Dialog ---------------------------------------------------------------

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

export function DialogContent({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 animate-fade-in bg-[var(--overlay)] backdrop-blur-[2px]" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 w-[min(36rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2",
          "animate-slide-up rounded-xl bg-surface p-5 shadow-2xl ring-1 ring-border focus:outline-none",
          className,
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

// --- Popover --------------------------------------------------------------

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export function PopoverContent({
  className,
  align = "start",
  sideOffset = 6,
  ...props
}: React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 animate-slide-up rounded-xl bg-surface p-1.5 shadow-xl ring-1 ring-border focus:outline-none",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}

// --- Dropdown menu --------------------------------------------------------

export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;
export const DropdownMenuSeparator = React.forwardRef<
  React.ComponentRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(function DropdownMenuSeparator({ className, ...props }, ref) {
  return (
    <DropdownMenuPrimitive.Separator
      ref={ref}
      className={cn("my-1 h-px bg-border", className)}
      {...props}
    />
  );
});

export function DropdownMenuContent({
  className,
  align = "end",
  sideOffset = 6,
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-44 animate-slide-up rounded-xl bg-surface p-1.5 shadow-xl ring-1 ring-border focus:outline-none",
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

export const DropdownMenuItem = React.forwardRef<
  React.ComponentRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & { destructive?: boolean }
>(function DropdownMenuItem({ className, destructive, ...props }, ref) {
  return (
    <DropdownMenuPrimitive.Item
      ref={ref}
      className={cn(
        "flex cursor-pointer select-none items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm outline-none",
        "data-[highlighted]:bg-surface-muted",
        destructive ? "text-danger data-[highlighted]:bg-danger-soft" : "text-foreground",
        className,
      )}
      {...props}
    />
  );
});

// --- Tooltip --------------------------------------------------------------

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({
  content,
  children,
  side = "bottom",
  shortcut,
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  shortcut?: string;
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 flex animate-fade-in items-center gap-2 rounded-lg bg-foreground px-2 py-1 text-xs font-medium text-background shadow-lg"
        >
          {content}
          {shortcut ? <Kbd className="bg-background/15 text-background">{shortcut}</Kbd> : null}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

// --- Small pieces ---------------------------------------------------------

export function Kbd({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded border border-border bg-surface-muted px-1.5",
        "font-sans text-[11px] font-medium text-muted-foreground",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div style={style} className={cn("animate-pulse rounded-md bg-surface-muted", className)} />;
}

export function Chip({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<"span">) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
