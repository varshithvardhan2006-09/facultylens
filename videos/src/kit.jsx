import "@fontsource/kalam/700.css";
import "@fontsource-variable/figtree";
import { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// The FacultyLens light theme, the same values as frontend/src/styles/tokens.css.
export const C = {
  wall: "#dde5e1",
  paper: "#ffffff",
  ink: "#16201e",
  muted: "#46524f",
  board: "#183f3a",
  board2: "#22524b",
  boardRule: "#2e5f57",
  onBoard: "#f3f7f5",
  onBoardMuted: "#b8cec7",
  praise: "#cdf1e5",
  criticism: "#ffd8cc",
  neutral: "#eceeed",
  edgePraise: "#0f7f6c",
  edgeCriticism: "#cf4b29",
  highlight: "#ffd84d",
  tape: "#f4e7b8",
};
export const FONT = '"Figtree Variable", "Segoe UI", sans-serif';
export const MARKER = '"Kalam", "Segoe Print", cursive';
export const FPS = 30;
const LEAD = 0.4; // seconds of quiet before the voice starts in each scene
const TAIL = 0.7;

/** Frames a scene needs: its narration plus a short breath either side. */
export const sceneFrames = (seconds) => Math.ceil((seconds + LEAD + TAIL) * FPS);

/** Hold rendering until the two fonts are ready, so no frame uses a fallback face. */
export function FontGate({ children }) {
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    Promise.all([
      document.fonts.load('700 40px "Kalam"'),
      document.fonts.load('400 40px "Figtree Variable"'),
      document.fonts.load('700 40px "Figtree Variable"'),
    ]).then(() => continueRender(handle));
  }, [handle]);
  return children;
}

/** Spoken spellings back to how they are written, for the captions. */
const WRITTEN = [
  [/Fast A P I/g, "FastAPI"],
  [/A P I/g, "API"],
  [/M V S R/g, "MVSR"],
  [/Mongo D B/g, "MongoDB"],
  [/C P U/g, "CPU"],
  [/W C A G double A/g, "WCAG AA"],
  [/T F I D F/g, "TF-IDF"],
  [/\bVeet\b/g, "Vite"],
  [/Re charts/g, "Recharts"],
  [/\bspacy\b/g, "spaCy"],
  [/\bRoberta\b/g, "RoBERTa"],
  [/\bDeberta\b/g, "DeBERTa"],
  [/\bGrock\b/g, "Groq"],
  [/\brouge\b/g, "ROUGE"],
  [/Bert score/g, "BERTScore"],
  [/short lived/g, "short-lived"],
  [/sign ins/g, "sign-ins"],
  [/one way code/g, "one-way code"],
];
const written = (text) => WRITTEN.reduce((t, [a, b]) => t.replace(a, b), text);

/** The narration for one scene, with captions timed sentence by sentence. */
export function Voice({ src, seconds, text }) {
  const frame = useCurrentFrame();
  const start = LEAD * FPS;
  const parts = written(text).match(/[^.!?:]+[.!?:]?/g).map((s) => s.trim()).filter(Boolean);
  const total = parts.reduce((n, p) => n + p.length, 0);
  let at = start;
  const spans = parts.map((p) => {
    const len = (p.length / total) * seconds * FPS;
    const span = [at, at + len, p];
    at += len;
    return span;
  });
  const now = spans.find(([a, b]) => frame >= a && frame < b);
  return (
    <>
      <Sequence from={start} layout="none">
        <Audio src={staticFile(src)} />
      </Sequence>
      {now && (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 54,
            display: "flex",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <span
            style={{
              maxWidth: 1400,
              padding: "12px 26px",
              borderRadius: 8,
              background: "rgba(22, 32, 30, 0.86)",
              color: C.onBoard,
              fontFamily: FONT,
              fontSize: 34,
              fontWeight: 500,
              lineHeight: 1.35,
              textAlign: "center",
            }}
          >
            {now[2]}
          </span>
        </div>
      )}
    </>
  );
}

/** A sound effect that plays once, at frame `at` of the current scene. */
export function Sfx({ name, at = 0, volume = 0.5 }) {
  return (
    <Sequence from={Math.round(at)} durationInFrames={60} layout="none">
      <Audio src={staticFile(`sound/${name}.wav`)} volume={volume} />
    </Sequence>
  );
}

/** 0 to 1 on a strong ease-out, starting `delay` frames into the scene. */
export function useIn(delay = 0, frames = 18) {
  const frame = useCurrentFrame();
  return interpolate(frame - delay, [0, frames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.23, 1, 0.32, 1),
  });
}

/** A student comment as a note: tinted paper and a strip of tape, settling in from a scatter. */
export function Note({
  kind = "neutral",
  children,
  x,
  y,
  w = 380,
  tilt = -1.5,
  delay = 0,
  from = [0, 80, -8],
  size = 30,
  style,
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 120, mass: 0.9 } });
  const [dx, dy, r0] = from;
  const paper = { praise: C.praise, criticism: C.criticism, neutral: C.neutral }[kind];
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        padding: "26px 26px 24px",
        background: paper,
        borderRadius: 4,
        boxShadow: "0 2px 3px rgba(22,32,30,0.12), 0 14px 28px -10px rgba(22,32,30,0.32)",
        color: C.ink,
        fontFamily: FONT,
        fontSize: size,
        lineHeight: 1.35,
        opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
        transform: `translate(${(1 - p) * dx}px, ${(1 - p) * dy}px) rotate(${tilt + (1 - p) * r0}deg) scale(${0.94 + 0.06 * p})`,
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: -11,
          left: "50%",
          width: 70,
          height: 22,
          marginLeft: -35,
          background: C.tape,
          opacity: 0.85,
          transform: `rotate(${tilt > 0 ? 4 : -3}deg)`,
        }}
      />
      {children}
    </div>
  );
}

/** Marker lettering written in from the left. */
export function Marker({ children, delay = 0, size = 72, color = C.ink, style }) {
  const p = useIn(delay, 22);
  return (
    <div
      style={{
        fontFamily: MARKER,
        fontWeight: 700,
        fontSize: size,
        lineHeight: 1.12,
        color,
        clipPath: `inset(-0.2em ${(1 - p) * 100}% -0.3em 0)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** Plain interface text that rises in. */
export function Text({ children, delay = 0, size = 34, color = C.ink, weight = 400, style }) {
  const p = useIn(delay, 16);
  return (
    <div
      style={{
        fontFamily: FONT,
        fontSize: size,
        fontWeight: weight,
        lineHeight: 1.35,
        color,
        opacity: p,
        transform: `translateY(${(1 - p) * 16}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** A real screenshot of the app on paper, easing in, then drifting slowly (pan and zoom). */
export function Shot({
  src,
  x,
  y,
  w,
  delay = 0,
  zoom = [1, 1.06],
  pan = [0, 0],
  origin = "50% 30%",
  crop,
  style,
}) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = useIn(delay, 20);
  const t = interpolate(frame, [delay, durationInFrames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scale = zoom[0] + (zoom[1] - zoom[0]) * t;
  const h = (w * 1080) / 1920;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: crop ?? h,
        overflow: "hidden",
        borderRadius: 10,
        border: `1px solid #c3cfca`,
        background: C.paper,
        boxShadow: "0 4px 8px rgba(22,32,30,0.12), 0 30px 60px -20px rgba(22,32,30,0.45)",
        opacity: p,
        transform: `translateY(${(1 - p) * 40}px)`,
        ...style,
      }}
    >
      <Img
        src={staticFile(`shots/${src}.png`)}
        style={{
          width: w,
          height: h,
          transformOrigin: origin,
          transform: `scale(${scale}) translate(${pan[0] * t}px, ${pan[1] * t}px)`,
        }}
      />
    </div>
  );
}

/** The two-notes mark, as on the site. */
export function Mark({ size = 120 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32">
      <rect width="32" height="32" rx="7" fill={C.board} />
      <g transform="rotate(-7 13 18)">
        <rect x="6" y="11" width="15" height="14" rx="1.5" fill={C.criticism} />
      </g>
      <g transform="rotate(6 19 13)">
        <rect x="11.5" y="6" width="15" height="14" rx="1.5" fill={C.praise} />
        <rect x="16" y="4.2" width="7" height="3" rx="0.6" fill={C.highlight} />
      </g>
    </svg>
  );
}

/** Background music under a whole video: faded in and out, kept well below the voice. */
export function Music({ volume = 0.14 }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const v = interpolate(frame, [0, 45, durationInFrames - 75, durationInFrames], [0, volume, volume, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <Audio src={staticFile("sound/pad.wav")} volume={v} />;
}

/** A small label chip, for stack names and rules. */
export function Chip({ children, delay = 0, tone = "paper" }) {
  const p = useIn(delay, 14);
  const look = {
    paper: { background: C.paper, color: C.ink, border: "1px solid #c3cfca" },
    board: { background: C.board2, color: C.onBoard, border: `1px solid ${C.boardRule}` },
    here: { background: C.highlight, color: C.ink, border: "1px solid #e6c235" },
  }[tone];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "10px 20px",
        borderRadius: 6,
        fontFamily: FONT,
        fontSize: 28,
        fontWeight: 600,
        opacity: p,
        transform: `translateY(${(1 - p) * 12}px)`,
        ...look,
      }}
    >
      {children}
    </span>
  );
}

export function Wall({ children, color = C.wall }) {
  return <AbsoluteFill style={{ background: color }}>{children}</AbsoluteFill>;
}
