import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const tones = {
  neutral: "bg-paper text-ink",
  amber: "bg-amber-soft text-amber",
  pine: "bg-pine-soft text-pine",
  copper: "bg-copper-soft text-copper",
  sea: "bg-sea-soft text-sea",
} as const;

export type PillTone = keyof typeof tones;

export function stateTone(state: string): PillTone {
  if (state === "ACTIVE") return "amber";
  if (state === "STOPPED") return "sea";
  return "neutral";
}

export function decisionTone(decision: string): PillTone {
  if (decision === "CANCEL") return "pine";
  if (decision === "DEFER") return "sea";
  if (decision === "ALLOW") return "amber";
  return "neutral";
}

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: PillTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[11px] tracking-wide",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
