"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = saved ? saved === "dark" : prefersDark;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  if (!mounted) return null;

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className={`p-2 rounded-full transition-colors
        bg-white/20 hover:bg-white/30 text-white
        ${className}`}
    >
      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
    </button>
  );
}

/** Inline script injected in <head> to prevent flash of wrong theme */
export function ThemeScript() {
  const script = `
(function(){
  var s=localStorage.getItem('theme');
  var p=window.matchMedia('(prefers-color-scheme: dark)').matches;
  if(s==='dark'||(s===null&&p)){document.documentElement.classList.add('dark')}
})();
  `.trim();
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
