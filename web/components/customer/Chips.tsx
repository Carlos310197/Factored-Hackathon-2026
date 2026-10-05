"use client";
import type { Lang } from "@/lib/contract";

export function Chips({ options, disabled, onPick }: { options: string[]; lang: Lang; disabled: boolean; onPick: (o: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2 pl-1">
      {options.map((o) => (
        <button key={o} type="button" disabled={disabled} onClick={() => onPick(o)}
          className="min-h-11 rounded-full border-[1.5px] border-b-cobalt bg-b-surface px-4 text-sm font-semibold text-b-cobalt transition-colors hover:bg-b-mist focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-b-cobalt disabled:opacity-50">
          {o}
        </button>
      ))}
    </div>
  );
}
