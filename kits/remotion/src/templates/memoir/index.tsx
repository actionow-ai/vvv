import React, { useMemo } from "react";
import { AbsoluteFill, type CalculateMetadataFunction } from "remotion";
import { z } from "zod";
import { Music } from "../../components/Music";
import { beatClock as sharedBeatClock, loadBeatGrid, type BeatGrid as Grid } from "../../core/beat-clock";
import { defineTemplate, type TemplateProps } from "../../core/template";
import { useT } from "../../core/time";
import {
  Ambient, Born, Chapter1, Chapter2, Chapter3, Chapter4, Chats, Ending, Into, Intro, Jump, Letter, License, Love1, Love2, Love3, Love4, LoveTitle, Strip, Thanks, Welcome,
  type Ctx, type PageProps,
} from "./scenes";

/**
 * Memoir · 手写胶片故事 — a wedding opening film that tells the couple's life story in a pen hand on
 * black: a typed welcome, photos in a scanned film frame with quotes, the couple as a die-cut sticker
 * under confetti, their hometowns and childhood faces as stickers, a scrolling 35 mm strip of
 * childhood photos, the chats that introduced them, four chapters, the licence in a camera
 * viewfinder, "what love is" in four pages, a letter and thanks. Every page is planned in beats of the
 * soundtrack's measured beat map. Default music: First Kiss (110 BPM, download-only; `npm run music`).
 */

export const memoirSlots = {
  intro: { count: 4 },
  couple: {},
  homeGroom: {},
  homeBride: {},
  kidGroom: {},
  kidBride: {},
  childhood: { count: 8 },
  chats: { count: 3 },
  ch1: { count: 2 },
  ch2: { count: 2 },
  ch3: { count: 2 },
  ch4: { count: 2 },
  license: {},
  love1: { count: 2 },
  love2: { count: 2 },
  love3: { count: 2 },
  love4: { count: 2 },
} as const;

/** Pages in order with their length in beats; boundaries fall on whole bars. */
const PAGES: [id: string, Page: React.FC<PageProps>, beats: number][] = [
  ["welcome", Welcome, 8],
  ["intro", Intro, 16],
  ["thanks", Thanks, 12],
  ["born", Born, 16],
  ["strip", Strip, 32],
  ["jump", Jump, 8],
  ["chats", Chats, 16],
  ["into", Into, 8],
  ["ch1", Chapter1, 12],
  ["ch2", Chapter2, 12],
  ["ch3", Chapter3, 12],
  ["ch4", Chapter4, 12],
  ["license", License, 16],
  ["lovetitle", LoveTitle, 8],
  ["love1", Love1, 12],
  ["love2", Love2, 12],
  ["love3", Love3, 12],
  ["love4", Love4, 12],
  ["letter", Letter, 32],
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
const FALLBACK_BPM = 110;
/** Seconds after the last beat for the closing fade. */
const TAIL = 2;

export const COPY = {
  welcome: { label: "开场 · 手写打字", text: "欢迎来到我们的婚礼" },
  intro_1: { label: "胶片框照片 · 第一句（前两张照片上）", text: "“人海里，刚好遇见你”" },
  intro_2: { label: "胶片框照片 · 第二句（后两张照片上）", text: "“多幸运，我们成了我们”" },
  thanks: { label: "贴纸合影 · 右侧两行（用｜分隔）", text: "谢谢你们今天能来｜陪我们走进这一天" },
  born_title: { label: "出生页 · 黄色标题", text: "1996年，我们来到这个世界" },
  home_groom: { label: "出生页 · 新郎家乡", text: "北方小城" },
  home_bride: { label: "出生页 · 新娘家乡", text: "南方小镇" },
  strip_1: { label: "胶片条 · 前半句（可用｜分两行）", text: "后来我们才知道" },
  strip_2: { label: "胶片条 · 后半句", text: "我们都被好好爱着长大" },
  jump: { label: "时间跳转（{since} 是相识日期）", text: "直到 {since}" },
  chat_lines: { label: "聊天截图页 · 右侧几行（用｜分行）", text: "朋友的一句介绍｜让我们加上了微信｜从早安聊到晚安" },
  into: { label: "过渡一句", text: "两个人的故事，从这里开始" },
  chapter_1: { label: "章节一 · 标题", text: "在银杏街，第一次并肩走" },
  chapter_2: { label: "章节二 · 标题", text: "一起过的每一个生日" },
  chapter_3: { label: "章节三 · 标题", text: "有了属于我们的小家" },
  chapter_4: { label: "章节四 · 标题", text: "走过分开的站台，等来那句我愿意" },
  license: { label: "领证页（用｜分行）", text: "2026.5.20｜这一年，我们领证啦" },
  love_title: { label: "“爱是什么”标题", text: "爱是什么" },
  love_1: { label: "爱是什么 · 第一页右侧几行（用｜分行）", text: "是一起找遍｜街角的每一家小馆" },
  love_sub_1: { label: "爱是什么 · 第一页底部小字", text: "是把最后一口留给你" },
  love_2: { label: "爱是什么 · 第二页", text: "是你记得｜我随口说过的话" },
  love_sub_2: { label: "爱是什么 · 第二页底部小字", text: "是每一次都被放在心上" },
  love_3: { label: "爱是什么 · 第三页", text: "是一起把日子｜过成喜欢的样子" },
  love_sub_3: { label: "爱是什么 · 第三页底部小字", text: "是吵吵闹闹，也从不松开的手" },
  love_4: { label: "爱是什么 · 第四页", text: "是往后余生｜都是你" },
  love_sub_4: { label: "爱是什么 · 第四页底部小字", text: "是今天，也是以后的每一天" },
  letter: { label: "结尾长信（用｜分行，每行一句）", text: "今天，我们在大家的见证下举行婚礼｜往后的日子，我们会好好相爱｜一起去更远的地方，看更多的风景｜把平凡的日子过得热气腾腾｜谢谢爸爸妈妈，谢谢每一位朋友｜因为你们，我们更懂得什么是爱" },
  ending: { label: "致谢（用｜分行）", text: "愿今天的每一位｜都被温柔以待" },
};

type Props = TemplateProps<typeof memoirSlots> & { beatGrid?: Grid | null; pace: number; since: string };

/** Beat clock that also extrapolates before beat 0, where the first entrance starts early. */
const beatClock = (grid: Grid | null | undefined) => {
  const at = sharedBeatClock(grid, FALLBACK_BPM);
  return (n: number) => (n >= 0 ? at(n) : Math.max(0, at(0) + n * (at(1) - at(0))));
};
const filmSeconds = (grid: Grid | null | undefined, pace = 1) => beatClock(grid)(totalBeats(pace)) + TAIL;

const dotDate = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return `${y}.${m}.${d}`;
};

const Memoir: React.FC<Props> = ({ couple, photos, copy, music, beatGrid, pace, since }) => {
  const t = useT();
  const B = useMemo(() => beatClock(beatGrid), [beatGrid]);
  const c: Ctx = useMemo(() => ({ B, ph: photos, copy, groom: couple.groom, bride: couple.bride, date: dotDate(couple.date), since: dotDate(since) }),
    [B, photos, copy, couple, since]);
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

const definition = defineTemplate(
  {
    id: "VVV-Memoir",
    code: "Memoir",
    title: "手写胶片故事",
    slots: memoirSlots,
    // Exact length needs the beat map; calculateMetadata supplies it. This is the no-music length.
    seconds: (props) => filmSeconds((props as Props).beatGrid, (props as Props).pace),
    component: Memoir as React.FC<TemplateProps<typeof memoirSlots>>,
    fps: 30,
    copy: COPY,
    poster: 32,
    // First Kiss — Mixkit Stock Music Free License; download-only (public/music/sources.json)
    music: { src: "music/mixkit-first-kiss.mp3", volume: 0.9, trimBeforeSec: 0, fadeInSec: 0.3, fadeOutSec: 3 },
  },
  {
    schema: {
      beatGrid: beatGridSchema,
      pace: z.number().min(1).max(2).describe("节奏：每页时长的倍数。1 为默认；1.5 让每页停留更久，全片随之变长"),
      since: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).describe("相识日期（YYYY-MM-DD），时间跳转页显示"),
    },
    defaults: { beatGrid: null, pace: 1, since: "2021-04-17" },
  },
);

/** Load the beat map once, before rendering, so the length and every page follow the music. */
const calculateMetadata: CalculateMetadataFunction<any> = async ({ props }) => {
  const parsed = definition.schema.parse(props) as Props;
  const grid = await loadBeatGrid(parsed.music);
  return { durationInFrames: Math.ceil(filmSeconds(grid, parsed.pace) * parsed.fps), props: { ...parsed, beatGrid: grid } };
};

export const memoir = { ...definition, calculateMetadata };
