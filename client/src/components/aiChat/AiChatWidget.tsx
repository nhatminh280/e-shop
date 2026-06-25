import { useState } from "react";
import { MessageCircle } from "lucide-react";
import AiChatPanel from "./AiChatPanel";

export default function AiChatWidget() {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {open && <AiChatPanel onClose={() => setOpen(false)} />}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="group relative flex h-14 w-14 items-center justify-center rounded-full bg-stone-900 text-white shadow-xl transition-all duration-200 hover:scale-105 hover:bg-stone-800 hover:shadow-2xl focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2"
        aria-label={open ? "Close shop assistant" : "Open shop assistant"}
      >
        {!open && (
          <span
            className="pointer-events-none absolute inset-0 rounded-full bg-stone-900 opacity-20 animate-ping"
            aria-hidden="true"
          />
        )}
        <MessageCircle className="h-5 w-5 relative" />
      </button>
    </div>
  );
}
