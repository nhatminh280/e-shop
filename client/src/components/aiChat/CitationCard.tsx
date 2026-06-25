import { useState } from "react";
import { ChevronDown, ChevronUp, BookOpen } from "lucide-react";
import type { AiCitation } from "../../types/aiChat";

interface Props {
  citation: AiCitation;
}

export default function CitationCard({ citation }: Props) {
  const [open, setOpen] = useState(false);
  const scoreLabel = citation.score != null ? citation.score.toFixed(2) : null;

  return (
    <div className="rounded-lg border border-stone-200 bg-stone-50 text-xs">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-left transition hover:bg-stone-100"
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <BookOpen className="h-3.5 w-3.5 flex-shrink-0 text-stone-500" />
          <span className="truncate font-medium text-stone-700">{citation.title || citation.sourceId}</span>
          {scoreLabel && (
            <span className="ml-1 flex-shrink-0 rounded bg-stone-200/70 px-1 text-[10px] text-stone-600">
              {scoreLabel}
            </span>
          )}
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-stone-400" /> : <ChevronDown className="h-3.5 w-3.5 text-stone-400" />}
      </button>
      {open && citation.snippet && (
        <div className="border-t border-stone-200 px-2.5 py-1.5 leading-snug text-stone-600">
          {citation.snippet}
        </div>
      )}
    </div>
  );
}
