import { AbsoluteFill, Series, interpolate, useCurrentFrame } from "remotion";
import script from "../scripts/tech.json";
import timings from "../public/audio/tech/timings.json";
import {
  C,
  Chip,
  FONT,
  FontGate,
  Mark,
  Marker,
  Music,
  Note,
  Sfx,
  Shot,
  Text,
  Voice,
  Wall,
  sceneFrames,
  useIn,
} from "./kit";

const say = Object.fromEntries(script.map((s) => [s.id, s.say]));
const V = ({ id }) => <Voice src={`audio/tech/${id}.wav`} seconds={timings[id]} text={say[id]} />;
const f = (id, share) => Math.round(sceneFrames(timings[id]) * share); // a point in a scene, by share of its length

function Title({ children, sub }) {
  return (
    <div style={{ position: "absolute", left: 120, top: 80 }}>
      <Marker size={64}>{children}</Marker>
      {sub && <Text delay={10} size={30} color={C.muted} style={{ marginTop: 8 }}>{sub}</Text>}
    </div>
  );
}

/** A paper box in a diagram, rising in. */
function Box({ x, y, w, h, delay, title, lines = [], tone = "paper" }) {
  const p = useIn(delay, 18);
  const dark = tone === "board";
  return (
    <div style={{
      position: "absolute", left: x, top: y, width: w, height: h, padding: "28px 32px", borderRadius: 10,
      background: dark ? C.board : C.paper, color: dark ? C.onBoard : C.ink,
      border: dark ? "none" : "1px solid #c3cfca",
      boxShadow: "0 2px 4px rgba(22,32,30,0.1), 0 20px 40px -18px rgba(22,32,30,0.4)",
      opacity: p, transform: `translateY(${(1 - p) * 30}px)`, fontFamily: FONT,
    }}>
      <div style={{ fontWeight: 700, fontSize: 38 }}>{title}</div>
      {lines.map((l, i) => (
        <div key={i} style={{ fontSize: 28, marginTop: 12, color: dark ? C.onBoardMuted : C.muted }}>{l}</div>
      ))}
    </div>
  );
}

/** A connector drawn on like a pen stroke. */
function Arrow({ x1, y1, x2, y2, delay, label }) {
  const p = useIn(delay, 20);
  const len = Math.hypot(x2 - x1, y2 - y1);
  const ang = Math.atan2(y2 - y1, x2 - x1);
  return (
    <svg style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }} width="1920" height="1080">
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={C.ink} strokeWidth="4" strokeLinecap="round"
        strokeDasharray={len} strokeDashoffset={len * (1 - p)} />
      {p > 0.95 && (
        <path d={`M ${x2} ${y2} l ${-18 * Math.cos(ang - 0.45)} ${-18 * Math.sin(ang - 0.45)} M ${x2} ${y2} l ${-18 * Math.cos(ang + 0.45)} ${-18 * Math.sin(ang + 0.45)}`}
          stroke={C.ink} strokeWidth="4" strokeLinecap="round" fill="none" />
      )}
      {label && (
        <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 16} textAnchor="middle" fontFamily={FONT} fontSize="24" fill={C.muted} opacity={p}>{label}</text>
      )}
    </svg>
  );
}

function T1() {
  const m = useIn(2, 22);
  return (
    <Wall color={C.board}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 30 }}>
        <div style={{ opacity: m, transform: `scale(${0.85 + 0.15 * m})` }}><Mark size={130} /></div>
        <Marker delay={10} size={100} color={C.onBoard}>How FacultyLens works</Marker>
        <Text delay={40} size={36} color={C.onBoardMuted}>What it is built with, and what happens to every comment</Text>
      </AbsoluteFill>
      <Sfx name="chime" at={8} volume={0.35} />
      <V id="t1" />
    </Wall>
  );
}

function T2() {
  return (
    <Wall>
      <Title sub="Three parts, all running on an ordinary laptop">The big picture</Title>
      <Box x={120} y={360} w={480} h={300} delay={f("t2", 0.12)} title="Website" lines={["React, in the browser", "what people use"]} />
      <Box x={720} y={360} w={480} h={300} delay={f("t2", 0.28)} tone="board" title="API" lines={["Python, FastAPI", "rules, roles, NLP models"]} />
      <Box x={1320} y={360} w={480} h={300} delay={f("t2", 0.45)} title="Database" lines={["MongoDB", "users, forms, responses, results"]} />
      <Arrow x1={605} y1={510} x2={712} y2={510} delay={f("t2", 0.24)} />
      <Arrow x1={1205} y1={510} x2={1312} y2={510} delay={f("t2", 0.42)} />
      <div style={{ position: "absolute", left: 720, top: 720, display: "flex", gap: 16 }}>
        <Chip delay={f("t2", 0.7)} tone="here">CPU only, no graphics card</Chip>
      </div>
      <V id="t2" />
    </Wall>
  );
}

function T3() {
  const stack = ["React 18", "Vite", "React Router", "Tailwind CSS", "Recharts"];
  return (
    <Wall>
      <Title sub="The website">Frontend</Title>
      <div style={{ position: "absolute", left: 120, top: 300, display: "flex", flexDirection: "column", gap: 18 }}>
        {stack.map((s, i) => <Chip key={s} delay={f("t3", 0.04) + i * 8}>{s}</Chip>)}
      </div>
      <Shot src="faculty-wall" x={560} y={250} w={1240} delay={f("t3", 0.3)} zoom={[1, 1.08]} origin="55% 40%" />
      <div style={{ position: "absolute", left: 560, top: 980 - 40, display: "flex", gap: 16 }}>
        <Chip delay={f("t3", 0.78)} tone="board">WCAG AA contrast</Chip>
        <Chip delay={f("t3", 0.82)} tone="board">Keyboard friendly</Chip>
        <Chip delay={f("t3", 0.86)} tone="board">Dark mode</Chip>
      </div>
      <Sfx name="swipe" at={f("t3", 0.3)} volume={0.25} />
      <V id="t3" />
    </Wall>
  );
}

function T4() {
  const stack = ["Python 3.13", "FastAPI", "Pydantic", "Short-lived sign-in tokens", "bcrypt passwords", "Rate-limited sign-in"];
  const roles = [["Student", "neutral"], ["Faculty", "praise"], ["Head of department", "praise"], ["IQAC admin", "criticism"]];
  return (
    <Wall>
      <Title sub="The API">Backend</Title>
      <div style={{ position: "absolute", left: 120, top: 300, display: "flex", flexWrap: "wrap", gap: 18, width: 820 }}>
        {stack.map((s, i) => <Chip key={s} delay={f("t4", 0.05) + i * 9}>{s}</Chip>)}
      </div>
      <div style={{ position: "absolute", left: 1040, top: 270 }}>
        <Text delay={f("t4", 0.55)} size={34} weight={700}>Four roles, checked on every request</Text>
      </div>
      {roles.map(([r, k], i) => (
        <Note key={r} kind={k} x={1040 + (i % 2) * 380} y={360 + Math.floor(i / 2) * 230} w={340} tilt={i % 2 ? 1.5 : -1.5}
          delay={f("t4", 0.6) + i * 8} size={32} from={[60, 120, 6]}>
          <b>{r}</b>
        </Note>
      ))}
      {roles.map((_, i) => <Sfx key={i} name="pin" at={f("t4", 0.62) + i * 8} volume={0.22} />)}
      <V id="t4" />
    </Wall>
  );
}

function T5() {
  const code = useIn(f("t5", 0.62), 20);
  return (
    <Wall>
      <Title sub="Step 1: a student submits">The journey of one comment</Title>
      <Shot src="student-form" x={120} y={260} w={980} delay={4} zoom={[1, 1.1]} origin="50% 30%" />
      <Note kind="neutral" x={1220} y={290} w={560} tilt={-1.2} delay={f("t5", 0.38)} size={30}>
        <b>Saved without a name</b>
        <div style={{ marginTop: 10, fontSize: 26, color: C.muted }}>ratings 1 to 5, and a few lines of comment</div>
      </Note>
      <div style={{ position: "absolute", left: 1220, top: 560, width: 560, padding: 26, borderRadius: 10, background: C.board,
        color: C.onBoard, fontFamily: '"Cascadia Mono", Consolas, monospace', fontSize: 26, lineHeight: 1.5, opacity: code,
        transform: `translateY(${(1 - code) * 24}px)` }}>
        code = HMAC(secret,<br />&nbsp;&nbsp;student + form)
        <div style={{ fontFamily: FONT, fontSize: 24, marginTop: 12, color: C.onBoardMuted }}>Only stops a second submission</div>
      </div>
      <V id="t5" />
    </Wall>
  );
}

function Step({ x, delay, n, title, body }) {
  return (
    <Note kind="neutral" x={x} y={330} w={500} tilt={n % 2 ? 1.2 : -1.2} delay={delay} size={30} from={[-200, 0, -6]}>
      <div style={{ fontWeight: 700 }}>{n}. {title}</div>
      <div style={{ marginTop: 12, fontSize: 25, color: C.muted }}>{body}</div>
    </Note>
  );
}

function T6() {
  const frame = useCurrentFrame();
  const redact = frame > f("t6", 0.55);
  return (
    <Wall>
      <Title sub="Step 2: in the background, right after submitting">Clean, redact, split</Title>
      <Step x={120} n={1} delay={f("t6", 0.1)} title="Clean" body="quotes, contractions, stretched words like sooo" />
      <Step x={700} n={2} delay={f("t6", 0.28)} title="Redact" body="our rules: phones, emails, MVSR roll numbers; spaCy: names" />
      <Step x={1280} n={3} delay={f("t6", 0.82)} title="Split" body="into sentences, keeping each position for highlights" />
      <div style={{ position: "absolute", left: 120, top: 700, width: 1680, padding: "26px 32px", borderRadius: 10,
        background: C.paper, border: "1px solid #c3cfca", fontFamily: FONT, fontSize: 34, opacity: useIn(f("t6", 0.4), 16) }}>
        {redact
          ? <><R>[FACULTY]</R> mam, call me on <R>[PHONE]</R> about the internals. My roll number is <R>[ROLL]</R>.</>
          : <>Kavitha mam, call me on 98480 12345 about the internals. My roll number is 2451-24-751-999.</>}
        <div style={{ marginTop: 10, fontSize: 22, color: C.muted }}>Real output of the redaction step</div>
      </div>
      <Sfx name="swipe" at={f("t6", 0.55)} volume={0.3} />
      <V id="t6" />
    </Wall>
  );
}

function R({ children }) {
  return <span style={{ background: C.board, color: C.onBoard, padding: "0 10px", borderRadius: 6, fontSize: "0.82em", fontWeight: 600 }}>{children}</span>;
}

function Bar({ label, value, color, delay, y }) {
  const p = useIn(delay, 26);
  return (
    <div style={{ position: "absolute", left: 1060, top: y, width: 720, fontFamily: FONT }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 28, color: C.ink }}>
        <span>{label}</span><span style={{ fontVariantNumeric: "tabular-nums" }}>{(value * p).toFixed(2)}</span>
      </div>
      <div style={{ height: 16, marginTop: 8, borderRadius: 8, background: "#cfdad5" }}>
        <div style={{ height: 16, width: `${value * p * 100}%`, borderRadius: 8, background: color }} />
      </div>
    </div>
  );
}

function T7() {
  const models = [
    ["Abuse", "unitary/unbiased-toxic-roberta"],
    ["Sentiment", "cardiffnlp/twitter-roberta-base-sentiment-latest"],
    ["Emotion", "j-hartmann/emotion-english-distilroberta-base"],
    ["Sarcasm", "cardiffnlp/twitter-roberta-base-irony"],
  ];
  return (
    <Wall>
      <Title sub="Step 3: pre-trained transformers read every sentence">The models</Title>
      {models.map(([task, id], i) => (
        <div key={task} style={{ position: "absolute", left: 120, top: 290 + i * 150, fontFamily: FONT, opacity: useIn(f("t7", 0.08) + i * 10, 14) }}>
          <div style={{ fontSize: 36, fontWeight: 700 }}>{task}</div>
          <div style={{ fontSize: 24, color: C.muted, fontFamily: '"Cascadia Mono", Consolas, monospace' }}>{id}</div>
        </div>
      ))}
      <Note kind="praise" x={1060} y={250} w={720} tilt={-1} delay={f("t7", 0.3)} size={32}>
        "Very knowledgeable, answers even tricky questions."
      </Note>
      <Bar label="Abuse" value={0.0} color={C.edgeCriticism} delay={f("t7", 0.4)} y={500} />
      <Bar label="Positive sentiment" value={0.96} color={C.edgePraise} delay={f("t7", 0.5)} y={590} />
      <Bar label="Emotion: neutral" value={0.94} color="#7c8582" delay={f("t7", 0.6)} y={680} />
      <Bar label="Sarcasm (flagged only above 0.95)" value={0.71} color="#7c8582" delay={f("t7", 0.7)} y={770} />
      <div style={{ position: "absolute", left: 1060, top: 880, fontFamily: FONT, fontSize: 22, color: C.muted, opacity: useIn(f("t7", 0.75), 12) }}>
        Real scores from the models in FacultyLens
      </div>
      <V id="t7" />
    </Wall>
  );
}

/** Embeddings: the sentence as a point, pulled to the nearest aspect prototype. */
function T8() {
  const frame = useCurrentFrame();
  const aspects = [
    ["Subject knowledge", 240, 360], ["Clarity", 640, 300], ["Punctuality", 1040, 380], ["Interaction", 1440, 320],
    ["Examples", 300, 700], ["Assessment", 700, 760], ["Behaviour", 1100, 700], ["Pace", 1500, 760],
  ];
  // The sentence's point travels from the note to the nearest prototype, Clarity.
  const land = useIn(f("t8", 0.45), 30);
  const sx = 960 + (640 - 960) * land;
  const sy = 470 + (311 - 470) * land;
  const verdict = useIn(f("t8", 0.78), 16);
  return (
    <Wall>
      <Title sub="Our own zero-shot method">Which teaching aspect?</Title>
      {aspects.map(([name, x, y], i) => (
        <div key={name} style={{ position: "absolute", left: x - 90, top: y - 30, width: 220, textAlign: "center", opacity: useIn(f("t8", 0.12) + i * 4, 12) }}>
          <div style={{ width: 22, height: 22, borderRadius: 11, margin: "0 auto 10px", background: name === "Clarity" ? C.edgePraise : "#9aa8a3" }} />
          <div style={{ fontFamily: '"Kalam"', fontWeight: 700, fontSize: 30, color: C.ink }}>{name}</div>
        </div>
      ))}
      {frame > f("t8", 0.45) && (
        <div style={{ position: "absolute", left: sx - 14, top: sy - 14, width: 28, height: 28, borderRadius: 14,
          background: C.highlight, border: `3px solid ${C.ink}` }} />
      )}
      {frame > f("t8", 0.3) && (
        <div style={{ position: "absolute", left: 680, top: 490, width: 560 }}>
          <Note kind="neutral" x={0} y={0} w={560} tilt={0} delay={f("t8", 0.3)} size={26} from={[0, 40, 0]}>
            "Explains every topic clearly, easy to understand."
            <div style={{ marginTop: 10, fontSize: 24, fontWeight: 700, color: C.edgePraise, opacity: verdict }}>Clarity (similarity 0.67), praised 0.997</div>
          </Note>
        </div>
      )}
      <Sfx name="pin" at={f("t8", 0.75)} volume={0.3} />
      <V id="t8" />
    </Wall>
  );
}

function T9() {
  return (
    <Wall>
      <Title sub="So it runs on any college computer">CPU first</Title>
      <Shot src="status" x={120} y={260} w={1100} delay={4} zoom={[1, 1.15]} origin="40% 75%" />
      <div style={{ position: "absolute", left: 1300, top: 300, display: "flex", flexDirection: "column", gap: 22 }}>
        <Chip delay={f("t9", 0.1)} tone="here">Load on first use</Chip>
        <Chip delay={f("t9", 0.4)}>Small batches on the CPU</Chip>
        <Chip delay={f("t9", 0.62)}>Results saved by model version</Chip>
        <Chip delay={f("t9", 0.8)}>Never analysed twice</Chip>
      </div>
      <V id="t9" />
    </Wall>
  );
}

function T10() {
  return (
    <Wall>
      <Title sub="The counts decide; the LLM only writes the words">Grounded summaries</Title>
      <Shot src="faculty-wall" x={120} y={270} w={1000} delay={4} zoom={[1, 1.05]} origin="40% 60%" />
      <Note kind="praise" x={1220} y={290} w={580} tilt={-1.2} delay={f("t10", 0.25)} size={28}>
        <b>Strength: Subject knowledge</b>
        <div style={{ marginTop: 10, fontSize: 24, color: C.muted }}>cites the comments behind it</div>
      </Note>
      <Note kind="criticism" x={1220} y={520} w={580} tilt={1.4} delay={f("t10", 0.38)} size={28}>
        <b>To improve: Pace</b>
        <div style={{ marginTop: 10, fontSize: 24, color: C.muted }}>cites the comments behind it</div>
      </Note>
      <div style={{ position: "absolute", left: 1220, top: 780, display: "flex", gap: 14, flexWrap: "wrap", width: 600 }}>
        <Chip delay={f("t10", 0.55)} tone="board">Groq LLM writes</Chip>
        <Chip delay={f("t10", 0.85)}>Local fallback: distilBART</Chip>
      </div>
      <V id="t10" />
    </Wall>
  );
}

function T11() {
  const rules = [
    ["praise", "Teachers see only moderated, redacted text"],
    ["neutral", "Nothing shown under 5 responses"],
    ["criticism", "Bias check by department, never one teacher"],
  ];
  return (
    <Wall>
      <Title>Privacy by design</Title>
      {rules.map(([k, t], i) => (
        <Note key={t} kind={k} x={120 + i * 590} y={330} w={540} tilt={[-1.6, 1.2, -0.8][i]} delay={f("t11", 0.12) + i * 22} size={34} from={[0, 200, 8]}>
          {t}
        </Note>
      ))}
      {rules.map((_, i) => <Sfx key={i} name="pin" at={f("t11", 0.14) + i * 22} volume={0.25} />)}
      <Shot src="bias" x={460} y={590} w={1000} delay={f("t11", 0.6)} crop={300} zoom={[1, 1.04]} origin="50% 20%" />
      <V id="t11" />
    </Wall>
  );
}

function T12() {
  return (
    <Wall>
      <Title sub="Real numbers only, from our own evaluation">Does it work?</Title>
      <Shot src="evaluation" x={120} y={260} w={1100} delay={4} zoom={[1, 1.12]} origin="50% 70%" />
      <div style={{ position: "absolute", left: 1300, top: 280, display: "flex", flexDirection: "column", gap: 20 }}>
        <Chip delay={f("t12", 0.12)}>Baselines: VADER, TF-IDF</Chip>
        <Chip delay={f("t12", 0.3)}>vs the transformer</Chip>
        <Chip delay={f("t12", 0.5)}>Cohen's kappa</Chip>
        <Chip delay={f("t12", 0.62)}>ROUGE, BERTScore</Chip>
        <Chip delay={f("t12", 0.8)} tone="here">555 automated tests</Chip>
      </div>
      <V id="t12" />
    </Wall>
  );
}

function T13() {
  const m = useIn(4, 24);
  return (
    <Wall color={C.board}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 32 }}>
        <div style={{ opacity: m, transform: `scale(${0.85 + 0.15 * m})` }}><Mark size={140} /></div>
        <Marker delay={12} size={104} color={C.onBoard}>FacultyLens</Marker>
        <Marker delay={36} size={54} color={C.onBoard}>Every comment, sorted and heard.</Marker>
        <Text delay={80} size={34} color={C.onBoardMuted}>Built by Rohnith, Varshith and Akhil</Text>
        <Text delay={90} size={30} color={C.onBoardMuted}>Maturi Venkata Subba Rao (MVSR) Engineering College</Text>
      </AbsoluteFill>
      <Sfx name="chime" at={10} volume={0.4} />
      <V id="t13" />
    </Wall>
  );
}

const SCENES = [
  ["t1", T1], ["t2", T2], ["t3", T3], ["t4", T4], ["t5", T5], ["t6", T6], ["t7", T7],
  ["t8", T8], ["t9", T9], ["t10", T10], ["t11", T11], ["t12", T12], ["t13", T13],
];

export const techFrames = SCENES.reduce((n, [id]) => n + sceneFrames(timings[id]), 0);

export function Tech() {
  return (
    <FontGate>
      <AbsoluteFill style={{ background: C.wall }}>
        <Music volume={0.1} />
        <Series>
          {SCENES.map(([id, Scene]) => (
            <Series.Sequence key={id} durationInFrames={sceneFrames(timings[id])}>
              <Scene />
              <Sfx name="swipe" at={0} volume={id === "t1" ? 0 : 0.16} />
            </Series.Sequence>
          ))}
        </Series>
      </AbsoluteFill>
    </FontGate>
  );
}
