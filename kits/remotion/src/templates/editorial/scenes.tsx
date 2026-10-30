import React, { type CSSProperties } from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Text } from "../../components/Text";
import { fontFor } from "../../core/fonts";
import { coverFit } from "../../core/crop";
import { eBack, eIo3, eOut3, eSine, lerp, ramp } from "../../core/ease";
import { getPhoto, photoSrc } from "../../core/manifest";
import { useT } from "../../core/time";

/**
 * Editorial pages. Every page is a white magazine spread laid out in 1920×1080 design px; all its
 * times are beats from the page's first beat (D(n) = seconds of beat `at + n`).
 *
 * The motion language follows the reference film: photos are mostly revealed in place from one edge
 * (the picture does not move, its frame opens), some slide in or grow from a point; text fades in
 * character by character; titles fade up from a slight blur; a photo set changes by a double-exposure
 * dissolve; and every page leaves through a cloud of translucent white bubbles that sweeps left to
 * right and dissolves it into the paper.
 */

export const PAPER = "#FFFFFF";
export const INK = "#3B3536";
export const GREY = "#7F7778";
export const ACCENT = "#A8263B";
export const ROSE = "#C97A86";

export type Ctx = {
  B: (n: number) => number;
  /** page length multiplier; drifts grow with it so a longer hold moves at the same speed */
  pace: number;
  ph: Record<string, string | string[]>;
  copy: Record<string, string>;
  groom: string;
  bride: string;
  date: string;
  tagline: string;
};

export type PageProps = { c: Ctx; at: number; len: number };

/** "a｜b|c" → ["a", "b", "c"]; an empty part is a paragraph gap. */
export const lines = (s: string) => s.split(/[｜|]/).map((x) => x.trim());

const pick = (c: Ctx, slot: string, i = 0) => {
  const v = c.ph[slot];
  return Array.isArray(v) ? v[i % v.length] : v;
};

type Box = { x: number; y: number; w: number; h: number };
type Edge = "left" | "right" | "top" | "bottom";

/** Clip that opens a frame from one edge; the picture inside stays where it is. */
const opening = (p: number, from: Edge) => {
  const q = `${((1 - Math.min(1, Math.max(0, p))) * 100).toFixed(3)}%`;
  return { left: `inset(0 ${q} 0 0)`, right: `inset(0 0 0 ${q})`, top: `inset(0 0 ${q} 0)`, bottom: `inset(${q} 0 0 0)` }[from];
};

/** A photo in a box, cropped around the faces, with a slow zoom so it never freezes. */
const Pic: React.FC<{ id: string; box: Box; zoom?: number; tx?: number; ty?: number; scale?: number; opacity?: number; reveal?: [number, Edge]; style?: CSSProperties }> = ({
  id, box, zoom = 1, tx = 0, ty = 0, scale = 1, opacity = 1, reveal, style,
}) => {
  if (opacity <= 0.002 || scale <= 0.002 || (reveal && reveal[0] <= 0)) return null;
  const photo = getPhoto(id);
  const fit = coverFit(photo, box.w, box.h);
  return (
    <div style={{ position: "absolute", left: box.x, top: box.y, width: box.w, height: box.h, overflow: "hidden", opacity,
      transform: `translate(${tx}px, ${ty}px) scale(${scale})`, clipPath: reveal ? opening(...reveal) : undefined, ...style }}>
      <Img src={photoSrc(photo)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: fit.objectPosition,
        transformOrigin: fit.transformOrigin, transform: `scale(${zoom})` }} />
    </div>
  );
};

/** Line-art decoration generated for this template (public/assets/editorial). */
const ART = {
  rings: { src: "assets/editorial/rings.png", w: 288, h: 240 },
  couple: { src: "assets/editorial/couple.png", w: 291, h: 480 },
  flourish: { src: "assets/editorial/flourish.png", w: 357, h: 240 },
  titleCover: { src: "assets/editorial/title-cover.png", w: 1188, h: 800 },
  titleRomance: { src: "assets/editorial/title-romance.png", w: 897, h: 1100 },
} as const;

/**
 * The two handwritten titles are lettered artwork for the default copy. Changed copy is set in the
 * packaged pen font instead, since the artwork cannot spell other words.
 */
const LETTERED = { titleCover: "我们的婚礼", titleRomance: "永远的浪漫主义者" } as const;
const lettered = (name: keyof typeof LETTERED, copy: string) => copy.replace(/[｜|\s]/g, "") === LETTERED[name];

const Art: React.FC<{ name: keyof typeof ART; x: number; y: number; height: number; opacity: number; style?: CSSProperties }> = ({ name, x, y, height, opacity, style }) => {
  if (opacity <= 0.002) return null;
  const a = ART[name];
  return <Img src={staticFile(a.src)} style={{ position: "absolute", left: x, top: y, height, width: (height * a.w) / a.h, opacity, ...style }} />;
};

/** Settle from 92% out of a slight blur, as the reference's titles do. */
const settle = (p: number): CSSProperties => ({ transform: `scale(${0.92 + 0.08 * p})`, transformOrigin: "center", filter: p < 1 ? `blur(${(1 - p) * 6}px)` : undefined });

/**
 * A sliding or opening photo changes the picture most a little after it starts (more of it is on
 * screen while it is still fast), so entrances start this share of a beat early to put that peak on
 * the beat. Pages hand over the same amount before their boundary beat.
 */
export const LEAD = 0.42;
/** Beats the bubble sweep takes. It starts fast, so its biggest change comes right as it enters. */
const BUBBLE_BEATS = 1.4;
/** The sweep starts this many beats before the page's last beat, so its peak lands on that beat. */
const BUBBLE_FROM = 1.23;
/** Beats before the page's boundary when the sweep has passed and the page is gone. */
export const BUBBLE_DONE = BUBBLE_FROM - BUBBLE_BEATS;
/** Lead for a frame opening from an edge: it changes the picture most right as it starts. */
const OPEN = 0.05;

/** Page clock: seconds now, D(n) for beat n of this page, and the eased entrance of a move peaking on beat n. */
const usePage = (c: Ctx, at: number) => {
  const t = useT();
  const D = (n: number) => c.B(at + n);
  const enter = (n: number, beats = 1.4, lead = LEAD) => eOut3(ramp(t, D(n - lead), D(n - lead + beats)));
  /** fade in over `beats` from beat n */
  const fade = (n: number, beats = 1) => eSine(ramp(t, D(n), D(n + beats)));
  /** constant zoom across [from, to] beats so a photo never freezes; a slower pace zooms further, not slower */
  const grow = c.pace ** 1.6;
  const amp = (z: number) => 1 + Math.min(0.35, (z - 1) * grow);
  const drift = (to: number, z0 = 1.06, z1 = 1.0, from = 0) => lerp(amp(z0), amp(z1), ramp(t, D(from), D(to)));
  return { t, D, enter, fade, drift };
};

// ---------------------------------------------------------------- bubble dissolve

/** Seeded bubbles: [x share of the sweep band, y share, radius px, alpha]. */
const BUBBLES: [number, number, number, number][] = (() => {
  let s = 7;
  const rnd = () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
  return Array.from({ length: 64 }, () => [rnd(), rnd() * 1.1 - 0.05, 70 + rnd() * 210, 0.38 + rnd() * 0.32] as [number, number, number, number]);
})();

/**
 * The page dissolves into the paper under translucent white bubbles. Each bubble swells as the
 * sweep reaches it; overlapping bubbles add up to white, and the paper closes in behind them.
 */
const BAND = 900;
/** x of the sweep's leading edge; the paper is opaque white up to `solid + BAND * 0.15`. */
const sweepFront = (p: number) => lerp(-250, 1920 + BAND, 1 - (1 - p) ** 2);

export const Bubbles: React.FC<{ from: number; to: number }> = ({ from, to }) => {
  const t = useT();
  if (t < from) return null;
  const p = ramp(t, from, to);
  const band = BAND;
  const front = sweepFront(p);
  const solid = front - band;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {BUBBLES.map(([u, v, r, a], i) => {
        const cx = solid + u * band;
        const grow = eOut3(ramp(front - cx, 0, 420));
        if (grow <= 0) return null;
        const R = r * (0.25 + 0.75 * grow);
        return (
          <div key={i} style={{ position: "absolute", left: cx - R, top: v * 1080 - R, width: R * 2, height: R * 2, borderRadius: "50%",
            background: `radial-gradient(circle, rgba(255,255,255,${a}) 0%, rgba(255,255,255,${a}) 62%, rgba(255,255,255,${a * 0.75}) 68%, rgba(255,255,255,0) 71%)`,
            boxShadow: `inset 0 0 ${R * 0.25}px rgba(255,255,255,${a * 0.6})` }} />
        );
      })}
      <AbsoluteFill style={{ background: `linear-gradient(to right, ${PAPER} ${solid + band * 0.15}px, rgba(255,255,255,0) ${solid + band * 0.55}px)` }} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- text

type AnchorKey = "lt" | "ct" | "rt" | "lm" | "cm" | "rm" | "lb" | "cb" | "rb";

/** One line whose characters fade in one after another, as if typed. */
const Line: React.FC<{ text: string; x: number; y: number; at: number; size?: number; font?: "songti" | "serif" | "loraItalic" | "display";
  color?: string; anchor?: AnchorKey; step?: number; tracking?: number; maxWidth?: number; weight?: number; shadow?: boolean }> = ({
  text, x, y, at, size = 32, font = "songti", color = INK, anchor = "ct", step = 0.06, tracking = 3, maxWidth, weight = 400, shadow,
}) => (text ? <Text font={font} size={size} weight={weight} color={color} tracking={tracking} x={x} y={y} anchor={anchor} maxWidth={maxWidth} shadow={shadow}
  reveal={{ start: at, step, dur: 0.45, dist: 0, blur: 3 }}>{text}</Text> : null);

/** Stacked lines typed one after another; empty lines leave a paragraph gap. */
const Stanza: React.FC<{ text: string; x: number; y: number; gap: number; D: (n: number) => number; from: number; every?: number; size?: number;
  color?: string; anchor?: "lt" | "ct" | "rt"; maxWidth?: number; shadow?: boolean; font?: "songti" | "loraItalic" | "serif"; tracking?: number; weight?: number }> = ({
  text, x, y, gap, D, from, every = 1, size = 32, color = INK, anchor = "ct", maxWidth, shadow, font = "songti", tracking = 3, weight,
}) => {
  let row = 0;
  let k = 0;
  return (
    <>
      {lines(text).map((l, i) => {
        if (!l) { row += 0.7; return null; }
        const el = <Line key={i} text={l} x={x} y={y + row * gap} at={D(from + k * every)} size={size} color={color} anchor={anchor} maxWidth={maxWidth}
          shadow={shadow} font={font} tracking={tracking} weight={weight} />;
        row += 1;
        k += 1;
        return el;
      })}
    </>
  );
};

/** Handwritten title that fades up from a slight blur and settles from 92%. */
const Pen: React.FC<{ text: string; x: number; y: number; size: number; p: number; color?: string; rotate?: number }> = ({ text, x, y, size, p, color = ACCENT, rotate = 0 }) =>
  p <= 0.002 ? null : (
    <div style={{ position: "absolute", left: x, top: y, transform: `rotate(${rotate}deg) scale(${0.92 + 0.08 * p})`, transformOrigin: "left center",
      opacity: p, filter: p < 1 ? `blur(${(1 - p) * 6}px)` : undefined }}>
      <Text font="pen" size={size} color={color} lineHeight={1}>{text}</Text>
    </div>
  );

/**
 * A page on white paper. While its bubbles sweep out, everything left of the opaque paper edge is
 * cut away, so the next page (rendered underneath) can already build there.
 */
const Frame: React.FC<{ c: Ctx; at: number; len: number; children: React.ReactNode }> = ({ c, at, len, children }) => {
  const t = useT();
  const from = c.B(at + len - BUBBLE_FROM);
  const to = c.B(at + len - BUBBLE_DONE);
  const edge = len > 0 && t > from ? sweepFront(ramp(t, from, to)) - BAND * 0.85 : 0;
  return (
    <AbsoluteFill style={{ background: PAPER, clipPath: edge > 0 ? `inset(0 0 0 ${edge}px)` : undefined }}>
      {children}
      {len > 0 ? <Bubbles from={from} to={to} /> : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- page layouts
// Boxes and text positions are measured from the reference film's settled frames (1920×1080).

// ---------------------------------------------------------------- 1 · cover

const COVER_FADE = "linear-gradient(to right, #000 0%, #000 74%, rgba(0,0,0,0.55) 86%, rgba(0,0,0,0) 100%)";

export const Cover: React.FC<PageProps> = ({ c, at, len }) => {
  const { enter, fade, drift } = usePage(c, at);
  const box = { x: 0, y: 0, w: 1044, h: 1080 };
  const [l1 = "", l2 = ""] = lines(c.copy.cover_title);
  const en = c.copy.cover_en.split(" ").filter(Boolean);
  const title = fade(0.6, 1.2);
  const small = { font: "serif" as const, size: 22, tracking: 3, color: GREY };
  // WELCOME above the first line, TO under its end, OUR under its start, WEDDING before the second line
  const spots: [number, number, AnchorKey][] = [[1236, 282, "lm"], [1450, 490, "lm"], [1044, 520, "lm"], [1098, 616, "lm"]];
  const words = en.length > 4 ? [en.slice(0, -3).join(" "), ...en.slice(-3)] : en;
  return (
    <Frame c={c} at={at} len={len}>
      {/* the photo's right side melts into the paper instead of ending on a hard edge */}
      <Pic id={pick(c, "cover")} box={box} zoom={drift(len, 1.1, 1.0)} tx={-box.w * (1 - enter(0, 1.2))}
        style={{ WebkitMaskImage: COVER_FADE, maskImage: COVER_FADE }} />
      {lettered("titleCover", c.copy.cover_title) ? (
        <Art name="titleCover" x={1000} y={240} height={520} opacity={title} style={settle(title)} />
      ) : (
        <>
          <Pen text={l1} x={1010} y={250} size={200} p={title} />
          <Pen text={l2} x={1210} y={520} size={200} p={title} />
        </>
      )}
      {words.map((w, i) => (
        <Text key={i} {...small} x={spots[i][0]} y={spots[i][1]} anchor={spots[i][2]} opacity={title}>{w}</Text>
      ))}
      <Text font="songti" size={26} tracking={2} color={ACCENT} x={1868} y={44} anchor="rt" opacity={fade(1, 1)}>{`【${c.tagline}】`}</Text>
      <Text font="songti" size={26} tracking={6} color={INK} x={1745} y={942} anchor="rm" opacity={fade(1.6, 1)}>{`新郎：${c.groom}`}</Text>
      <Text font="songti" size={26} tracking={6} color={INK} x={1745} y={988} anchor="rm" opacity={fade(1.6, 1)}>{`新娘：${c.bride}`}</Text>
      <div style={{ position: "absolute", left: 1764, top: 922, width: 2, height: 86 * fade(1.8, 1), background: INK }} />
      <Art name="rings" x={1778} y={935} height={64} opacity={fade(2.4, 1)} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 2 · invitation with two round portraits

const arcPath = (cx: number, cy: number, r: number, a0: number, a1: number) => {
  const p = (a: number) => `${cx + r * Math.cos((a * Math.PI) / 180)} ${cy + r * Math.sin((a * Math.PI) / 180)}`;
  return `M ${p(a0)} A ${r} ${r} 0 0 1 ${p(a1)}`;
};

export const Invite: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, enter, fade, drift } = usePage(c, at);
  const R = 312;
  const circles = [
    { cx: 488, cy: 500, id: pick(c, "invite", 0), label: "GROOM", name: c.groom, say: c.copy.invite_ask, arc: [195, 262] as const },
    { cx: 1430, cy: 500, id: pick(c, "invite", 1), label: "BRIDE", name: c.bride, say: c.copy.invite_yes, arc: [290, 330] as const },
  ];
  const grow = enter(0, 1.6);
  const draw = eIo3(ramp(t, D(1), D(2.6)));
  const bx = 945;
  const by = 905;
  return (
    <Frame c={c} at={at} len={len}>
      <Text font="serif" size={24} tracking={64} color={GREY} x={960} y={68} anchor="cm" reveal={{ start: D(0.3), step: 0.05, dur: 0.4, dist: 0, blur: 3 }}>{`· ${c.copy.invite_head} ·`}</Text>
      {circles.map((k, i) => (
        <React.Fragment key={i}>
          <Pic id={k.id} box={{ x: k.cx - R, y: k.cy - R, w: R * 2, h: R * 2 }} zoom={drift(len, 1.18, 1.0)} scale={grow} style={{ borderRadius: "50%" }} />
          <svg width={1920} height={1080} style={{ position: "absolute", left: 0, top: 0 }}>
            <defs><path id={`arc-${at}-${i}`} d={arcPath(k.cx, k.cy, R + 26, k.arc[0], k.arc[1])} /></defs>
            <text fill={INK} fontSize={26} letterSpacing={1} style={{ fontFamily: fontFor("loraItalic", k.say), fontStyle: "italic" }} opacity={fade(1.6 + i * 0.5, 1)}>
              <textPath href={`#arc-${at}-${i}`}>{k.say}</textPath>
            </text>
          </svg>
          <div style={{ position: "absolute", left: 0, top: 0, width: 1920, height: 1080, clipPath: opening(draw, "left") }}>
            <Text font="serif" size={26} tracking={3} color={INK} x={k.cx - 6} y={850} anchor="rm">{`${k.label} /`}</Text>
            <Text font="songti" size={32} weight={700} tracking={3} color={INK} x={k.cx + 6} y={850} anchor="lm">{k.name}</Text>
          </div>
        </React.Fragment>
      ))}
      <svg width={1920} height={1080} style={{ position: "absolute", left: 0, top: 0 }} fill="none" stroke={ACCENT} strokeWidth={2.5} strokeLinecap="round">
        <path pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} d="M -20 832 C 300 905, 700 925, 945 905 C 1190 925, 1620 905, 1940 832" />
        <g opacity={fade(2.2, 0.8)}>
          <path d={`M ${bx} ${by} C ${bx - 60} ${by - 52}, ${bx - 74} ${by + 22}, ${bx} ${by}`} />
          <path d={`M ${bx} ${by} C ${bx + 60} ${by - 52}, ${bx + 74} ${by + 22}, ${bx} ${by}`} />
          <path d={`M ${bx} ${by} Q ${bx - 22} ${by + 70}, ${bx - 40} ${by + 160}`} />
          <path d={`M ${bx} ${by} Q ${bx + 18} ${by + 74}, ${bx + 34} ${by + 165}`} />
        </g>
      </svg>
    </Frame>
  );
};

// ---------------------------------------------------------------- 3 · photo and poem

export const Poem: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, enter, fade, drift } = usePage(c, at);
  const en = lines(c.copy.poem_en);
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "poem")} box={{ x: 0, y: 0, w: 816, h: 1080 }} zoom={drift(len, 1.06, 1.0)} reveal={[enter(0, 1.3), "left"]} />
      <Stanza text={c.copy.poem} x={1363} y={246} gap={52} D={D} from={1} every={0.6} size={28} maxWidth={900} />
      {en.map((l, i) => (
        <Text key={i} font="loraItalic" size={20} tracking={1} color={INK} x={1363} y={820 + i * 34} anchor="ct" maxWidth={900} opacity={fade(4.4 + i * 0.3, 1)}>{l}</Text>
      ))}
      <Art name="flourish" x={1680} y={800} height={52} opacity={fade(5.2, 1)} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 4 · three portraits rising

export const Trio: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, enter, fade, drift } = usePage(c, at);
  const boxes: Box[] = [
    { x: 56, y: 180, w: 536, h: 720 },
    { x: 636, y: 108, w: 648, h: 864 },
    { x: 1328, y: 184, w: 536, h: 712 },
  ];
  const [k1 = "", k2 = ""] = lines(c.copy.trio_kicker);
  return (
    <Frame c={c} at={at} len={len}>
      {boxes.map((b, i) => (
        <Pic key={i} id={pick(c, "trio", i)} box={b} zoom={drift(len, 1.06, 1.0)}
          ty={(1080 - b.y) * (1 - enter(i, 1.6, 0.25)) - 12 * ramp(t, D(2), D(len))} />
      ))}
      <Text font="serif" size={20} tracking={2} color={INK} x={58} y={124} anchor="lm" opacity={fade(2.4, 1)}>{k1}</Text>
      <Text font="serif" size={20} tracking={2} color={INK} x={58} y={150} anchor="lm" opacity={fade(2.6, 1)}>{k2}</Text>
      <Stanza text={c.copy.trio_quote} x={1864} y={918} gap={42} D={D} from={3} every={0.8} size={22} color={INK} anchor="rt" maxWidth={800} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 5 · a pair, then a second pair by double exposure

const Hearts: React.FC<{ x: number; y: number; opacity: number }> = ({ x, y, opacity }) => (
  <svg width={66} height={18} style={{ position: "absolute", left: x, top: y, opacity }} viewBox="0 0 90 24" fill={INK}>
    {[0, 28, 56].map((dx) => <path key={dx} transform={`translate(${dx + 2} 3) scale(0.19)`} d="M50 88 C20 65 0 45 0 25 C0 10 12 0 26 0 C38 0 46 8 50 16 C54 8 62 0 74 0 C88 0 100 10 100 25 C100 45 80 65 50 88 Z" />)}
  </svg>
);

export const Pair: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, enter, fade, drift } = usePage(c, at);
  const L = { x: 48, y: 108, w: 648, h: 864 };
  const Rb = { x: 716, y: 104, w: 1156, h: 872 };
  const half = len / 2;
  // both frames open from bright edges (veil, sky), so the change peaks later than a plain opening
  const open = enter(0, 1.5, 0.4);
  const swap = fade(half - 0.5, 1);
  const quote = (text: string, n: number, out: number) => (
    <Text font="loraItalic" size={24} tracking={2} color={INK} x={1848} y={66} anchor="rm" maxWidth={1100}
      reveal={{ start: D(n), step: 0.06, dur: 0.45, dist: 0, blur: 3 }} opacity={out}>{text}</Text>
  );
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "pair", 0)} box={L} zoom={drift(half + 1, 1.06, 1.0)} reveal={[open, "left"]} />
      <Pic id={pick(c, "pair", 1)} box={Rb} zoom={drift(half + 1, 1.06, 1.0)} reveal={[open, "left"]} />
      <Pic id={pick(c, "pair", 2)} box={L} zoom={drift(len, 1.06, 1.0, half - 0.5)} opacity={swap} />
      <Pic id={pick(c, "pair", 3)} box={Rb} zoom={drift(len, 1.06, 1.0, half - 0.5)} opacity={swap} />
      {quote(c.copy.pair_quote_a, 1.6, 1 - swap)}
      {swap > 0 ? quote(c.copy.pair_quote_b, half + 0.6, 1) : null}
      <Hearts x={58} y={1003} opacity={fade(1.8, 0.6)} />
      <Line text={c.copy.pair_tag} x={136} y={1012} at={D(2)} size={24} tracking={4} font="loraItalic" anchor="lm" />
    </Frame>
  );
};

// ---------------------------------------------------------------- 6 · two portraits around centered lines

export const Thanks: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, enter, fade, drift } = usePage(c, at);
  const L = { x: 60, y: 76, w: 696, h: 928 };
  const R = { x: 1164, y: 76, w: 696, h: 928 };
  const open = enter(0, 1.2, OPEN);
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "thanks", 0)} box={L} zoom={drift(len, 1.06, 1.0)} reveal={[open, "top"]} />
      <Pic id={pick(c, "thanks", 1)} box={R} zoom={drift(len, 1.0, 1.06)} reveal={[open, "bottom"]} />
      <Stanza text={c.copy.thanks} x={960} y={276} gap={76} D={D} from={1.4} every={0.8} size={30} weight={700} maxWidth={380} />
      <Art name="couple" x={960 - 36} y={770} height={120} opacity={fade(5, 1)} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 7 · pair with a typed caption

export const Caption: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, enter, drift } = usePage(c, at);
  const L = { x: 64, y: 76, w: 636, h: 844 };
  const R = { x: 736, y: 76, w: 1120, h: 844 };
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "caption", 0)} box={L} zoom={drift(len, 1.06, 1.0)} reveal={[enter(0, 1.2, OPEN), "left"]} />
      <Pic id={pick(c, "caption", 1)} box={R} zoom={drift(len, 1.06, 1.0)} reveal={[enter(1, 1.2, OPEN), "left"]} />
      <Text font="songti" size={28} weight={700} tracking={3} color={INK} x={960} y={976} anchor="cm" maxWidth={1500}
        reveal={{ start: D(1.6), step: 0.11, dur: 0.35, dist: 0, blur: 2 }}>{c.copy.caption}</Text>
    </Frame>
  );
};

// ---------------------------------------------------------------- 8 · full-bleed photo opening from a heart

const HEART = encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 90"><path d="M50 88 C20 65 0 45 0 25 C0 10 12 0 26 0 C38 0 46 8 50 16 C54 8 62 0 74 0 C88 0 100 10 100 25 C100 45 80 65 50 88 Z"/></svg>',
);

export const Heart: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, enter, fade, drift } = usePage(c, at);
  const g = enter(0, 2.4, 0.6);
  const size = lerp(110, 4600, g * g);
  // the small heart appears near the top and drops to the middle as it grows
  const cy = lerp(4, 46, Math.min(1, g * 1.6));
  const mask = g < 1 ? `url("data:image/svg+xml,${HEART}") 50% ${cy}% / ${size}px ${size * 0.9}px no-repeat` : undefined;
  return (
    <Frame c={c} at={at} len={len}>
      {g > 0 ? (
        <AbsoluteFill style={{ WebkitMask: mask, mask }}>
          <Pic id={pick(c, "heart")} box={{ x: 0, y: 0, w: 1920, h: 1080 }} zoom={drift(len, 1.1, 1.0)} />
          <AbsoluteFill style={{ opacity: fade(1.6, 1), background: "linear-gradient(to top, rgba(20,12,14,0.45) 0%, rgba(20,12,14,0) 32%), linear-gradient(to bottom, rgba(20,12,14,0.25) 0%, rgba(20,12,14,0) 16%)" }} />
        </AbsoluteFill>
      ) : null}
      <Stanza text={c.copy.heart_lines} x={46} y={906} gap={52} D={D} from={2} every={0.7} size={26} color="#FFFFFF" anchor="lt" maxWidth={1100} shadow tracking={2} />
      <Stanza text={c.copy.heart_en} x={1880} y={30} gap={34} D={D} from={2.4} every={0.5} size={20} color="#FFFFFF" anchor="rt" maxWidth={900} shadow font="loraItalic" tracking={1} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 9 · wide + tall with a 囍

export const Xi: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, enter, drift } = usePage(c, at);
  const A = { x: 52, y: 60, w: 1156, h: 648 };
  const Bx = { x: 1236, y: 0, w: 684, h: 1080 };
  const pop = eBack(ramp(t, D(1.6), D(2.4)), 1.8);
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "xi", 0)} box={A} zoom={drift(len, 1.06, 1.0)} tx={-(A.x + A.w) * (1 - enter(0, 1.3))} />
      <Pic id={pick(c, "xi", 1)} box={Bx} zoom={drift(len, 1.0, 1.06)} tx={(1920 - Bx.x) * (1 - enter(1, 1.3))} />
      <Text font="songti" weight={700} size={112} color={ACCENT} x={154} y={850} anchor="cm" scale={Math.max(0.001, pop)} opacity={ramp(t, D(1.6), D(1.9))}>囍</Text>
      <Stanza text={c.copy.xi_lines} x={326} y={796} gap={74} D={D} from={2} every={0.8} size={24} anchor="lt" maxWidth={880} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 10 · two portraits, sideways title

export const About: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, enter, drift } = usePage(c, at);
  const A = { x: 88, y: 52, w: 728, h: 976 };
  const Bx = { x: 876, y: 52, w: 732, h: 976 };
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "about", 0)} box={A} zoom={drift(len, 1.06, 1.0)} reveal={[enter(0, 1.2, OPEN), "left"]} />
      <Pic id={pick(c, "about", 1)} box={Bx} zoom={drift(len, 1.0, 1.06)} reveal={[enter(1, 1.2, OPEN), "left"]} />
      <Text font="bodoni" weight={500} size={42} tracking={10} color={INK} x={1747} y={540} anchor="cm" sideways wipe={eSine(ramp(t, D(1.8), D(3.4)))} wipeDir="tb">{c.copy.about_title}</Text>
      <Text font="loraItalic" size={32} tracking={8} color={INK} x={1832} y={540} anchor="cm" sideways wipe={eSine(ramp(t, D(2.2), D(3.6)))} wipeDir="tb">{c.copy.about_kicker}</Text>
    </Frame>
  );
};

// ---------------------------------------------------------------- 11 · three columns growing, then a second set by double exposure

export const Columns: React.FC<PageProps> = ({ c, at, len }) => {
  const { enter, fade, drift } = usePage(c, at);
  const half = len / 2;
  const cols: Box[] = [56, 664, 1272].map((x) => ({ x, y: 52, w: 592, h: 976 }));
  // each card starts small in the middle of its column and opens to full height
  const scale = lerp(0.22, 1, enter(0, 1.8, 0.5));
  // the double exposure is centred on the beat
  const swap = fade(half - 0.6, 1.2);
  return (
    <Frame c={c} at={at} len={len}>
      {cols.map((b, i) => (
        <React.Fragment key={i}>
          <Pic id={pick(c, "triptych", i)} box={b} zoom={drift(half + 1, 1.08, 1.0)} scale={scale} />
          <Pic id={pick(c, "triptych", 3 + i)} box={b} zoom={drift(len, 1.08, 1.0, half - 0.6)} opacity={swap} />
        </React.Fragment>
      ))}
    </Frame>
  );
};

// ---------------------------------------------------------------- 12 · one tall photo and two staggered portraits

export const Collage: React.FC<PageProps> = ({ c, at, len }) => {
  const { D, enter, fade, drift } = usePage(c, at);
  const A = { x: 0, y: 0, w: 764, h: 1080 };
  const Bx = { x: 792, y: 60, w: 536, h: 832 };
  const C = { x: 1352, y: 188, w: 532, h: 832 };
  const [k1 = "", k2 = ""] = lines(c.copy.collage_kicker);
  return (
    <Frame c={c} at={at} len={len}>
      <Pic id={pick(c, "collage", 0)} box={A} zoom={drift(len, 1.06, 1.0)} reveal={[enter(0, 1.2, OPEN), "left"]} />
      <Pic id={pick(c, "collage", 1)} box={Bx} zoom={drift(len, 1.0, 1.06)} reveal={[enter(1, 1.2, OPEN), "top"]} />
      <Pic id={pick(c, "collage", 2)} box={C} zoom={drift(len, 1.06, 1.0)} reveal={[enter(2, 1.2, OPEN), "bottom"]} />
      <Text font="loraItalic" weight={700} size={18} tracking={1} color={INK} x={1884} y={112} anchor="rm" opacity={fade(2.6, 1)}>{k1}</Text>
      <Text font="loraItalic" weight={700} size={18} tracking={1} color={INK} x={1884} y={136} anchor="rm" opacity={fade(2.8, 1)}>{k2}</Text>
      <Stanza text={c.copy.collage_lines} x={800} y={918} gap={36} D={D} from={3} every={0.6} size={20} anchor="lt" maxWidth={520} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 13 · handwritten romance

export const Romance: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, enter, fade, drift } = usePage(c, at);
  const [a = "", b = "", d = ""] = lines(c.copy.romance_title);
  // the title fades up from pale pink to full colour
  const tint = (p: number) => `rgba(212,35,122,${0.25 + 0.75 * p})`;
  const pens: [string, number, number, number][] = [[a, 860, 150, 1.2], [b, 1040, 380, 1.5], [d, 880, 610, 1.8]];
  return (
    <Frame c={c} at={at} len={len}>
      {lettered("titleRomance", c.copy.romance_title) ? (
        <Art name="titleRomance" x={850} y={140} height={830} opacity={0.25 + 0.75 * fade(1.2, 2)} style={settle(fade(1.2, 1.4))} />
      ) : pens.map(([text, x, y, n], i) => {
        const p = fade(n, 1.6);
        return <Pen key={i} text={text} x={x} y={y} size={176} color={tint(p)} p={p} rotate={-6} />;
      })}
      <Pic id={pick(c, "romance")} box={{ x: 0, y: 0, w: 832, h: 1080 }} zoom={drift(len, 1.06, 1.0)} reveal={[enter(0, 1.2, OPEN), "left"]} />
      <Text font="songti" weight={700} size={120} color={ACCENT} x={1774} y={276} anchor="cm" opacity={eSine(ramp(t, D(2), D(3)))}>囍</Text>
      <Stanza text={c.copy.romance_lines} x={1843} y={556} gap={64} D={D} from={2.6} every={0.6} size={24} color={INK} anchor="rt" maxWidth={640} />
    </Frame>
  );
};

// ---------------------------------------------------------------- 14 · vows and thank you

export const Ending: React.FC<PageProps> = ({ c, at, len }) => {
  const { t, D, enter, drift } = usePage(c, at);
  const box = { x: 0, y: 0, w: 812, h: 1080 };
  // the photo grows out of a small card right of its column's middle and settles at full size
  const g = enter(0, 1.6, 0.53);
  const out = eIo3(ramp(t, D(len - 1.5), D(len) + 1));
  return (
    <Frame c={c} at={at} len={0}>
      <Pic id={pick(c, "ending")} box={box} zoom={drift(len + 2, 1.16, 1.0)} scale={lerp(0.06, 1, g)} tx={lerp(330, 0, g)} />
      <Stanza text={c.copy.vow} x={1371} y={228} gap={96} D={D} from={1.4} every={1} size={28} weight={700} maxWidth={900} />
      <Text font="serif" size={40} tracking={30} color={ACCENT} x={1371} y={826} anchor="cm" reveal={{ start: D(6.6), step: 0.08, dur: 0.5, dist: 0, blur: 4 }}>{c.copy.thank_you}</Text>
      <Line text={`${c.groom} & ${c.bride} · ${c.date}`} x={1371} y={900} at={D(7.6)} size={24} tracking={4} color={GREY} anchor="cm" />
      <AbsoluteFill style={{ background: PAPER, opacity: out }} />
    </Frame>
  );
};
