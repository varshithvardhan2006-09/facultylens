import { useCallback } from "react";
import { getHealth, getModelHealth } from "../api/client";
import { useAsync } from "../hooks/useAsync";

const TASK_LABELS = {
  sentiment: "Overall sentiment",
  embeddings: "Aspect detection (embeddings)",
  absa: "Aspect polarity",
  toxicity: "Moderation (toxicity)",
  emotion: "Emotion",
  irony: "Sarcasm / irony",
  summarizer: "Summary fallback (no LLM)",
  ner: "PII names (spaCy NER)",
};

const fmt = (n, digits = 0) =>
  n === null || n === undefined
    ? null
    : n.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function Dash() {
  return (
    <span className="text-faint" aria-label="not measured yet">
      –
    </span>
  );
}

function Num({ value, digits, unit }) {
  const text = fmt(value, digits);
  if (text === null) return <Dash />;
  return (
    <span className="num">
      {text}
      {unit && <span className="ml-0.5 text-small text-muted">{unit}</span>}
    </span>
  );
}

function loadStatus(health, models) {
  if (health.error) return { tone: "negative", text: "API unreachable" };
  if (!health.data) return null;
  if (health.data.mongo !== "ok") return { tone: "negative", text: "Database unreachable" };
  if (models.error) return { tone: "warning", text: "Model status unavailable" };
  return { tone: "positive", text: "Ready" };
}

function finding(health, models) {
  if (health.error)
    return "The browser could not reach /api. Start the API with uvicorn on port 8000, then retry.";
  if (!health.data) return null;
  if (health.data.mongo !== "ok")
    return "The API is up but MongoDB did not answer a ping at the configured address. Start the MongoDB service, then retry.";
  if (models.error) return "The API is up, but the model status couldn't be read. Retry.";
  if (!models.data) return null;
  const { loaded_count, models: rows } = models.data;
  const llm = health.data.llm_configured
    ? "Summaries and profiles use Groq."
    : "No Groq key is set, so summaries and profiles use the no-LLM fallback.";
  return `API and database are reachable. ${loaded_count} of ${rows.length} models are loaded in this process; the rest load on first use. ${llm}`;
}

function ServiceStrip({ health, models }) {
  const h = health.data;
  const m = models.data;
  const cells = [
    {
      label: "API",
      value: h ? `FastAPI ${h.version}` : null,
    },
    {
      label: "Database",
      value: h ? (
        <span className={`pill ${h.mongo === "ok" ? "pill-positive" : "pill-negative"}`}>
          MongoDB {h.mongo === "ok" ? "connected" : "unreachable"}
        </span>
      ) : null,
    },
    {
      label: "ML mode",
      value: m ? `${m.ml_mode} · ${m.torch_num_threads} CPU threads` : null,
    },
    {
      label: "LLM",
      value: h ? (h.llm_configured ? "Groq configured" : "No-LLM fallback") : null,
    },
    {
      label: "API process memory",
      value: m ? <Num value={m.process_rss_mb} digits={0} unit="MB" /> : null,
    },
  ];
  return (
    <section aria-labelledby="services-h" className="flex flex-col gap-2">
      <h2 id="services-h" className="text-section font-medium">
        Services
      </h2>
      {/* Dividers are the 1px grid gap showing the rule colour, so they stay right at any column count. */}
      <dl className="card m-0 grid grid-cols-2 gap-px overflow-hidden bg-rule xl:grid-cols-5">
        {cells.map((c, i) => (
          <div
            key={c.label}
            className={`flex min-h-[84px] flex-col gap-1.5 bg-surface p-[var(--card-pad)] ${
              i === cells.length - 1 ? "max-xl:col-span-2" : ""
            }`}
          >
            <dt className="text-small text-muted">{c.label}</dt>
            <dd className="m-0 text-lead font-medium">
              {c.value ??
                (health.error || models.error ? <Dash /> : <span className="skeleton h-6 w-32" />)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ModelTable({ models }) {
  const m = models.data;
  return (
    <section aria-labelledby="models-h" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="models-h" className="text-section font-medium">
          Models
        </h2>
        {m && (
          <p className="m-0 text-small text-muted">
            Version <span className="font-mono">{m.model_version}</span> ·{" "}
            <Num value={m.system_available_mb} unit="MB" /> RAM free on this machine
          </p>
        )}
      </div>
      <div className="card overflow-hidden">
        {models.error ? (
          <p className="m-0 flex flex-wrap items-center gap-3 p-[var(--card-pad)] text-body">
            <span className="pill pill-negative">Failed</span>
            Couldn&apos;t load model status from /api/health/models.
            <button type="button" className="btn btn-ghost h-8 px-2" onClick={models.reload}>
              Retry
            </button>
          </p>
        ) : (
          <table className="w-full border-collapse text-body">
            <thead className="max-md:sr-only">
              <tr className="text-left text-small text-muted">
                <th scope="col" className="h-10 px-[var(--card-pad)] font-medium">
                  Task
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Model
                </th>
                <th scope="col" className="h-10 px-3 font-medium">
                  Status
                </th>
                <th scope="col" className="h-10 px-3 text-right font-medium">
                  Load time
                </th>
                <th scope="col" className="h-10 px-3 text-right font-medium">
                  Avg per item
                </th>
                <th
                  scope="col"
                  className="h-10 px-[var(--card-pad)] text-right font-medium max-lg:hidden"
                >
                  Calls
                </th>
              </tr>
            </thead>
            <tbody>
              {(m?.models ?? Array.from({ length: 8 }, () => null)).map((row, i) =>
                row ? (
                  <tr
                    key={row.task}
                    className="border-t border-rule max-md:grid max-md:grid-cols-[1fr_auto] max-md:gap-x-3 max-md:gap-y-0.5 max-md:px-4 max-md:py-3"
                  >
                    <td className="h-[var(--row-height)] px-[var(--card-pad)] font-medium max-md:h-auto max-md:p-0">
                      {TASK_LABELS[row.task] ?? row.task}
                    </td>
                    <td className="px-3 font-mono text-[13px] leading-5 text-muted max-md:order-3 max-md:col-span-2 max-md:p-0 max-md:break-all">
                      {row.model_id}
                    </td>
                    <td className="px-3 max-md:order-2 max-md:row-span-1 max-md:p-0 max-md:text-right">
                      <span className={`pill ${row.loaded ? "pill-positive" : "pill-neutral"}`}>
                        {row.loaded ? "Loaded" : "Not loaded"}
                      </span>
                    </td>
                    <td className="px-3 text-right max-md:hidden">
                      <Num value={row.load_seconds} digits={1} unit="s" />
                    </td>
                    <td className="px-3 text-right max-md:hidden">
                      <Num value={row.avg_ms_per_item} digits={1} unit="ms" />
                    </td>
                    <td className="px-[var(--card-pad)] text-right max-lg:hidden">
                      <Num value={row.calls} />
                    </td>
                  </tr>
                ) : (
                  <tr key={i} className="border-t border-rule">
                    <td className="h-[var(--row-height)] px-[var(--card-pad)]" colSpan={6}>
                      <span className="skeleton h-4 w-full max-w-[560px]" />
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        )}
      </div>
      <p className="m-0 text-small text-muted">
        Models load lazily on first use, once per process. CPU timings for this machine are in
        docs/MODEL_CHECK.md.
      </p>
    </section>
  );
}

export function StatusPage() {
  const health = useAsync(getHealth);
  const models = useAsync(getModelHealth);
  const status = loadStatus(health, models);
  const sentence = finding(health, models);
  const busy = health.loading || models.loading || health.refreshing || models.refreshing;
  const checkedAt = health.checkedAt ?? models.checkedAt;

  const refresh = useCallback(() => {
    health.reload();
    models.reload();
  }, [health, models]);

  return (
    <div className="mx-auto flex max-w-[1184px] flex-col gap-10">
      <header className="board flex flex-col gap-4 px-[var(--card-pad)] py-5 md:flex-row md:items-center md:justify-between md:gap-8 md:px-6">
        <div className="flex max-w-[72ch] flex-col gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="m-0 font-marker text-marker">System status</h1>
            {status && (
              <span className={`pill pill-${status.tone}`} role="status">
                {status.text}
              </span>
            )}
          </div>
          <p className="m-0 min-h-10 text-body text-on-board-muted" aria-live="polite">
            {sentence ?? <span className="skeleton h-4 w-[420px] max-w-full" />}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {checkedAt && (
            <span className="num text-small text-on-board-muted">
              Checked {checkedAt.toLocaleTimeString("en-IN", { hour12: false })}
            </span>
          )}
          <button type="button" className="btn btn-primary" onClick={refresh} disabled={busy}>
            {busy ? "Checking…" : "Refresh"}
          </button>
        </div>
      </header>

      <ServiceStrip health={health} models={models} />
      <ModelTable models={models} />
    </div>
  );
}
