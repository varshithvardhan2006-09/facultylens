import { useEffect } from "react";

const MESSAGE = "You have unsaved changes. Leave this page and lose them?";

/** Warns before closing the tab or following a link while `dirty` is true. */
export function useUnsavedWarning(dirty) {
  useEffect(() => {
    if (!dirty) return undefined;
    const beforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const onClick = (e) => {
      const link = e.target.closest?.("a[href]");
      if (!link || link.target === "_blank" || e.metaKey || e.ctrlKey || e.shiftKey) return;
      if (new URL(link.href).pathname === window.location.pathname) return;
      if (!window.confirm(MESSAGE)) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [dirty]);
}

/** For buttons that would throw away the edits on screen. */
export function confirmDiscard(dirty) {
  return !dirty || window.confirm(MESSAGE);
}
