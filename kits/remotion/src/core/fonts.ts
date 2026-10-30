import { localFont } from "./local-fonts";

/** Only families actually used by the shipped templates are configured. */
const DEFS = {
  display: { module: "PlayfairDisplay", style: "normal", fallback: "serif" },
  scriptThin: { module: "Tangerine", style: "normal", fallback: "cursive" },
  avenir: { module: "NunitoSans", style: "normal", fallback: "sans-serif" },
  bodoni: { module: "BodoniModa", style: "normal", fallback: "serif" },
  condensed: { module: "BarlowCondensed", style: "normal", fallback: "sans-serif" },
  songti: { module: "NotoSerifSC", style: "normal", fallback: "serif" },
  hand: { module: "ZhiMangXing", style: "normal", fallback: "cursive" },
  running: { module: "ZhiMangXing", style: "normal", fallback: "cursive" },
  caveat: { module: "Caveat", style: "normal", fallback: "cursive" },
  lora: { module: "Lora", style: "normal", fallback: "serif" },
  loraItalic: { module: "Lora", style: "italic", fallback: "serif" },
  emoji: { module: "NotoColorEmoji", style: "normal", fallback: "sans-serif" },
  serif: { module: "CormorantGaramond", style: "normal", fallback: "Georgia, serif" },
  heiti: { module: "NotoSansSC", style: "normal", fallback: "sans-serif" },
  brush: { module: "MaShanZheng", style: "normal", fallback: "cursive" },
  pen: { module: "LongCang", style: "normal", fallback: "cursive" },
  kuaile: { module: "ZCOOLKuaiLe", style: "normal", fallback: "sans-serif" },
  mono: { module: "JetBrainsMono", style: "normal", fallback: "monospace" },
} as const;

/** Kept in shared drawing-kit types; using these requires an explicit local package addition. */
type UnconfiguredFontKey = "serifItalic" | "script" | "sans" | "baskervilleItalic" | "xiaowei";
export type FontKey = keyof typeof DEFS | UnconfiguredFontKey;

export function fontFor(key: FontKey, text: string, weight = 400): string {
  if (!(key in DEFS)) throw new Error(`Font key "${key}" is not configured in this VVV kit; add its local font files explicitly.`);
  const def = DEFS[key as keyof typeof DEFS];
  return `"${localFont(def.module, text, weight, def.style)}", ${def.fallback}`;
}

/** Packaged font module behind a key (e.g. "songti" → "NotoSerifSC"); used for width estimates. */
export const fontModuleOf = (key: FontKey): string | undefined => (key in DEFS ? DEFS[key as keyof typeof DEFS].module : undefined);

export const fontStyleOf = (key: FontKey): "normal" | "italic" =>
  key in DEFS ? DEFS[key as keyof typeof DEFS].style : key === "serifItalic" || key === "baskervilleItalic" ? "italic" : "normal";
