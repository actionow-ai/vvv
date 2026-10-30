import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Text } from "../../components/Text";
import { coverFit } from "../../core/crop";
import { eBack, eOut3, eSine, lerp, ramp } from "../../core/ease";
import { getPhoto, photoSrc } from "../../core/manifest";
import { useT } from "../../core/time";
import { DriftLights, Typed } from "../../core/typing";

/**
 * Memoir pages: a handwritten life story on black. Lines are typed in a pen hand with a thin caret;
 * photos sit in a scanned film frame, on a scrolling 35 mm strip, as die-cut stickers with a coloured
 * outline, side by side under a chapter title, or in a camera viewfinder. All times are beats from
 * the page's first beat; D(n) = seconds of beat `at + n`.
 */

export const INK = "#F6F2EC";
const GREY = "rgba(246,242,236,0.72)";
const GROOM = "#38AEE0";
const BRIDE = "#F2646A";
const GOLD = "#F8B42A";

export type Ctx = {
  B: (n: number) => number;
  ph: Record<string, string | string[]>;
  copy: Record<string, string>;
  groom: string;
  bride: string;
  /** "2026.9.19" */
  date: string;
  since: string;
};

export type PageProps = { c: Ctx; at: number; len: number };

export const lines = (s: string) => s.split(/[｜|]/).map((x) => x.trim()).filter(Boolean);
const fill = (c: Ctx, s: string) => s.replace("{since}", c.since).replace("{date}", c.date);

const listOf = (c: Ctx, slot: string) => {
  const v = c.ph[slot];
  return (Array.isArray(v) ? v : v ? [v] : []).filter(Boolean);
};

type Box = { x: number; y: number; w: number; h: number };

/** A photo cropped into a box around the faces, with a slow zoom so it never freezes. */
const Pic: React.FC<{ id: string; box: Box; zoom?: number; ty?: number; opacity?: number; radius?: number; style?: React.CSSProperties }> = ({
  id, box, zoom = 1, ty = 0, opacity = 1, radius = 0, style,
}) => {
  if (!id || opacity <= 0.002) return null;
  const photo = getPhoto(id);
  const fit = coverFit(photo, box.w, box.h);
  return (
    <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, overflow: "hidden", opacity, borderRadius: radius,
      transform: ty ? `translateY(${ty}px)` : undefined, ...style }}>
      <Img src={photoSrc(photo)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: fit.objectPosition,
        transformOrigin: fit.transformOrigin, transform: `scale(${zoom})` }} />
    </div>
  );
};

/** Outline that follows a cut-out's transparent edge (or a photo's rectangle). */
const outline = (color: string, w: number) =>
  [[w, 0], [-w, 0], [0, w], [0, -w]].map(([x, y]) => `drop-shadow(${x}px ${y}px 0 ${color})`).join(" ");

/**
 * A photo shown whole as a sticker, standing on its bottom centre: a cut-out (PNG with transparency)
 * gets a white die-cut border and a coloured line; an ordinary photo becomes a bordered card.
 */
const Sticker: React.FC<{ id: string; cx: number; bottom: number; height: number; pop: number; rotate?: number; color?: string }> = ({
  id, cx, bottom, height, pop, rotate = 0, color,
}) => {
  if (!id || pop <= 0.002) return null;
  const photo = getPhoto(id);
  const width = (height * photo.width) / photo.height;
  const filter = [outline("#FFFFFF", 6), color ? outline(color, 4) : ""].join(" ");
  return (
    <Img src={photoSrc(photo)} style={{ position: "absolute", left: cx - width / 2, top: bottom - height, width, height, filter,
      transform: `rotate(${rotate}deg) scale(${pop})`, transformOrigin: "50% 100%" }} />
  );
};

/**
 * A slide changes the picture most a little after it starts, so slides start this share of a beat
 * early to put that peak on the beat.
 */
const LEAD = 0.42;

/** Page clock: D(n), a fade from beat n, a pop and a slide peaking on beat n, a page-long zoom, the fade-out. */
const usePage = (c: Ctx, at: number, len: number) => {
  const t = useT();
  const D = (n: number) => c.B(at + n);
  const beat = D(1) - D(0);
  const fade = (n: number, beats = 1) => eSine(ramp(t, D(n), D(n + beats)));
  const pop = (n: number) => Math.max(0, eBack(ramp(t, D(n - 0.25), D(n + 0.6)), 1.6));
  const slide = (n: number, beats = 1.4, lead = LEAD) => eOut3(ramp(t, D(n - lead), D(n - lead + beats)));
  /** a gentle sway once a sticker has landed: -1..1, one swing every two beats */
  const sway = (k = 0) => Math.sin(((t - D(0)) / beat) * Math.PI + k);
  // the fade-out is centred on the page's last beat but one, so its biggest change lands on a beat
  const out = 1 - eSine(ramp(t, D(len - 1.4), D(len - 0.6)));
  const drift = (z0 = 1.1, z1 = 1, from = 0, to = len) => lerp(z0, z1, ramp(t, D(from), D(to)));
  return { t, D, beat, fade, pop, slide, sway, out, drift };
};

/**
 * Lines typed one after another in the pen hand, each starting a beat after the previous one ends.
 * `perChar` is beats per character. Returns the beat the last line finishes.
 */
const typedLines = (text: string, o: { x: number; y: number; gap: number; D: (n: number) => number; from: number; size: number; perChar?: number;
  anchor?: "lm" | "cm" | "rm"; color?: string; until?: number; shadow?: boolean }) => {
  const ls = lines(text);
  const perChar = o.perChar ?? 0.25;
  const beat = o.D(1) - o.D(0);
  let n = o.from;
  const nodes = ls.map((l, i) => {
    const start = n;
    n += Math.ceil([...l].length * perChar) + 1;
    return <Typed key={i} text={l} x={o.x} y={o.y + (i - (ls.length - 1) / 2) * o.gap} start={o.D(start)} step={beat * perChar} beat={beat} size={o.size}
      anchor={o.anchor ?? "cm"} font="pen" caret="bar" tracking={2} color={o.color ?? INK} until={o.until}
      caretUntil={i < ls.length - 1 ? o.D(n - 0.5) : Infinity} style={o.shadow ? { textShadow: "0 2px 12px rgba(0,0,0,0.75)" } : undefined} />;
  });
  return { nodes, end: n };
};

// ---------------------------------------------------------------- ambient light

/** Soft drifting lights behind every page, so a page of typed text alone never freezes. */
export const Ambient: React.FC = () => <DriftLights seed={41} count={24} />;

// ---------------------------------------------------------------- 1 · typed welcome

export const Welcome: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, beat, out } = usePage(c, at, len);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Typed text={c.copy.welcome} x={960} y={360} start={D(0.5)} step={beat / 2} beat={beat} size={76} anchor="cm" font="pen" caret="bar" tracking={4} color={INK} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 2 · photos in a scanned film frame, with quotes

export const Intro: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, fade, out, drift } = usePage(c, at, len);
  const ids = listOf(c, "intro");
  const per = len / Math.max(1, ids.length);
  const one = typedLines(c.copy.intro_1, { x: 960, y: 540, gap: 80, D, from: 1, size: 64, until: D(len / 2), shadow: true });
  const two = typedLines(c.copy.intro_2, { x: 960, y: 540, gap: 80, D, from: len / 2 + 1, size: 64, shadow: true });
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {ids.map((id, i) => (
        <Pic key={i} id={id} box={{ x: 0, y: 0, w: 1920, h: 1080 }} zoom={drift(1.1, 1, i * per, (i + 1) * per + 1)} opacity={i === 0 ? fade(-0.5, 1) : fade(i * per - 0.25, 0.5)} />
      ))}
      <Img src={staticFile("assets/memoir/film-frame.png")} style={{ position: "absolute", inset: 0, width: 1920, height: 1080 }} />
      {one.nodes}
      {two.nodes}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 3 · the couple as a sticker, thanks, confetti

const CONFETTI = (() => {
  let s = 7;
  const rnd = () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
  const colors = ["#F8B42A", "#F2646A", "#38AEE0", "#7BD389", "#C58CF2", "#FFFFFF"];
  return Array.from({ length: 90 }, () => ({ x: rnd() * 1920, delay: rnd() * 2.4, speed: 160 + rnd() * 220, w: 8 + rnd() * 10, h: 4 + rnd() * 6, spin: 120 + rnd() * 360,
    sway: 20 + rnd() * 40, color: colors[Math.floor(rnd() * colors.length)] }));
})();

export const Thanks: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, pop, out } = usePage(c, at, len);
  const text = typedLines(c.copy.thanks, { x: 1060, y: 520, gap: 96, D, from: 1.5, size: 58, anchor: "lm" });
  const t0 = D(2);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Sticker id={listOf(c, "couple")[0]} cx={560} bottom={1020} height={880} pop={pop(0)} rotate={-2} />
      {text.nodes}
      {t > t0 ? CONFETTI.map((p, i) => {
        const dt = t - t0 - p.delay;
        if (dt < 0) return null;
        const y = -40 + dt * p.speed;
        if (y > 1120) return null;
        return <div key={i} style={{ position: "absolute", left: p.x + Math.sin(dt * 2 + i) * p.sway, top: y, width: p.w, height: p.h, background: p.color,
          transform: `rotate(${dt * p.spin}deg)`, opacity: 0.9 }} />;
      }) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 4 · where we were born: hometown and child stickers

const ARROW = { src: "assets/memoir/doodle-arrow.png", w: 600, h: 444 };

export const Born: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, beat, fade, pop, sway, out } = usePage(c, at, len);
  const side = (k: 0 | 1) => {
    const right = k === 1;
    const color = right ? BRIDE : GROOM;
    const mirror = (x: number) => (right ? 1920 - x : x);
    return (
      <React.Fragment key={k}>
        <Sticker id={listOf(c, right ? "homeBride" : "homeGroom")[0]} cx={mirror(480)} bottom={880} height={560} pop={pop(1 + k * 0.5)} rotate={(right ? 2 : -2) + 1.2 * sway(k)} color={color} />
        <Sticker id={listOf(c, right ? "kidBride" : "kidGroom")[0]} cx={mirror(690)} bottom={990} height={430} pop={pop(2 + k * 0.5)} rotate={(right ? -3 : 3) + 2 * sway(k + 1.6)} color={color} />
        <Text font="heiti" weight={900} size={50} tracking={4} color={INK} x={mirror(140)} y={980} anchor={right ? "rm" : "lm"} opacity={fade(3 + k * 0.5, 0.6)}
          style={{ textShadow: "0 3px 10px rgba(0,0,0,0.8)" }}>{c.copy[right ? "home_bride" : "home_groom"]}</Text>
        {/* the name is written just inside the child sticker, with an arrow curling down to the face */}
        <Img src={staticFile(ARROW.src)} style={{ position: "absolute", left: mirror(770) - (right ? 130 : 0), top: 470, width: 130, height: (130 * ARROW.h) / ARROW.w,
          opacity: fade(4 + k, 0.6), transform: right ? "scaleX(-1)" : undefined }} />
        <Typed text={right ? c.bride : c.groom} x={mirror(900)} y={440} start={D(4 + k)} step={beat / 4} beat={beat}
          size={50} anchor={right ? "lm" : "rm"} font="pen" caret="bar" color={color} caretUntil={D(5.5 + k)} />
      </React.Fragment>
    );
  };
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Typed text={c.copy.born_title} x={960} y={150} start={D(0.2)} step={beat / 4} beat={beat} size={68} anchor="cm" font="heiti" caret="bar" color={GOLD} tracking={4}
        caretUntil={D(3)} style={{ fontWeight: 900 }} />
      {side(0)}
      {side(1)}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 5 · a scrolling 35 mm strip of childhood photos

const FRAME = { w: 760, h: 520, gap: 44 };
const HOLE = { w: 26, h: 34, every: 56 };

export const Strip: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, slide, out, drift } = usePage(c, at, len);
  const ids = listOf(c, "childhood");
  const step = FRAME.w + FRAME.gap;
  const every = Math.max(2, Math.floor((len - 4) / Math.max(1, ids.length - 1)));
  // the strip comes in from the right, then advances one frame on every `every` beats
  // a whole strip moving changes the picture most as it starts, so each advance starts on its beat
  let offset = -(1920 - 280) * (1 - slide(0, 2, 0.05));
  for (let j = 1; j < ids.length; j++) offset += step * slide(j * every, 1.6, 0.05);
  const x0 = 280 - offset;
  const top = 280;
  const band = 64;
  const holes = Math.ceil((ids.length * step + 2400) / HOLE.every);
  const half = Math.floor(ids.length / 2) * every;
  const one = typedLines(c.copy.strip_1, { x: 960, y: top + band + FRAME.h / 2, gap: 76, D, from: 2, size: 58, until: D(half), shadow: true });
  const two = typedLines(c.copy.strip_2, { x: 960, y: top + band + FRAME.h / 2, gap: 76, D, from: half + 1, size: 58, shadow: true });
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{ position: "absolute", left: x0 - 600, top, width: ids.length * step + 1800, height: FRAME.h + 2 * band, background: "#0B0A09",
        boxShadow: "0 0 40px rgba(0,0,0,0.6)" }} />
      {[top + (band - HOLE.h) / 2, top + band + FRAME.h + (band - HOLE.h) / 2].map((y, r) =>
        Array.from({ length: holes }, (_, k) => (
          <div key={`${r}-${k}`} style={{ position: "absolute", left: x0 - 600 + k * HOLE.every, top: y, width: HOLE.w, height: HOLE.h, borderRadius: 5, background: "rgba(232,226,214,0.9)" }} />
        )))}
      {ids.map((id, i) => (
        <React.Fragment key={i}>
          <Pic id={id} box={{ x: x0 + i * step, y: top + band, w: FRAME.w, h: FRAME.h }} zoom={drift(1.08, 1)} style={{ filter: "sepia(0.18) saturate(0.9) contrast(0.95)" }} />
          <Text font="mono" size={16} tracking={3} color="rgba(232,226,214,0.7)" x={x0 + i * step + 30} y={top + 12} anchor="lt">{`VVV 400  ▸ ${i * 2 + 12}A`}</Text>
          <Text font="mono" size={16} tracking={3} color="rgba(232,226,214,0.7)" x={x0 + i * step + FRAME.w - 30} y={top + band + FRAME.h + band - 30} anchor="rt">{`${i + 1}`}</Text>
        </React.Fragment>
      ))}
      {one.nodes}
      {two.nodes}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 6 · a typed line on black

const Line: React.FC<PageProps & { copy: string; size?: number; perChar?: number }> = ({ c, at, len, copy, size = 64, perChar = 0.25 }) => {
  const { D, out } = usePage(c, at, len);
  const text = typedLines(fill(c, c.copy[copy] ?? ""), { x: 960, y: 520, gap: size * 1.6, D, from: 0.5, size, perChar });
  return <AbsoluteFill style={{ opacity: out }}>{text.nodes}</AbsoluteFill>;
};

export const Jump: React.FC<PageProps> = (p) => <Line {...p} copy="jump" />;
export const Into: React.FC<PageProps> = (p) => <Line {...p} copy="into" />;
export const LoveTitle: React.FC<PageProps> = (p) => <Line {...p} copy="love_title" size={92} perChar={0.5} />;
export const Ending: React.FC<PageProps> = (p) => {
  const { fade } = usePage(p.c, p.at, p.len);
  return (
    <>
      <Line {...p} copy="ending" size={62} />
      <Text font="pen" size={40} tracking={6} color={GREY} x={960} y={760} anchor="cm" opacity={fade(7, 1.2)}>{`${p.c.groom} & ${p.c.bride}  ${p.c.date}`}</Text>
    </>
  );
};

// ---------------------------------------------------------------- 7 · chat screenshots and how we met

export const Chats: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, fade, pop, sway, out } = usePage(c, at, len);
  const ids = listOf(c, "chats");
  const text = typedLines(c.copy.chat_lines, { x: 1060, y: 540, gap: 92, D, from: 1.5, size: 52, anchor: "lm" });
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {ids.slice(0, 3).map((id, i) => {
        const p = pop(1 + i * 2);
        return <Pic key={i} id={id} box={{ x: 180 + i * 170, y: 230 + i * 30, w: 330, h: 590 }} radius={18} opacity={fade(0.75 + i * 2, 0.4)}
          style={{ transform: `rotate(${[-5, 3, -2][i] + 1.5 * sway(i)}deg) scale(${0.8 + 0.2 * p})`, boxShadow: "0 18px 40px rgba(0,0,0,0.55)", border: "6px solid #fff" }} />;
      })}
      {text.nodes}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 8 · a chapter: title and two photos

const Chapter: React.FC<PageProps & { n: number }> = ({ c, at, len, n }) => {
  const { D, beat, fade, out, drift } = usePage(c, at, len);
  const ids = listOf(c, `ch${n}`);
  const boxes: Box[] = [{ x: 80, y: 250, w: 860, h: 640 }, { x: 980, y: 250, w: 860, h: 640 }];
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Typed text={c.copy[`chapter_${n}`]} x={960} y={150} start={D(0.2)} step={beat / 4} beat={beat} size={50} anchor="cm" font="pen" caret="bar" color={INK} />
      {boxes.map((b, i) => {
        // each photo's fade is centred on its beat (the first on beat 1, the second on beat 2)
        const f = fade(i + 1 - 0.3, 0.6);
        return <Pic key={i} id={ids[i]} box={b} zoom={drift(1.08, 1)} opacity={f} ty={(1 - f) * 30} />;
      })}
    </AbsoluteFill>
  );
};

export const Chapter1: React.FC<PageProps> = (p) => <Chapter {...p} n={1} />;
export const Chapter2: React.FC<PageProps> = (p) => <Chapter {...p} n={2} />;
export const Chapter3: React.FC<PageProps> = (p) => <Chapter {...p} n={3} />;
export const Chapter4: React.FC<PageProps> = (p) => <Chapter {...p} n={4} />;

// ---------------------------------------------------------------- 9 · the licence: typed lines, then a photo in a camera viewfinder

export const License: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, fade, out, drift } = usePage(c, at, len);
  const half = len / 2;
  const text = typedLines(fill(c, c.copy.license), { x: 960, y: 520, gap: 92, D, from: 0.5, size: 58, until: D(half) });
  const box = { x: 280, y: 158, w: 1360, h: 765 };
  const f = fade(half - 0.25, 0.6);
  const ui = "rgba(255,255,255,0.92)";
  const corner = (x: number, y: number, sx: number, sy: number, k: number) => (
    <div key={k} style={{ position: "absolute", left: x - (sx < 0 ? 60 : 0), top: y - (sy < 0 ? 60 : 0), width: 60, height: 60,
      borderLeft: sx > 0 ? `4px solid ${ui}` : undefined, borderRight: sx < 0 ? `4px solid ${ui}` : undefined,
      borderTop: sy > 0 ? `4px solid ${ui}` : undefined, borderBottom: sy < 0 ? `4px solid ${ui}` : undefined }} />
  );
  const secs = Math.max(0, t - D(half));
  const tc = `00:00:${String(Math.floor(secs)).padStart(2, "0")}:${String(Math.floor((secs % 1) * 30)).padStart(2, "0")}`;
  const rec = Math.floor((t - D(0)) / (D(1) - D(0))) % 2 === 0;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {text.nodes}
      <AbsoluteFill style={{ opacity: f }}>
        <Pic id={listOf(c, "license")[0]} box={box} zoom={drift(1.12, 1, half, len)} />
        {corner(box.x + 30, box.y + 30, 1, 1, 0)}
        {corner(box.x + box.w - 30, box.y + 30, -1, 1, 1)}
        {corner(box.x + 30, box.y + box.h - 30, 1, -1, 2)}
        {corner(box.x + box.w - 30, box.y + box.h - 30, -1, -1, 3)}
        <div style={{ position: "absolute", left: box.x + box.w - 170, top: box.y + 52, width: 18, height: 18, borderRadius: "50%", background: rec ? "#FF3B30" : "transparent" }} />
        <Text font="mono" size={26} tracking={3} color={ui} x={box.x + box.w - 140} y={box.y + 61} anchor="lm">REC</Text>
        <Text font="mono" size={24} tracking={2} color={ui} x={box.x + 60} y={box.y + 61} anchor="lm">{tc}</Text>
        <Text font="mono" size={24} tracking={2} color={ui} x={box.x + 60} y={box.y + box.h - 61} anchor="lm">4K 60FPS</Text>
        <Text font="mono" size={24} tracking={2} color={ui} x={box.x + box.w - 60} y={box.y + box.h - 61} anchor="rm">HD</Text>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 10 · what love is: a photo, typed lines, a subtitle

const Love: React.FC<PageProps & { n: number }> = ({ c, at, len, n }) => {
  const { D, fade, out, drift } = usePage(c, at, len);
  const ids = listOf(c, `love${n}`);
  const half = len / 2;
  const box = { x: 160, y: 140, w: 720, h: 800 };
  const text = typedLines(c.copy[`love_${n}`] ?? "", { x: 1060, y: 470, gap: 84, D, from: 1, size: 54, anchor: "lm" });
  const sub = typedLines(c.copy[`love_sub_${n}`] ?? "", { x: 1340, y: 990, gap: 44, D, from: 3, size: 36, color: GREY, perChar: 0.125 });
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Pic id={ids[0]} box={box} zoom={drift(1.1, 1, 0, half + 1)} opacity={fade(-0.4, 0.8)} />
      {ids[1] ? <Pic id={ids[1]} box={box} zoom={drift(1.1, 1, half, len)} opacity={fade(half - 0.25, 0.5)} /> : null}
      {text.nodes}
      {sub.nodes}
    </AbsoluteFill>
  );
};

export const Love1: React.FC<PageProps> = (p) => <Love {...p} n={1} />;
export const Love2: React.FC<PageProps> = (p) => <Love {...p} n={2} />;
export const Love3: React.FC<PageProps> = (p) => <Love {...p} n={3} />;
export const Love4: React.FC<PageProps> = (p) => <Love {...p} n={4} />;

// ---------------------------------------------------------------- 11 · the letter

export const Letter: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, out } = usePage(c, at, len);
  const ls = lines(c.copy.letter);
  const text = typedLines(c.copy.letter, { x: 960, y: 540, gap: Math.min(84, 820 / Math.max(1, ls.length)), D, from: 0.5, size: 46 });
  // the letter rises slowly as it is written, like a page scrolled while reading
  const rise = lerp(60, -60, ramp(t, D(0), D(len)));
  return <AbsoluteFill style={{ opacity: out, transform: `translateY(${rise}px)` }}>{text.nodes}</AbsoluteFill>;
};
