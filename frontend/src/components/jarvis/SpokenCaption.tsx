import { useEffect, useState } from "react";

export function SpokenCaption({ text }: { text: string }) {
  const [shown, setShown] = useState("");

  useEffect(() => {
    setShown("");
    if (!text) return;
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) window.clearInterval(id);
    }, 22);
    return () => window.clearInterval(id);
  }, [text]);

  if (!text) return null;

  return (
    <div className="pointer-events-none max-w-2xl px-6 text-center">
      <div className="font-mono text-[11px] tracking-[0.3em] text-[color:var(--jv-cyan)]/60 mb-2">
        &gt; JARVIS RESPONSE
      </div>
      <p className="font-sans text-lg leading-relaxed text-white/90">
        {shown}
        <span
          className="inline-block w-2 text-[color:var(--jv-cyan)]"
          style={{ animation: "jv-caret 0.8s step-end infinite" }}
        >
          ▍
        </span>
      </p>
    </div>
  );
}
