import { useEffect, useRef, useState } from "react";

/**
 * Holds the notes inside it until the group scrolls into view, then lets them settle (once).
 * Groups already on screen settle straight away; without IntersectionObserver they never wait.
 * `ready` holds off watching until the content is in, so a loading placeholder that happens to
 * be on screen does not count as "seen". `threshold` and `rootMargin` make a group wait until it
 * is further into view (the landing page waits until its notes reach the upper part of the screen).
 */
export function Reveal({
  as: Tag = "div",
  ready = true,
  threshold = 0.15,
  rootMargin = "0px",
  afterScroll = false,
  className = "",
  children,
  ...rest
}) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === "undefined");
  // afterScroll: on a page that scrolls, nothing counts as seen until the reader has scrolled.
  const [scrolled, setScrolled] = useState(!afterScroll);

  useEffect(() => {
    if (scrolled) return undefined;
    const go = () => setScrolled(true);
    const scrollable = document.documentElement.scrollHeight > window.innerHeight + 40;
    const id = scrollable ? null : setTimeout(go, 0);
    window.addEventListener("scroll", go, { once: true, passive: true });
    return () => {
      clearTimeout(id);
      window.removeEventListener("scroll", go);
    };
  }, [scrolled]);

  useEffect(() => {
    const node = ref.current;
    if (seen || !ready || !scrolled || !node) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [seen, ready, scrolled, threshold, rootMargin]);

  return (
    <Tag ref={ref} data-reveal="" className={`${className} ${seen ? "in-view" : ""}`} {...rest}>
      {children}
    </Tag>
  );
}
