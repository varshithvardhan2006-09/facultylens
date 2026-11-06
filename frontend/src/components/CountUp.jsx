import { useEffect, useState } from "react";

const DURATION = 700;
const still = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * A number that counts up to its value once, on a strong ease-out. Screen readers get the
 * final value straight away; with reduced motion the number simply appears.
 */
export function CountUp({ value, format = (v) => String(Math.round(v)) }) {
  const animate = typeof value === "number" && !still();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!animate) return undefined;
    let frame;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / DURATION);
      setShown(value * (1 - (1 - t) ** 3));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, animate]);

  return (
    <>
      <span aria-hidden="true">{format(animate ? shown : value)}</span>
      <span className="sr-only">{format(value)}</span>
    </>
  );
}
