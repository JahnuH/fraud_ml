// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
// Change anything here and it propagates everywhere.

// ── Colors ───────────────────────────────────────────────────────────────────
export const C = {
  navy:   "#1C2B3A",   // sidebar, dark panels
  sand:   "#F5F0E8",   // page background
  border: "#E8E0D0",   // card borders, dividers
  gold:   "#C8A96E",   // accent, CTA buttons, active nav
  white:  "#FFFFFF",   // card backgrounds
  text:   "#2D3748",   // primary body text
  muted:  "#8A9BB0",   // labels, subtitles
  green:  "#2D6A4F",   // healthy / success
  red:    "#9B2335",   // error / alert

  // Dark panel (response/terminal area)
  dark:       "#1C2B3A",
  darkPanel:  "#131F2B",
  darkBorder: "#243447",
  darkMid:    "#1A2A38",

  // Semantic
  successText: "#86EFAC",
  errorText:   "#F4A0A0",
  errorBg:     "#2A1A1E",
  successBg:   "#162A1E",
  codeFg:      "#E2C98A",
};

// ── Chart colors (cycle through for multi-series) ─────────────────────────────
export const CHART_COLORS = [
  C.gold,
  "#6D8196",
  C.green,
  C.red,
  C.muted,
];

// ── Typography ────────────────────────────────────────────────────────────────
export const font = {
  sans: "font-sans",   // default UI font (Tailwind: Inter / system)
  mono: "font-mono",   // code, numbers, timestamps
};

// ── Reusable class strings ────────────────────────────────────────────────────
export const cls = {
  label:
    "block mb-1.5 text-[11px] font-bold uppercase tracking-widest text-[#8A9BB0]",

  input:
    "w-full px-3.5 py-2.5 rounded-lg border text-sm outline-none transition-all bg-white placeholder-[#B0A898]" +
    " border-[#E8E0D0] text-[#2D3748] focus:ring-2 focus:ring-[#C8A96E]/40 focus:border-[#C8A96E]",

  inputError:
    "w-full px-3.5 py-2.5 rounded-lg border text-sm outline-none transition-all bg-white placeholder-[#B0A898]" +
    " text-[#2D3748] focus:ring-2 focus:ring-[#9B2335]/40 focus:border-[#9B2335]",

  btnPrimary:
    "px-8 py-2.5 rounded-lg text-sm font-bold tracking-wide uppercase transition-all",

  btnOutline:
    "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-semibold transition-all",

  card:
    "rounded-xl border",

  panelHeader:
    "px-7 py-5 border-b flex items-center justify-between",

  sidebarLink:
    "w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center",
};
