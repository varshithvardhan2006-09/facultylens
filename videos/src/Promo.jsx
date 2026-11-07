import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  Series,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import script from "../scripts/promo.json";
import timings from "../public/audio/promo/timings.json";
import { C, FONT, FPS, FontGate, MARKER, Mark, Marker, Sfx, Text, useIn } from "./kit";

/*
 * The publishing promo: 76.8 s at 100 BPM. Every scene is a whole number of beats, so cuts land on
 * the music, and the pile snaps into the wall on the drop at 12.0 s (bar 6).
 */
const BEAT = 0.6;
const SCENES = [
  // id, beats, when the voice starts (s into the scene)
  ["p1", 5, 0.3],
  ["p2", 11, 0.25],
  ["p3", 7, 0.2],
  ["p4", 12, 0.2],
  ["p5", 10, 0.25],
  ["s1", 16, 0.25],
  ["f1", 14, 0.25],
  ["f2", 14, 0.25],
  ["h1", 15, 0.25],
  ["q1", 10, 0.25],
  ["p8", 14, 0.6],
];
const frames = (beats) => Math.round(beats * BEAT * FPS);
const say = Object.fromEntries(script.map((s) => [s.id, s.say]));
const starts = SCENES.reduce((acc, [, beats]) => [...acc, acc.at(-1) + frames(beats)], [0]);
export const promoFrames = starts.at(-1);

// Comments from the app's demo data (synthetic); every scene that shows them says so.
const COMMENTS = [
  ["praise", "Very knowledgeable, answers even tricky questions.", 0],
  ["criticism", "Often comes late to class.", 2],
  ["praise", "Explains every topic clearly, easy to understand.", 1],
  ["criticism", "The pace is too fast, the last units were rushed.", 3],
  ["praise", "Always comes on time and never cancels class.", 2],
  ["criticism", "Very slow in the beginning and rushed at the end.", 3],
  ["praise", "Sir has deep knowledge of the subject.", 0],
  ["praise", "The explanations are very clear and step by step.", 1],
];
const ASPECTS = [
  ["Subject knowledge", C.edgePraise, "Mostly praise"],
  ["Clarity", C.edgePraise, "Mostly praise"],
  ["Punctuality", C.edgeCriticism, "Mixed views"],
  ["Pace", C.edgeCriticism, "Mostly criticism"],
];
const PILE = [[560, 330, -8], [900, 300, 6], [720, 420, -3], [1040, 440, 9], [640, 520, 4], [960, 560, -6], [800, 360, 2], [860, 500, -10]];
const SHADOW = "0 2px 3px rgba(22,32,30,0.12), 0 14px 28px -10px rgba(22,32,30,0.32)";

function DemoLabel({ dark }) {
  return (
    <div style={{ position: "absolute", right: 40, top: 30, fontFamily: FONT, fontSize: 22, color: dark ? C.onBoardMuted : C.muted }}>
      Demo data
    </div>
  );
}

/** Karaoke captions: the line builds word by word as it is spoken, the current word highlighted. */
function Captions({ id, lead, dark }) {
  const frame = useCurrentFrame();
  const words = say[id].split(" ");
  const start = lead * FPS;
  const total = words.reduce((n, w) => n + w.length + 1, 0);
  let at = start;
  const spans = words.map((w) => {
    const len = ((w.length + 1) / total) * timings[id] * FPS;
    const span = [at, w];
    at += len;
    return span;
  });
  if (frame < start) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 48, display: "flex", justifyContent: "center" }}>
      <div style={{ maxWidth: 1500, padding: "12px 26px", borderRadius: 8, background: dark ? "rgba(243,247,245,0.1)" : "rgba(22,32,30,0.88)",
        fontFamily: FONT, fontSize: 38, fontWeight: 600, lineHeight: 1.35, textAlign: "center", color: C.onBoard }}>
        {spans.map(([t, w], i) => {
          const shown = frame >= t;
          const current = shown && (i === spans.length - 1 || frame < spans[i + 1][0]);
          return (
            <span key={i} style={{ opacity: shown ? 1 : 0.18, color: current ? C.highlight : C.onBoard }}>
              {w}{" "}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Voice({ id, lead, dark }) {
  return (
    <>
      <Sequence from={Math.round(lead * FPS)} layout="none">
        <Audio src={staticFile(`audio/promo/${id}.wav`)} />
      </Sequence>
      <Captions id={id} lead={lead} dark={dark} />
    </>
  );
}

/** A note that falls from above and lands with a little bounce. */
function Falling({ text, x, y, tilt, delay }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 11, stiffness: 140, mass: 0.8 } });
  if (frame < delay) return null;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: 360, padding: "22px 22px 20px", background: C.neutral, borderRadius: 4,
      boxShadow: SHADOW, fontFamily: FONT, fontSize: 25, color: C.ink, lineHeight: 1.3,
      transform: `translateY(${(1 - p) * -700}px) rotate(${tilt * (2 - p)}deg)` }}>
      <div style={{ position: "absolute", top: -10, left: "50%", width: 60, height: 20, marginLeft: -30, background: C.tape, opacity: 0.85 }} />
      {text}
    </div>
  );
}

/** p1: the hook, written word by word over a rain of notes. */
function Hook() {
  const frame = useCurrentFrame();
  const words = ["What", "are", "your", "students", "really", "saying?"];
  return (
    <AbsoluteFill style={{ background: C.board }}>
      {[...Array(14)].map((_, i) => {
        const x = ((i * 263) % 1820) - 40;
        const speed = 7 + (i % 4) * 2;
        const y = ((frame * speed + i * 170) % 1500) - 300;
        const paper = [C.praise, C.criticism, C.neutral][i % 3];
        return (
          <div key={i} style={{ position: "absolute", left: x, top: y, width: 150, height: 110, background: paper, opacity: 0.18,
            borderRadius: 4, transform: `rotate(${(i % 2 ? 1 : -1) * (6 + frame * 0.4)}deg)` }} />
        );
      })}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0 26px", maxWidth: 1500 }}>
          {words.map((w, i) => {
            const p = spring({ frame: frame - (9 + i * 5), fps: FPS, config: { damping: 12, stiffness: 180 } });
            return (
              <span key={w} style={{ fontFamily: MARKER, fontWeight: 700, fontSize: 124, color: w === "really" ? C.highlight : C.onBoard,
                display: "inline-block", opacity: Math.min(1, p * 1.5), transform: `translateY(${(1 - p) * 60}px) scale(${0.7 + 0.3 * p})` }}>
                {w}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
      <Voice id="p1" lead={0.3} dark />
    </AbsoluteFill>
  );
}

/** p2: comments pile up, the count climbs, and most go unread. */
function Pile() {
  const frame = useCurrentFrame();
  const count = Math.round(interpolate(frame, [6, 120], [0, 614], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const unread = useIn(118, 14);
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <DemoLabel />
      {COMMENTS.map(([, text], i) => (
        <Falling key={i} text={text} x={PILE[i][0]} y={PILE[i][1]} tilt={PILE[i][2]} delay={4 + i * 9} />
      ))}
      {COMMENTS.map((_, i) => <Sfx key={i} name="pin" at={10 + i * 9} volume={0.22} />)}
      <div style={{ position: "absolute", left: 120, top: 110, fontFamily: FONT }}>
        <div style={{ fontSize: 120, fontWeight: 800, color: C.ink, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{count}</div>
        <div style={{ fontSize: 34, color: C.muted, marginTop: 6 }}>responses this semester</div>
      </div>
      <div style={{ position: "absolute", right: 140, top: 760, opacity: unread, transform: `rotate(-4deg) scale(${0.8 + 0.2 * unread})` }}>
        <span style={{ fontFamily: MARKER, fontWeight: 700, fontSize: 96, color: C.edgeCriticism }}>Never read.</span>
      </div>
      <Voice id="p2" lead={0.25} />
    </AbsoluteFill>
  );
}

/** p3: "FacultyLens reads them all", then the snap on the drop: the pile becomes the wall. */
const SNAP = Math.round(2.4 * FPS);
function Snap() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const logo = spring({ frame: frame - 2, fps, config: { damping: 13, stiffness: 160 } });
  const p = spring({ frame: frame - SNAP, fps, config: { damping: 15, stiffness: 120 } });
  const shake = frame >= SNAP && frame < SNAP + 8 ? Math.sin(frame * 3) * (SNAP + 8 - frame) * 1.6 : 0;
  const perCol = [0, 0, 0, 0];
  return (
    <AbsoluteFill style={{ background: C.wall, transform: `translate(${shake}px, ${shake * 0.5}px)` }}>
      <DemoLabel />
      {COMMENTS.map(([kind, text, col], i) => {
        const row = perCol[col]++;
        const [px, py, pt] = PILE[i];
        const tx = 90 + col * 450;
        const ty = 300 + row * 240;
        const paper = frame < SNAP ? C.neutral : { praise: C.praise, criticism: C.criticism }[kind];
        return (
          <div key={i} style={{ position: "absolute", left: px + (tx - px) * p, top: py + (ty - py) * p, width: 360, padding: "22px 22px 20px",
            background: paper, borderRadius: 4, boxShadow: SHADOW, fontFamily: FONT, fontSize: 25, lineHeight: 1.3, color: C.ink,
            transform: `rotate(${pt + ((row % 2 ? 1.3 : -1.5) - pt) * p}deg)` }}>
            {text}
          </div>
        );
      })}
      {frame < SNAP + 6 && (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center",
          opacity: interpolate(frame, [SNAP, SNAP + 6], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          <div style={{ display: "flex", alignItems: "center", gap: 30, padding: "28px 44px", borderRadius: 14, background: C.board,
            boxShadow: "0 30px 60px -20px rgba(22,32,30,0.6)", transform: `scale(${0.6 + 0.4 * logo})`, opacity: logo }}>
            <Mark size={110} />
            <span style={{ fontFamily: MARKER, fontWeight: 700, fontSize: 92, color: C.onBoard }}>FacultyLens</span>
          </div>
        </AbsoluteFill>
      )}
      <Sfx name="snap" at={SNAP} volume={0.7} />
      <Voice id="p3" lead={0.2} />
    </AbsoluteFill>
  );
}

function AspectHeading({ title, color, verdict, c, at }) {
  const p = useIn(at, 12);
  const v = useIn(at + 8, 10);
  return (
    <div style={{ position: "absolute", left: 90 + c * 450, top: 110 }}>
      <div style={{ fontFamily: MARKER, fontWeight: 700, fontSize: 50, color: C.ink, transform: `scale(${0.6 + 0.4 * p})`,
        transformOrigin: "left bottom", opacity: p }}>
        {title}
      </div>
      <svg width="270" height="14" style={{ marginTop: 4 }}>
        <path d="M2 8 C 60 4 120 11 180 7 S 245 6 266 8" stroke={color} strokeWidth="6" fill="none" strokeLinecap="round"
          pathLength="1" strokeDasharray="1" strokeDashoffset={1 - p} />
      </svg>
      <div style={{ marginTop: 6, fontFamily: FONT, fontSize: 24, fontWeight: 700, color, opacity: v }}>{verdict}</div>
    </div>
  );
}

/** p4: each aspect heading lands as it is named, with its marker stroke and verdict. */
function Sort() {
  const frame = useCurrentFrame();
  // When each aspect is spoken: after about 2.4 s of lead-in, the four names follow.
  const named = [2.5, 3.5, 4.2, 5.1].map((s) => Math.round(s * FPS));
  const perCol = [0, 0, 0, 0];
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <DemoLabel />
      {ASPECTS.map(([title, color, verdict], c) => (
        <AspectHeading key={title} title={title} color={color} verdict={verdict} c={c} at={named[c]} />
      ))}
      {COMMENTS.map(([kind, text, col], i) => {
        const row = perCol[col]++;
        const pulse = frame >= named[col] && frame < named[col] + 10 ? 1 + 0.04 * Math.sin(((frame - named[col]) / 10) * Math.PI) : 1;
        return (
          <div key={i} style={{ position: "absolute", left: 90 + col * 450, top: 300 + row * 240, width: 360, padding: "22px 22px 20px",
            background: { praise: C.praise, criticism: C.criticism }[kind], borderRadius: 4, boxShadow: SHADOW, fontFamily: FONT,
            fontSize: 25, lineHeight: 1.3, color: C.ink, transform: `rotate(${row % 2 ? 1.3 : -1.5}deg) scale(${pulse})` }}>
            {text}
            <div style={{ marginTop: 8, fontSize: 20, color: C.muted }}>{kind === "praise" ? "Praise" : "Criticism"}</div>
          </div>
        );
      })}
      {named.map((t, c) => <Sfx key={c} name="pin" at={t} volume={0.3} />)}
      <Voice id="p4" lead={0.2} />
    </AbsoluteFill>
  );
}

/** p5: a comment is typed live; the highlighter finds the name and number, which turn into tags. */
function Redact() {
  const frame = useCurrentFrame();
  const text = "Kavitha mam, call me on 98480 12345 about the internals.";
  const typed = Math.min(text.length, Math.max(0, Math.floor((frame - 4) * 1.9)));
  const typingDone = 4 + Math.ceil(text.length / 1.9);
  const hl = useIn(typingDone + 4, 14);
  const swap = frame > typingDone + 22;
  const held = useIn(typingDone + 40, 22);
  const abuse = useIn(6, 12);
  const tray = useIn(typingDone + 30, 12);
  const mark = (s) => (
    <span style={{ backgroundImage: `linear-gradient(${C.highlight}, ${C.highlight})`, backgroundRepeat: "no-repeat",
      backgroundSize: `${hl * 100}% 100%`, borderRadius: 4, padding: "0 4px" }}>{s}</span>
  );
  const tag = (s) => <span style={{ background: C.board, color: C.onBoard, padding: "0 12px", borderRadius: 6, fontWeight: 700, fontSize: "0.85em" }}>{s}</span>;
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <div style={{ position: "absolute", left: 120, top: 100 }}>
        <Marker size={64}>Private before anyone reads it</Marker>
      </div>
      <div style={{ position: "absolute", left: 120, top: 280, width: 1000, minHeight: 210, padding: "34px 40px", borderRadius: 6,
        background: C.neutral, boxShadow: "0 2px 3px rgba(22,32,30,0.12), 0 18px 34px -12px rgba(22,32,30,0.35)", fontFamily: FONT,
        fontSize: 48, lineHeight: 1.4, color: C.ink }}>
        {typed < text.length ? (
          <>{text.slice(0, typed)}<span style={{ opacity: frame % 16 < 8 ? 1 : 0 }}>|</span></>
        ) : swap ? (
          <>{tag("[FACULTY]")} mam, call me on {tag("[PHONE]")} about the internals.</>
        ) : (
          <>{mark("Kavitha")} mam, call me on {mark("98480 12345")} about the internals.</>
        )}
      </div>
      {[...Array(Math.ceil(text.length / 3))].map((_, i) => <Sfx key={i} name="key" at={4 + i * 1.6} volume={0.25} />)}
      <Sfx name="swipe" at={typingDone + 4} volume={0.3} />
      <Sfx name="click" at={typingDone + 22} volume={0.4} />
      <div style={{ position: "absolute", left: 1220, top: 260, width: 600 }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: 560, padding: "26px 28px", borderRadius: 4, background: C.criticism,
          fontFamily: FONT, fontSize: 32, lineHeight: 1.35, color: C.ink, boxShadow: SHADOW, opacity: abuse,
          transform: `translate(${held * 20}px, ${held * 300}px) rotate(${3 - held * 4}deg) scale(${1 - held * 0.08})` }}>
          This teacher is useless and a total waste of time.
        </div>
        <div style={{ position: "absolute", left: -20, top: 260, width: 620, height: 250, borderRadius: 12,
          border: `3px dashed ${C.edgeCriticism}`, opacity: tray }}>
          <div style={{ position: "absolute", left: 22, bottom: 16, fontFamily: FONT, fontSize: 28, fontWeight: 700, color: C.edgeCriticism }}>
            Held for review
          </div>
        </div>
      </div>
      <Voice id="p5" lead={0.25} />
    </AbsoluteFill>
  );
}

/** A browser window around a real screenshot, so the app reads as an app. */
function Browser({ src, x = 280, y = 56, w = 1360, children }) {
  const s = w / 1920;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, borderRadius: 12, overflow: "hidden", background: C.paper,
      boxShadow: "0 6px 12px rgba(22,32,30,0.15), 0 40px 80px -24px rgba(22,32,30,0.55)", border: "1px solid #c3cfca" }}>
      <div style={{ height: 40, background: "#e6ece9", display: "flex", alignItems: "center", gap: 9, padding: "0 16px" }}>
        {["#cf4b29", "#e3b341", "#0f7f6c"].map((c) => <span key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />)}
        <span style={{ marginLeft: 18, padding: "4px 16px", borderRadius: 6, background: C.paper, fontFamily: FONT, fontSize: 18, color: C.muted }}>
          localhost:5173
        </span>
      </div>
      <div style={{ position: "relative", width: w, height: 1080 * s, overflow: "hidden" }}>
        <Img src={staticFile(`shots/${src}.png`)} style={{ width: w, height: 1080 * s }} />
        {children}
      </div>
    </div>
  );
}

/** A drawn pointer that glides along `path` ([frame, x, y] stops) and clicks, with a ripple. */
function Pointer({ path, clickAt }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  let [x, y] = [path[0][1], path[0][2]];
  for (let i = 0; i < path.length - 1; i++) {
    const [f0, x0, y0] = path[i];
    const [f1, x1, y1] = path[i + 1];
    if (frame >= f0) {
      const t = interpolate(frame, [f0, f1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
      const e = 1 - (1 - t) ** 3;
      x = x0 + (x1 - x0) * e;
      y = y0 + (y1 - y0) * e;
    }
  }
  const press = clickAt.some((c) => frame >= c && frame < c + 5);
  return (
    <>
      {clickAt.map((c) => {
        if (frame < c || frame > c + 24) return null;
        const r = spring({ frame: frame - c, fps, config: { damping: 30, stiffness: 120 } });
        return (
          <div key={c} style={{ position: "absolute", left: x - 34 * r, top: y - 34 * r, width: 68 * r, height: 68 * r,
            borderRadius: "50%", border: `4px solid ${C.highlight}`, opacity: 1 - r }} />
        );
      })}
      <svg width="46" height="46" viewBox="0 0 24 24" style={{ position: "absolute", left: x - 6, top: y - 3,
        transform: `scale(${press ? 0.85 : 1})`, transformOrigin: "6px 3px", filter: "drop-shadow(0 3px 4px rgba(0,0,0,0.35))" }}>
        <path d="M5 3l13 8-6 1.5L9 19z" fill={C.ink} stroke={C.paper} strokeWidth="1.6" strokeLinejoin="round" />
      </svg>
    </>
  );
}

const S = 1360 / 1920; // screenshot scale inside the browser window

/** A role label that slides in from the left, naming who this part of the app is for. */
function Role({ children, at = 2 }) {
  const p = useIn(at, 14);
  return (
    <div style={{ position: "absolute", left: 280, top: 6, padding: "6px 18px", borderRadius: 6, background: C.highlight, color: C.ink,
      fontFamily: FONT, fontSize: 30, fontWeight: 700, opacity: p, transform: `translateX(${(1 - p) * -40}px)`, zIndex: 5 }}>
      {children}
    </div>
  );
}

/** A short explanatory label pinned over a screen (it explains; it never pretends to be the app). */
function Callout({ children, x, y, at, kind = "praise" }) {
  const { fps } = useVideoConfig();
  const p = spring({ frame: useCurrentFrame() - at, fps, config: { damping: 13, stiffness: 160 } });
  const paper = { praise: C.praise, criticism: C.criticism, neutral: C.neutral }[kind];
  return (
    <div style={{ position: "absolute", left: x, top: y, width: 420, padding: "20px 22px", borderRadius: 4, background: paper, boxShadow: SHADOW,
      fontFamily: FONT, fontSize: 28, fontWeight: 700, lineHeight: 1.3, color: C.ink, zIndex: 6, opacity: Math.min(1, p * 1.6),
      transform: `translateY(${(1 - p) * 40}px) rotate(${-2 + (1 - p) * 6}deg) scale(${0.85 + 0.15 * p})` }}>
      <div style={{ position: "absolute", top: -10, left: "50%", width: 60, height: 20, marginLeft: -30, background: C.tape, opacity: 0.85 }} />
      {children}
    </div>
  );
}

/** Pick the screen for the current frame from [fromFrame, shot] steps. */
const screenAt = (frame, steps) => steps.reduce((cur, [f, src]) => (frame >= f ? src : cur), steps[0][1]);

/** s1: a student opens a form, rates, ticks the consent box, and sends. */
function Students() {
  const frame = useCurrentFrame();
  const GIVE = 54;
  const RATE = 128;
  const TICK = 218;
  const src = screenAt(frame, [[0, "student-forms"], [GIVE + 6, "student-form"], [RATE + 30, "student-form-end"]]);
  const rated = frame >= RATE && src === "student-form";
  const ticked = frame >= TICK;
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <Role>Students</Role>
      <Browser src={src}>
        {rated && (
          <div style={{ position: "absolute", left: (1370 - 40) * S, top: (340 - 23) * S, width: 80 * S, height: 46 * S, borderRadius: 4,
            background: C.highlight, border: `1px solid ${C.ink}`, display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: FONT, fontWeight: 700, fontSize: 15, color: C.ink }}>4</div>
        )}
        {ticked && src === "student-form-end" && (
          <svg width={20} height={20} viewBox="0 0 16 16" style={{ position: "absolute", left: 652 * S - 10, top: 898 * S - 10 }}>
            <rect x="1" y="1" width="14" height="14" rx="2" fill={C.ink} />
            <path d="M4 8.5 7 11.5 12 5" stroke={C.paper} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        <Pointer
          clickAt={[GIVE, RATE, TICK]}
          path={[
            [0, 900, 600], [10, 900, 600], [GIVE - 4, 1481 * S, 285 * S + 4],
            [GIVE + 20, 1481 * S, 285 * S + 4], [RATE - 4, 1370 * S, 340 * S + 4],
            [RATE + 26, 1000, 500], [TICK - 6, 652 * S, 898 * S + 4],
          ]}
        />
      </Browser>
      {[GIVE, RATE, TICK].map((t) => <Sfx key={t} name="click" at={t} volume={0.4} />)}
      <Sfx name="swipe" at={GIVE + 6} volume={0.2} />
      <Callout x={1300} y={420} at={TICK + 26}>Sent. Saved without the student's name.</Callout>
      <Sfx name="pin" at={TICK + 28} volume={0.35} />
      <DemoLabel />
      <Voice id="s1" lead={0.25} />
    </AbsoluteFill>
  );
}

/** f1: the faculty page; the pointer opens a cluster's notes and the drawer slides in. */
function TeacherPage() {
  const frame = useCurrentFrame();
  const CLICK = 120;
  const zoom = interpolate(frame, [CLICK + 10, 252], [1, 1.1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <Role>Faculty</Role>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${zoom})`, transformOrigin: "78% 35%" }}>
        <Browser src={frame < CLICK + 6 ? "faculty-top" : "faculty-drawer"}>
          {frame < CLICK + 30 && (
            <Pointer clickAt={[CLICK]} path={[[0, 1100, 700], [40, 1100, 700], [CLICK - 4, 911 * S, 764 * S + 4]]} />
          )}
        </Browser>
      </div>
      <Sfx name="click" at={CLICK} volume={0.45} />
      <Sfx name="swipe" at={CLICK + 4} volume={0.25} />
      <DemoLabel />
      <Voice id="f1" lead={0.25} />
    </AbsoluteFill>
  );
}

/** f2: strengths, areas to improve with next steps, then the profile that waits for approval. */
function Strengths() {
  const frame = useCurrentFrame();
  const CUT = 140;
  const GEN = 200;
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <Role>Faculty</Role>
      <Browser src={frame < CUT ? "faculty-summary" : "profile-review"}>
        {frame >= CUT && frame < GEN + 30 && (
          <Pointer clickAt={[GEN]} path={[[CUT, 900, 500], [CUT + 12, 900, 500], [GEN - 4, 580 * S, 342 * S + 4]]} />
        )}
      </Browser>
      {frame < CUT && <Callout x={1320} y={600} at={70} kind="neutral">A next step for every area to improve</Callout>}
      {frame >= CUT && <Callout x={1320} y={430} at={GEN + 10}>Nothing is published until the teacher approves it</Callout>}
      <Sfx name="swipe" at={CUT} volume={0.22} />
      <Sfx name="click" at={GEN} volume={0.4} />
      <Sfx name="pin" at={72} volume={0.3} />
      <DemoLabel />
      <Voice id="f2" lead={0.25} />
    </AbsoluteFill>
  );
}

/** h1: department insights, the bias tab, then Action taken. */
function HeadOfDepartment() {
  const frame = useCurrentFrame();
  const BIAS = 70;
  const ACTIONS = 168;
  const src = screenAt(frame, [[0, "insights"], [BIAS + 6, "bias"], [ACTIONS + 6, "hod-actions"]]);
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <Role>Head of department</Role>
      <Browser src={src}>
        {frame < ACTIONS + 28 && (
          <Pointer
            clickAt={[BIAS, ACTIONS]}
            path={[[0, 900, 600], [8, 900, 600], [BIAS - 4, 1489 * S, 198 * S + 4], [BIAS + 30, 1489 * S, 198 * S + 4], [ACTIONS - 4, 1611 * S, 198 * S + 4]]}
          />
        )}
      </Browser>
      <Sfx name="click" at={BIAS} volume={0.45} />
      <Sfx name="click" at={ACTIONS} volume={0.45} />
      {frame >= ACTIONS && <Callout x={1300} y={560} at={ACTIONS + 20}>Approved here, then into the Feedback report</Callout>}
      <DemoLabel />
      <Voice id="h1" lead={0.25} />
    </AbsoluteFill>
  );
}

/** q1: the admin presses Download PDF and the real report page flies out. */
function AdminExport() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const PDF = 74;
  const pdf = spring({ frame: frame - PDF - 6, fps, config: { damping: 14, stiffness: 110 } });
  return (
    <AbsoluteFill style={{ background: C.wall }}>
      <Role>college office</Role>
      <Browser src="feedback-report">
        {frame < PDF + 26 && <Pointer clickAt={[PDF]} path={[[0, 900, 700], [12, 900, 700], [PDF - 4, 1414 * S, 519 * S + 4]]} />}
      </Browser>
      <Sfx name="click" at={PDF} volume={0.45} />
      {frame > PDF && (
        <div style={{ position: "absolute", left: 1350, top: 120, opacity: Math.min(1, pdf * 2),
          transform: `translate(${(1 - pdf) * -200}px, ${(1 - pdf) * 260}px) rotate(${4 * pdf - 8 * (1 - pdf)}deg) scale(${0.4 + 0.6 * pdf})` }}>
          <Img src={staticFile("shots/feedback-report-pdf.png")} style={{ width: 430, borderRadius: 4, border: "1px solid #c3cfca",
            boxShadow: "0 30px 60px -16px rgba(22,32,30,0.6)" }} />
          <div style={{ marginTop: 14, fontFamily: FONT, fontSize: 26, fontWeight: 700, color: C.ink, textAlign: "center" }}>feedback report.pdf</div>
        </div>
      )}
      <Sfx name="swipe" at={PDF + 6} volume={0.3} />
      <DemoLabel />
      <Voice id="q1" lead={0.25} />
    </AbsoluteFill>
  );
}

/** p8: the closing card, on the last bars. */
function End() {
  const m = spring({ frame: useCurrentFrame() - 2, fps: FPS, config: { damping: 12, stiffness: 140 } });
  return (
    <AbsoluteFill style={{ background: C.board }}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 30 }}>
        <div style={{ transform: `scale(${0.5 + 0.5 * m}) rotate(${(1 - m) * -14}deg)`, opacity: Math.min(1, m * 1.5) }}>
          <Mark size={160} />
        </div>
        <Marker delay={10} size={120} color={C.onBoard}>FacultyLens</Marker>
        <Marker delay={30} size={60} color={C.highlight}>Every comment, sorted and heard.</Marker>
        <Text delay={72} size={34} color={C.onBoardMuted}>A B.Tech mini project by Rohnith, Varshith and Akhil</Text>
        <Text delay={82} size={30} color={C.onBoardMuted}>Maturi Venkata Subba Rao (MVSR) Engineering College</Text>
      </AbsoluteFill>
      <Sfx name="chime" at={6} volume={0.4} />
      <Sequence from={Math.round(0.6 * FPS)} layout="none">
        <Audio src={staticFile("audio/promo/p8.wav")} />
      </Sequence>
    </AbsoluteFill>
  );
}

const VIEWS = { p1: Hook, p2: Pile, p3: Snap, p4: Sort, p5: Redact, s1: Students, f1: TeacherPage, f2: Strengths, h1: HeadOfDepartment, q1: AdminExport, p8: End };

/** The beat, ducked under the voice so every word is clear, and faded out at the end. */
function Beat() {
  const voiced = SCENES.map(([id, , lead], i) => [starts[i] + lead * FPS, starts[i] + (lead + timings[id]) * FPS]);
  return (
    <Audio
      src={staticFile("sound/beat.wav")}
      volume={(f) => {
        const inVoice = voiced.some(([a, b]) => f >= a - 4 && f <= b + 4);
        const near = voiced.some(([a, b]) => f >= a - 10 && f <= b + 10);
        const base = inVoice ? 0.12 : near ? 0.26 : 0.5;
        const fadeOut = interpolate(f, [promoFrames - 40, promoFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return base * fadeOut;
      }}
    />
  );
}

export function Promo() {
  return (
    <FontGate>
      <AbsoluteFill style={{ background: C.wall }}>
        <Beat />
        <Series>
          {SCENES.map(([id, beats]) => {
            const View = VIEWS[id];
            return (
              <Series.Sequence key={id} durationInFrames={frames(beats)}>
                <View />
              </Series.Sequence>
            );
          })}
        </Series>
      </AbsoluteFill>
    </FontGate>
  );
}
