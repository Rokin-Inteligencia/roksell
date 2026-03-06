"use client";

import { useState, useRef, useEffect } from "react";

type FieldTooltipProps = {
  text: string;
  id?: string;
};

export function FieldTooltip({ text, id }: FieldTooltipProps) {
  const [visible, setVisible] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!visible) return;
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setVisible(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [visible]);

  return (
    <span ref={wrapperRef} className="relative inline-flex ml-1">
      <button
        type="button"
        aria-label="Mais informações"
        tabIndex={-1}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onClick={(e) => {
          e.preventDefault();
          setVisible((v) => !v);
        }}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-semibold text-slate-500 bg-slate-200 hover:bg-slate-300 hover:text-slate-700 transition-colors"
      >
        ?
      </button>
      {visible && (
        <span
          id={id}
          role="tooltip"
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 z-50 px-2 py-1.5 text-xs text-slate-700 bg-slate-800 text-white rounded-lg shadow-lg max-w-[220px] whitespace-normal pointer-events-none"
        >
          {text}
        </span>
      )}
    </span>
  );
}
