/**
 * A part-of-whole bar at its true ratio, both ends labelled ("212 of 288"), in the one chart
 * hue. With nothing eligible it shows a dash instead of an empty bar.
 */
export function RateBar({ value, total, label = "responses" }) {
  if (!total) return <span className="text-faint">–</span>;
  const ratio = Math.min(1, value / total);
  const pct = Math.round(ratio * 100);
  return (
    <div className="flex min-w-40 flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 text-small">
        <span className="num">
          <span className="font-medium text-text">{value.toLocaleString("en-IN")}</span>
          <span className="text-muted">
            {" "}
            of {total.toLocaleString("en-IN")} {label}
          </span>
        </span>
        <span className="num text-muted">{pct}%</span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-active"
        role="img"
        aria-label={`${value} of ${total} ${label}, ${pct} percent`}
      >
        <div
          className="grow-x h-full rounded-full bg-chart-main"
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
    </div>
  );
}
