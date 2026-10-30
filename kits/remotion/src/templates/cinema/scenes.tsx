import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Text } from "../../components/Text";
import { coverFit } from "../../core/crop";
import { eOut3, eSine, lerp, ramp } from "../../core/ease";
import { getPhoto, photoSrc } from "../../core/manifest";
import { useT } from "../../core/time";
import { DriftLights, Typed } from "../../core/typing";

/**
 * Cinema pages: a wedding opening film for the venue screen, on black. Titles are typed with a block
 * caret; photos fade in panel by panel, slide in from the sides or open out of a drawn line; the story
 * runs from two childhood portraits to the wedding and ends on a line drawing of the couple. All times
 * are beats from the page's first beat; D(n) = seconds of beat `at + n`.
 */

export const INK = "#F4F1EC";
const GREY = "rgba(244,241,236,0.72)";

export type Ctx = {
  B: (n: number) => number;
  ph: Record<string, string | string[]>;
  copy: Record<string, string>;
  groom: string;
  bride: string;
  /** dates as "2026年05月20日" */
  date: string;
  since: string;
  groomBorn: string;
  brideBorn: string;
  days: number;
};

export type PageProps = { c: Ctx; at: number; len: number };

export const lines = (s: string) => s.split(/[｜|]/).map((x) => x.trim()).filter(Boolean);

const pick = (c: Ctx, slot: string, i = 0) => {
  const v = c.ph[slot];
  return Array.isArray(v) ? v[i % v.length] : v;
};

type Box = { x: number; y: number; w: number; h: number };

/** A photo in a box, cropped around the faces, with a slow zoom so it never freezes. */
const Pic: React.FC<{ id: string; box: Box; zoom?: number; tx?: number; opacity?: number; radius?: number; clip?: string }> = ({
  id, box, zoom = 1, tx = 0, opacity = 1, radius = 0, clip,
}) => {
  if (!id || opacity <= 0.002) return null;
  const photo = getPhoto(id);
  const fit = coverFit(photo, box.w, box.h);
  return (
    <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, overflow: "hidden", opacity, borderRadius: radius,
      transform: tx ? `translateX(${tx}px)` : undefined, clipPath: clip }}>
      <Img src={photoSrc(photo)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: fit.objectPosition,
        transformOrigin: fit.transformOrigin, transform: `scale(${zoom})` }} />
    </div>
  );
};

/**
 * A slide changes the picture most a little after it starts, so slides start this share of a beat
 * early to put that peak on the beat.
 */
const LEAD = 0.42;

/** Page clock: D(n), a fade over `beats` from beat n, a slide peaking on beat n, a zoom across the page, the fade-out. */
const usePage = (c: Ctx, at: number, len: number) => {
  const t = useT();
  const D = (n: number) => c.B(at + n);
  const beat = D(1) - D(0);
  const fade = (n: number, beats = 1) => eSine(ramp(t, D(n), D(n + beats)));
  const slide = (n: number, beats = 1.4) => eOut3(ramp(t, D(n - LEAD), D(n - LEAD + beats)));
  // the fade-out is centred on the page's last beat but one, so its biggest change lands on a beat
  const out = 1 - eSine(ramp(t, D(len - 1.4), D(len - 0.6)));
  const drift = (z0 = 1.1, z1 = 1, from = 0, to = len) => lerp(z0, z1, ramp(t, D(from), D(to)));
  return { t, D, beat, fade, slide, out, drift };
};

// ---------------------------------------------------------------- typing

/** Several lines typed one after another, each starting a beat after the previous one ends. */
const TypedLines: React.FC<{ text: string; x: number; y: number; gap: number; D: (n: number) => number; from: number; size: number; perChar?: number;
  anchor?: "lm" | "cm"; color?: string; tracking?: number }> = ({ text, x, y, gap, D, from, size, perChar = 0.5, anchor = "cm", color, tracking }) => {
  const ls = lines(text);
  let n = from;
  return (
    <>
      {ls.map((l, i) => {
        const start = n;
        n += Math.ceil([...l].length * perChar) + 1;
        return <Typed key={i} text={l} x={x} y={y + (i - (ls.length - 1) / 2) * gap} start={D(start)} step={(D(1) - D(0)) * perChar} beat={D(1) - D(0)}
          size={size} anchor={anchor} color={color} tracking={tracking} caretUntil={i < ls.length - 1 ? D(n - 0.5) : Infinity} />;
      })}
    </>
  );
};

// ---------------------------------------------------------------- ambient light

/** Soft drifting lights behind every page, so a page of typed text alone never freezes. */
export const Ambient: React.FC = () => <DriftLights />;

// ---------------------------------------------------------------- 1 · welcome, typed over a dusk sky

export const Welcome: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, beat, fade, out, drift } = usePage(c, at, len);
  const one = c.copy.welcome_1;
  // the second line replaces the first on the bar after the first is typed and has stood a moment
  const swap = Math.ceil((1 + [...one].length / 2 + 2) / 4) * 4;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <AbsoluteFill style={{ opacity: fade(-0.5, 1.5) }}>
        <Img src={staticFile("assets/cinema/sky.jpg")} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${drift(1.0, 1.12)})` }} />
        <AbsoluteFill style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0) 45%, rgba(0,0,0,0.5) 100%)" }} />
      </AbsoluteFill>
      <Typed text={one} x={440} y={610} start={D(1)} step={beat / 2} beat={beat} size={68} until={D(swap)} />
      <Typed text={c.copy.welcome_2} x={440} y={610} start={D(swap)} step={beat / 2} beat={beat} size={68} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 2 · two childhood portraits

export const Born: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, beat, fade, out, drift } = usePage(c, at, len);
  const size = { w: 500, h: 520 };
  const people = [
    { cx: 660, id: pick(c, "kidGroom"), label: `${c.copy.groom_label}  ${c.groom}`, born: `${c.copy.born_prefix} ${c.groomBorn}` },
    { cx: 1260, id: pick(c, "kidBride"), label: `${c.copy.bride_label}  ${c.bride}`, born: `${c.copy.born_prefix} ${c.brideBorn}` },
  ];
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {people.map((p, i) => {
        const f = fade(i * 0.5 - 0.3, 1.2);
        return (
          <React.Fragment key={i}>
            <Pic id={p.id} box={{ x: p.cx - size.w / 2, y: 150 + (1 - f) * 24, w: size.w, h: size.h }} radius={38} zoom={drift(1.1, 1)} opacity={f} />
            <Typed text={p.label} x={p.cx} y={746} start={D(2 + i * 2)} step={beat / 4} beat={beat} size={34} anchor="cm" color={GREY} caretUntil={D(3.5 + i * 2)} />
            <Typed text={p.born} x={p.cx} y={804} start={D(3 + i * 2)} step={beat / 4} beat={beat} size={34} anchor="cm" color={GREY} caretUntil={i === 1 ? Infinity : D(4)} />
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 3 · four childhood photos slide into a row

export const Growing: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, beat, fade, slide, out, drift } = usePage(c, at, len);
  const w = 380;
  const gap = 44;
  const x0 = 960 - (4 * w + 3 * gap) / 2;
  const [l1 = "", l2 = ""] = lines(c.copy.grow_lines);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {[0, 1, 2, 3].map((i) => {
        // each pair comes in from its own side: the inner photo leads (it travels furthest) and the
        // outer one follows a beat behind, so they never cross
        const fromLeft = i < 2;
        const s = slide([1, 0, 0, 1][i] + (fromLeft ? 0 : 0.5), 1.6);
        const x = x0 + i * (w + gap);
        const off = fromLeft ? -(x + w + 40) : 1920 - x + 40;
        return <Pic key={i} id={pick(c, "childhood", i)} box={{ x, y: 350, w, h: 380 }} radius={30} tx={off * (1 - s)} zoom={drift(1.08, 1)} />;
      })}
      <Text font="songti" size={44} tracking={10} color={INK} x={960} y={250} anchor="cm" opacity={fade(2, 1)}>{c.copy.grow_title}</Text>
      <Typed text={l1} x={960} y={826} start={D(3)} step={beat / 4} beat={beat} size={34} anchor="cm" color={GREY} caretUntil={D(3 + [...l1].length / 4 + 0.5)} />
      <Typed text={l2} x={960} y={882} start={D(3.5 + [...l1].length / 4)} step={beat / 4} beat={beat} size={34} anchor="cm" color={GREY} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 4 · the day they met: a line, a date, a sentence, then a photo opens out of the line

export const Met: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, beat, fade, out, drift } = usePage(c, at, len);
  const draw = eOut3(ramp(t, D(-0.1), D(1.4)));
  // the photo opens from the line on beat `open`: a slit that grows to the full frame
  const open = 6;
  const slit = eOut3(ramp(t, D(open - 0.05), D(open + 1.4)));
  const q = `${((1 - slit) * 50).toFixed(3)}%`;
  const textOut = 1 - fade(open - 0.6, 0.6);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{ position: "absolute", left: 1920 * (1 - draw), top: 539, width: 1920 * draw, height: 2, background: "rgba(244,241,236,0.8)", opacity: textOut }} />
      <AbsoluteFill style={{ opacity: textOut }}>
        <Typed text={c.since} x={960} y={490} start={D(1.5)} step={beat / 4} beat={beat} size={36} anchor="cm" tracking={6} caretUntil={D(3)} />
        <Typed text={c.copy.met_line} x={960} y={600} start={D(3)} step={beat / 4} beat={beat} size={30} anchor="cm" color={GREY} />
      </AbsoluteFill>
      {slit > 0 ? <Pic id={pick(c, "first")} box={{ x: 0, y: 0, w: 1920, h: 1080 }} zoom={drift(1.14, 1, open, len)} clip={`inset(${q} 0 ${q} 0)`} /> : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 5 · the day counter

export const Counter: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, fade, out } = usePage(c, at, len);
  const n = Math.round(c.days * eOut3(ramp(t, D(0.5), D(4))));
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Text font="songti" size={32} tracking={10} color={GREY} x={960} y={450} anchor="cm" opacity={fade(-0.3, 0.8)}>{c.copy.counter_head}</Text>
      <Text font="songti" size={96} tracking={10} color={INK} x={960} y={570} anchor="cm" opacity={fade(0.2, 0.6)}>{`${n}${c.copy.counter_unit}`}</Text>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 6 · full-height panels, one per beat, then a second set

const Panels: React.FC<PageProps & { slot: string; from: number; count: number; gap?: number; second?: boolean }> = ({ c, at, len, slot, from, gap = 0, second }) => {
  const { fade, out, drift } = usePage(c, at, len);
  const half = second ? len / 2 : len;
  const w = (1920 - 2 * gap) / 3;
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {[0, 1, 2].map((i) => {
        const box = { x: i * (w + gap), y: 0, w, h: 1080 };
        return (
          <React.Fragment key={i}>
            <Pic id={pick(c, slot, from + i)} box={box} zoom={drift(1.1, 1, 0, half + 1)} opacity={fade(i - 0.25, 0.5)} />
            {second ? <Pic id={pick(c, slot, from + 3 + i)} box={box} zoom={drift(1.1, 1, half, len)} opacity={fade(half + i - 0.25, 0.5)} /> : null}
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

export const Dating: React.FC<PageProps> = (p) => <Panels {...p} slot="dating" from={0} count={6} second />;
export const Dating2: React.FC<PageProps> = (p) => <Panels {...p} slot="dating2" from={0} count={3} />;
export const Trio: React.FC<PageProps> = (p) => <Panels {...p} slot="trio" from={0} count={3} gap={24} />;

// ---------------------------------------------------------------- 7 · a typed sentence on black

const Sentence: React.FC<PageProps & { copy: string; size?: number }> = ({ c, at, len, copy, size = 44 }) => {
  const { D, out } = usePage(c, at, len);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <TypedLines text={c.copy[copy] ?? ""} x={960} y={540} gap={size * 1.9} D={D} from={0.5} size={size} tracking={8} />
    </AbsoluteFill>
  );
};

export const Hearts: React.FC<PageProps> = (p) => <Sentence {...p} copy="hearts" />;
export const Today: React.FC<PageProps> = (p) => <Sentence {...p} copy="today" />;
export const Quote: React.FC<PageProps> = (p) => <Sentence {...p} copy="quote" size={40} />;

// ---------------------------------------------------------------- 8 · one photo, full frame

const Full: React.FC<PageProps & { slot: string }> = ({ c, at, len, slot }) => {
  const { fade, out, drift } = usePage(c, at, len);
  return (
    <AbsoluteFill style={{ opacity: out * fade(-0.4, 1) }}>
      <Pic id={pick(c, slot)} box={{ x: 0, y: 0, w: 1920, h: 1080 }} zoom={drift(1.12, 1)} />
    </AbsoluteFill>
  );
};

export const Wedding: React.FC<PageProps> = (p) => <Full {...p} slot="wedding" />;
export const Closing: React.FC<PageProps> = (p) => <Full {...p} slot="closing" />;

// ---------------------------------------------------------------- 9 · two photos side by side, then a second pair

export const Pairs: React.FC<PageProps> = ({ c, at, len }) => {
  const { slide, fade, out, drift } = usePage(c, at, len);
  const half = len / 2;
  const boxes: Box[] = [{ x: 60, y: 40, w: 880, h: 1000 }, { x: 980, y: 40, w: 880, h: 1000 }];
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {boxes.map((b, i) => {
        // the first pair slides in from its own side; the second dissolves over it
        const s = slide(i, 1.4);
        const off = i === 0 ? -(b.x + b.w) : 1920 - b.x;
        return (
          <React.Fragment key={i}>
            <Pic id={pick(c, "pairs", i)} box={b} tx={off * (1 - s)} zoom={drift(1.1, 1, 0, half + 1)} />
            <Pic id={pick(c, "pairs", 2 + i)} box={b} zoom={drift(1.1, 1, half, len)} opacity={fade(half + i - 0.5, 1)} />
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 10 · line drawing of the couple and thanks

const ART = { src: "assets/cinema/couple-line.png", w: 894, h: 1000 };

export const Ending: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, beat, fade } = usePage(c, at, len);
  // the drawing appears from the top down as if drawn, with a soft edge
  const draw = eSine(ramp(t, D(0), D(3)));
  const mask = `linear-gradient(to bottom, #000 ${draw * 120 - 20}%, transparent ${draw * 120}%)`;
  const h = 640;
  const [l1 = "", l2 = ""] = lines(c.copy.thanks);
  return (
    <AbsoluteFill>
      <Img src={staticFile(ART.src)} style={{ position: "absolute", left: 300, top: 540 - h / 2, height: h, width: (h * ART.w) / ART.h,
        WebkitMaskImage: mask, maskImage: mask, opacity: 0.95 }} />
      <Typed text={l1} x={900} y={480} start={D(2.5)} step={beat / 4} beat={beat} size={44} tracking={8} caretUntil={D(2.5 + [...l1].length / 4 + 0.5)} />
      <Typed text={l2} x={900} y={560} start={D(3 + [...l1].length / 4)} step={beat / 4} beat={beat} size={44} tracking={8} />
      <Text font="songti" size={28} tracking={8} color={GREY} x={900} y={680} anchor="lm" opacity={fade(7, 1.2)}>{`${c.groom}  &  ${c.bride}  ·  ${c.date}`}</Text>
    </AbsoluteFill>
  );
};
