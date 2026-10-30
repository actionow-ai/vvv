import React, { useMemo } from "react";
import { AbsoluteFill, type CalculateMetadataFunction } from "remotion";
import { z } from "zod";
import { Music } from "../../components/Music";
import { beatClock as sharedBeatClock, loadBeatGrid, type BeatGrid as Grid } from "../../core/beat-clock";
import { formatDate } from "../../core/couple";
import { defineTemplate, type TemplateProps } from "../../core/template";
import { useT } from "../../core/time";
import { About, Caption, Collage, Columns, Cover, Ending, Heart, Invite, BUBBLE_DONE, PAPER, Pair, Poem, Romance, Thanks, Trio, Xi, type Ctx, type PageProps } from "./scenes";

/**
 * Editorial · 简约留白杂志 — a clean wedding MV laid out like magazine spreads on white paper: a
 * handwritten cover, round portraits on an invitation, poems beside photos, a heart that opens onto
 * a full-bleed photo, columns that grow to full height, and a closing vow. Every page is planned in
 * beats of the soundtrack's measured beat map and leaves under a sweep of soft white discs.
 * Default music: When in Love (94.8 BPM, download-only; `npm run music`).
 */

export const editorialSlots = {
  cover: {},
  invite: { count: 2 },
  poem: {},
  trio: { count: 3 },
  pair: { count: 4 },
  thanks: { count: 2 },
  caption: { count: 2 },
  heart: {},
  xi: { count: 2 },
  about: { count: 2 },
  triptych: { count: 6 },
  collage: { count: 3 },
  romance: {},
  ending: {},
} as const;

/** Pages in order with their length in beats; boundaries fall on 8-beat phrases. */
const PAGES: [id: string, Page: React.FC<PageProps>, beats: number][] = [
  ["cover", Cover, 8],
  ["invite", Invite, 8],
  ["poem", Poem, 8],
  ["trio", Trio, 8],
  ["pair", Pair, 16],
  ["thanks", Thanks, 8],
  ["caption", Caption, 8],
  ["heart", Heart, 8],
  ["xi", Xi, 8],
  ["about", About, 8],
  ["columns", Columns, 16],
  ["collage", Collage, 8],
  ["romance", Romance, 8],
  ["ending", Ending, 12],
];
/**
 * Page lengths at a pace: each page lasts `pace` times its designed beats, rounded to whole bars
 * (4 beats) so every page change still falls on a downbeat. Entrances keep their beat timing; a
 * slower pace only lengthens the hold.
 */
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
const FALLBACK_BPM = 94.8;
/** Seconds after the last beat for the closing fade. */
const TAIL = 1.4;

export const COPY = {
  cover_title: { label: "封面 · 手写标题（两行，用｜分隔）", text: "我们的｜婚礼" },
  cover_en: { label: "封面 · 英文小字", text: "WELCOME TO OUR WEDDING" },
  invite_head: { label: "请柬页 · 顶部英文", text: "WEDDING INVITATION" },
  invite_ask: { label: "请柬页 · 左圆弧形英文", text: "Would you marry me?" },
  invite_yes: { label: "请柬页 · 右圆弧形英文", text: "Yes, I do." },
  poem: { label: "诗句页 · 诗句（用｜分行，空一段用｜｜）", text: "遇见你的那天｜风也变得很温柔｜往后的每一个清晨与黄昏｜都想和你一起慢慢走｜｜愿余生岁岁年年｜都有你在身旁" },
  poem_en: { label: "诗句页 · 英文小字（用｜分行）", text: "Of all the roads I could have taken,｜every one led me to you,｜and I would walk them all again." },
  trio_kicker: { label: "三联页 · 左上英文（两行，用｜分隔）", text: "I LOVE YOU｜FOR YOU" },
  trio_quote: { label: "三联页 · 右下一句（两行，用｜分隔）", text: "喜欢你的笑｜也喜欢笑着的我们" },
  pair_quote_a: { label: "双图页 · 第一组顶部一句", text: "“在人海里，偏偏遇见你”" },
  pair_quote_b: { label: "双图页 · 第二组顶部一句", text: "“爱是日常，也是一生”" },
  pair_tag: { label: "双图页 · 左下英文", text: "FOREVER IN LOVE" },
  thanks: { label: "居中诗句页（用｜分行，空一段用｜｜）", text: "谢谢时光｜让我们刚好遇见｜｜从那天起｜每一天都是好日子" },
  caption: { label: "双图页 · 底部打字一句", text: "从此我们相识、相知、相爱，再也不分开" },
  heart_lines: { label: "爱心页 · 左下三行（用｜分隔）", text: "我们决定牵起彼此的手｜把平凡的日子过成诗｜一起去看更远的风景" },
  heart_en: { label: "爱心页 · 右上英文（用｜分隔）", text: "Two hearts, one home,｜one story still being written." },
  xi_lines: { label: "囍字页 · 三行（用｜分隔）", text: "日子平平淡淡，有你就很好｜一粥一饭，一朝一夕｜都是我们的小幸福" },
  about_kicker: { label: "竖排页 · 小标题", text: "· About Love ·" },
  about_title: { label: "竖排页 · 大标题", text: "WE GOT MARRIED" },
  collage_kicker: { label: "拼贴页 · 右上英文（两行，用｜分隔）", text: "LOVE｜PURE LOVE" },
  collage_lines: { label: "拼贴页 · 小字（用｜分行）", text: "红妆十里，良辰已至｜愿我们岁岁年年，喜乐平安｜把每一个平凡的日子都过成节日" },
  romance_title: { label: "手写大字（三行，用｜分隔）", text: "永远的｜浪漫｜主义者" },
  romance_lines: { label: "手写页 · 右下三行（用｜分隔）", text: "把这份浪漫写进日子里｜把这份心动留给每一天｜也分享给今天的你们" },
  vow: { label: "结尾 · 誓言（用｜分行）", text: "我们会坚守｜今天许下的诺言｜未来的路一起走｜风雨同舟，甘苦与共｜相伴一生" },
  thank_you: { label: "结尾 · 致谢英文", text: "THANK YOU" },
};

type Props = TemplateProps<typeof editorialSlots> & { beatGrid?: Grid | null; pace: number };

/** Beat clock that also extrapolates before beat 0, where the first entrance starts early. */
const beatClock = (grid: Grid | null | undefined) => {
  const at = sharedBeatClock(grid, FALLBACK_BPM);
  return (n: number) => (n >= 0 ? at(n) : Math.max(0, at(0) + n * (at(1) - at(0))));
};
const filmSeconds = (grid: Grid | null | undefined, pace = 1) => beatClock(grid)(totalBeats(pace)) + TAIL;

const Editorial: React.FC<Props> = ({ couple, photos, copy, music, beatGrid, pace }) => {
  const t = useT();
  const B = useMemo(() => beatClock(beatGrid), [beatGrid]);
  const c: Ctx = useMemo(() => ({ B, pace, ph: photos, copy, groom: couple.groom, bride: couple.bride, date: formatDate(couple.date, "dot"), tagline: couple.tagline }),
    [B, pace, photos, copy, couple]);
  const pages = useMemo(() => pagedAt(pace), [pace]);
  // A page is on screen from just before its first entrance until its bubbles have passed. While
  // one page sweeps out, the next one builds underneath where the paper is already clean.
  const live = pages.filter((p, i) => (i === 0 || t >= B(p.at - 1)) && (i === pages.length - 1 || t < B(p.at + p.len - BUBBLE_DONE)));
  return (
    <AbsoluteFill style={{ background: PAPER }}>
      {[...live].reverse().map(({ id, Page, at, len }) => <Page key={id} c={c} at={at} len={len} />)}
      <Music music={music} />
    </AbsoluteFill>
  );
};

const beatGridSchema = z.object({ beats: z.array(z.number()) }).nullable().optional();

const definition = defineTemplate(
  {
    id: "VVV-Editorial",
    code: "Editorial",
    title: "简约留白杂志",
    slots: editorialSlots,
    // Exact length needs the beat map; calculateMetadata supplies it. This is the no-music length.
    seconds: (props) => filmSeconds((props as Props).beatGrid, (props as Props).pace),
    component: Editorial as React.FC<TemplateProps<typeof editorialSlots>>,
    fps: 30,
    copy: COPY,
    poster: 3.5,
    // When in Love — Mixkit Stock Music Free License; download-only (public/music/sources.json)
    music: { src: "music/mixkit-when-in-love.mp3", volume: 0.9, trimBeforeSec: 0, fadeInSec: 0.3, fadeOutSec: 3 },
  },
  {
    schema: { beatGrid: beatGridSchema, pace: z.number().min(1).max(2).describe("节奏：每页时长的倍数。1 为默认；1.5 让每页（每组照片）停留更久，全片随之变长") },
    defaults: { beatGrid: null, pace: 1 },
  },
);

/** Load the beat map once, before rendering, so the length and every page follow the music. */
const calculateMetadata: CalculateMetadataFunction<any> = async ({ props }) => {
  const parsed = definition.schema.parse(props) as Props;
  const grid = await loadBeatGrid(parsed.music);
  return { durationInFrames: Math.ceil(filmSeconds(grid, parsed.pace) * parsed.fps), props: { ...parsed, beatGrid: grid } };
};

export const editorial = { ...definition, calculateMetadata };
