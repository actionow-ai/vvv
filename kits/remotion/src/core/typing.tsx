import React, { type CSSProperties } from "react";
import { AbsoluteFill } from "remotion";
import { fontFor, type FontKey } from "./fonts";
import { useT } from "./time";

/**
 * A line typed one character at a time with a caret: solid while typing, blinking on the half beat
 * after. `caret: "block"` is a terminal-style block, `"bar"` a thin text cursor. Hidden characters
 * keep their space, so the line never shifts as it grows.
 */
export const Typed: React.FC<{ text: string; x: number; y: number; start: number; step: number; beat: number; size: number; anchor?: "lm" | "cm" | "rm";
  font?: FontKey; color?: string; tracking?: number; caret?: "block" | "bar"; caretUntil?: number; until?: number; style?: CSSProperties }> = ({
  text, x, y, start, step, beat, size, anchor = "lm", font = "songti", color = "#F4F1EC", tracking = 4, caret = "block", caretUntil = Infinity, until = Infinity, style,
}) => {
  const t = useT();
  if (t < start || t >= until || !text) return null;
  const chars = [...text];
  const shown = Math.min(chars.length, Math.floor((t - start) / step) + 1);
  const doneAt = start + chars.length * step;
  const on = t < caretUntil && (t < doneAt || Math.floor((t - doneAt) / (beat / 2)) % 2 === 1);
  const shift = { lm: "0", cm: "-50%", rm: "-100%" }[anchor];
  const box: CSSProperties = {
    position: "absolute", left: x, top: y, transform: `translate(${shift}, -50%)`,
    fontFamily: fontFor(font, text), fontSize: size, letterSpacing: tracking, color, whiteSpace: "pre", lineHeight: 1.2, ...style,
  };
  const cursor: CSSProperties = caret === "block"
    ? { display: "inline-block", width: size * 0.5, height: size * 1.02, marginLeft: 2, verticalAlign: "-0.16em", background: on ? color : "transparent" }
    : { display: "inline-block", width: Math.max(2, size * 0.06), height: size * 1.05, marginLeft: 3, verticalAlign: "-0.18em", background: on ? color : "transparent" };
  return (
    <div style={box}>
      {chars.slice(0, shown).join("")}
      <span style={cursor} />
      <span style={{ visibility: "hidden" }}>{chars.slice(shown).join("")}</span>
    </div>
  );
};

/**
 * Soft out-of-focus lights drift slowly across a dark frame, like dust in a projector beam, so a page
 * of typed text alone never freezes. Seeded, so every render is the same.
 */
const lightsOf = (seed: number, count: number) => {
  let s = seed;
  const rnd = () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
  return Array.from({ length: count }, () => ({ x: rnd() * 2200, y: rnd() * 1200, r: 50 + rnd() * 110, a: 0.05 + rnd() * 0.07, vx: 14 + rnd() * 26, vy: -8 - rnd() * 16 }));
};

export const DriftLights: React.FC<{ seed?: number; count?: number; rgb?: string; background?: string }> = ({ seed = 23, count = 16, rgb = "255,232,205", background = "#000" }) => {
  const t = useT();
  const lights = React.useMemo(() => lightsOf(seed, count), [seed, count]);
  return (
    <AbsoluteFill style={{ background }}>
      {lights.map((l, i) => {
        const x = ((l.x + l.vx * t) % 2200) - 140;
        const y = ((((l.y + l.vy * t) % 1200) + 1200) % 1200) - 60;
        return <div key={i} style={{ position: "absolute", left: x - l.r, top: y - l.r, width: l.r * 2, height: l.r * 2, borderRadius: "50%",
          background: `radial-gradient(circle, rgba(${rgb},${l.a}) 0%, rgba(${rgb},${l.a * 0.6}) 45%, rgba(${rgb},0) 70%)` }} />;
      })}
    </AbsoluteFill>
  );
};
