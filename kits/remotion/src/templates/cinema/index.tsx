import React, { useMemo } from "react";
import { AbsoluteFill, type CalculateMetadataFunction } from "remotion";
import { z } from "zod";
import { Music } from "../../components/Music";
import { beatClock as sharedBeatClock, loadBeatGrid, type BeatGrid as Grid } from "../../core/beat-clock";
import { defineTemplate, type TemplateProps } from "../../core/template";
import { useT } from "../../core/time";
import { Ambient, Born, Closing, Counter, Dating, Dating2, Ending, Growing, Hearts, Met, Pairs, Quote, Today, Trio, Wedding, Welcome, type Ctx, type PageProps } from "./scenes";

/**
 * Cinema · 黑幕影院 — a wedding opening film for the venue screen: on black, the welcome is typed over
 * a dusk sky, two childhood portraits carry the couple's names and birthdays, four childhood photos
 * slide into a row, the day they met is a drawn line that opens into their first photo, a counter runs
 * up to the days together, dating photos fill the screen panel by panel, then the wedding, a typed
 * line of their own, and a line drawing of the couple with thanks. Every page is planned in beats of
 * the soundtrack's measured beat map.
 * Default music: Possible Dreams (86.9 BPM, download-only; `npm run music`).
 */

export const cinemaSlots = {
  kidGroom: {},
  kidBride: {},
  childhood: { count: 4 },
  first: {},
  dating: { count: 6 },
  dating2: { count: 3 },
  wedding: {},
  pairs: { count: 4 },
  trio: { count: 3 },
  closing: {},
} as const;

/** Pages in order with their length in beats; boundaries fall on whole bars. */
const PAGES: [id: string, Page: React.FC<PageProps>, beats: number][] = [
  ["welcome", Welcome, 16],
  ["born", Born, 12],
  ["growing", Growing, 12],
  ["met", Met, 12],
  ["counter", Counter, 8],
  ["dating", Dating, 16],
  ["hearts", Hearts, 8],
  ["dating2", Dating2, 8],
  ["today", Today, 8],
  ["wedding", Wedding, 8],
  ["pairs", Pairs, 16],
  ["trio", Trio, 8],
  ["quote", Quote, 12],
  ["closing", Closing, 8],
  ["ending", Ending, 12],
];
/** Page lengths at a pace: each page lasts `pace` times its beats, rounded to whole bars (4 beats). */
const pagedAt = (pace: number) => {
  let at = 0;
  return PAGES.map(([id, Page, beats]) => {
    const len = Math.max(4, Math.round((beats * pace) / 4) * 4);
    const page = { id, Page, at, len };
    at += len;
    return page;
  });
};
const totalBeats = (pace: number) => pagedAt(pace).reduce((sum, p) => sum + p.len, 0);
/** Tempo used when the project has no beat map (silent drafts). */
const FALLBACK_BPM = 86.9;
/** Seconds after the last beat for the closing fade. */
const TAIL = 2;

export const COPY = {
  welcome_1: { label: "开场 · 第一行打字", text: "欢迎来到我们的婚礼" },
  welcome_2: { label: "开场 · 第二行打字", text: "这是属于我们的故事" },
  groom_label: { label: "童年页 · 新郎称呼", text: "新郎" },
  bride_label: { label: "童年页 · 新娘称呼", text: "新娘" },
  born_prefix: { label: "童年页 · 生日前缀", text: "出生于" },
  grow_title: { label: "童年四图 · 标题", text: "在慢慢长大的路上" },
  grow_lines: { label: "童年四图 · 下方两行（用｜分隔）", text: "我们各自走过｜属于自己的童年" },
  met_line: { label: "相遇页 · 日期下的一句", text: "那一天，两个人的故事有了交集" },
  counter_head: { label: "计数页 · 上方小字", text: "我们已经一起走过" },
  counter_unit: { label: "计数页 · 数字后的单位", text: "天" },
  hearts: { label: "恋爱中段 · 打字一句（可用｜分两行）", text: "两颗心｜慢慢靠近" },
  today: { label: "婚礼前 · 打字一句", text: "今天，我们决定一起走下去" },
  quote: { label: "结尾前 · 打字两行（用｜分隔）", text: "人海里有那么多人｜我只想和你慢慢变老" },
  thanks: { label: "结尾 · 致谢两行（用｜分隔）", text: "谢谢你们前来｜见证我们的新篇章" },
};

type Props = TemplateProps<typeof cinemaSlots> & { beatGrid?: Grid | null; pace: number; since: string; groomBorn: string; brideBorn: string };

/** Beat clock that also extrapolates before beat 0, where the first entrance starts early. */
const beatClock = (grid: Grid | null | undefined) => {
  const at = sharedBeatClock(grid, FALLBACK_BPM);
  return (n: number) => (n >= 0 ? at(n) : Math.max(0, at(0) + n * (at(1) - at(0))));
};
const filmSeconds = (grid: Grid | null | undefined, pace = 1) => beatClock(grid)(totalBeats(pace)) + TAIL;

const pad = (n: number) => String(n).padStart(2, "0");
const dateCn = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return `${y}年${pad(m)}月${pad(d)}日`;
};
const daysBetween = (from: string, to: string) => Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 86400000));

const Cinema: React.FC<Props> = ({ couple, photos, copy, music, beatGrid, pace, since, groomBorn, brideBorn }) => {
  const t = useT();
  const B = useMemo(() => beatClock(beatGrid), [beatGrid]);
  const c: Ctx = useMemo(() => ({ B, ph: photos, copy, groom: couple.groom, bride: couple.bride, date: dateCn(couple.date), since: dateCn(since),
    groomBorn: dateCn(groomBorn), brideBorn: dateCn(brideBorn), days: daysBetween(since, couple.date) }), [B, photos, copy, couple, since, groomBorn, brideBorn]);
  const pages = useMemo(() => pagedAt(pace), [pace]);
  const end = B(totalBeats(pace));
  // a page is on screen from a beat before it starts until its own end; the last one stays to the end
  const live = pages.filter((p, i) => t >= B(p.at - 1) && (i === pages.length - 1 || t < B(p.at + p.len)));
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Ambient />
      {live.map(({ id, Page, at, len }) => <Page key={id} c={c} at={at} len={len} />)}
      <AbsoluteFill style={{ background: "#000", opacity: Math.min(1, Math.max(0, (t - end + 0.5) / TAIL)) }} />
      <Music music={music} />
    </AbsoluteFill>
  );
};

const beatGridSchema = z.object({ beats: z.array(z.number()) }).nullable().optional();
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

const definition = defineTemplate(
  {
    id: "VVV-Cinema",
    code: "Cinema",
    title: "黑幕影院",
    slots: cinemaSlots,
    // Exact length needs the beat map; calculateMetadata supplies it. This is the no-music length.
    seconds: (props) => filmSeconds((props as Props).beatGrid, (props as Props).pace),
    component: Cinema as React.FC<TemplateProps<typeof cinemaSlots>>,
    fps: 30,
    copy: COPY,
    poster: 6,
    // Possible Dreams — Mixkit Stock Music Free License; download-only (public/music/sources.json)
    music: { src: "music/mixkit-possible-dreams.mp3", volume: 0.9, trimBeforeSec: 0, fadeInSec: 0.3, fadeOutSec: 3 },
  },
  {
    schema: {
      beatGrid: beatGridSchema,
      pace: z.number().min(1).max(2).describe("节奏：每页时长的倍数。1 为默认；1.5 让每页停留更久，全片随之变长"),
      since: isoDate.describe("相遇或在一起的日期（YYYY-MM-DD）：相遇页显示它，计数页算到婚礼日期的天数"),
      groomBorn: isoDate.describe("新郎生日（YYYY-MM-DD），童年页显示"),
      brideBorn: isoDate.describe("新娘生日（YYYY-MM-DD），童年页显示"),
    },
    defaults: { beatGrid: null, pace: 1, since: "2021-09-12", groomBorn: "1996-03-08", brideBorn: "1997-11-21" },
  },
);

/** Load the beat map once, before rendering, so the length and every page follow the music. */
const calculateMetadata: CalculateMetadataFunction<any> = async ({ props }) => {
  const parsed = definition.schema.parse(props) as Props;
  const grid = await loadBeatGrid(parsed.music);
  return { durationInFrames: Math.ceil(filmSeconds(grid, parsed.pace) * parsed.fps), props: { ...parsed, beatGrid: grid } };
};

export const cinema = { ...definition, calculateMetadata };
