import { useId } from "react";
import { useTheme } from "../context/theme";

const OPTIONS = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

/** Three-way segmented control (a radio group, so arrow keys move between options). */
export function ThemeSwitch({ onBoard = false }) {
  const { theme, setTheme } = useTheme();
  const name = useId();
  return (
    <fieldset className="m-0 border-0 p-0">
      <legend className={`mb-1.5 text-small ${onBoard ? "text-on-board-muted" : "text-muted"}`}>
        Theme
      </legend>
      <div
        className={`grid grid-cols-3 gap-0.5 rounded-button p-0.5 ${onBoard ? "bg-board-2" : "bg-active"}`}
      >
        {OPTIONS.map((o) => (
          <label
            key={o.value}
            className={`flex h-7 cursor-pointer items-center justify-center rounded-button text-small font-semibold transition-colors duration-150 has-[:focus-visible]:outline-2 ${onBoard ? "has-[:focus-visible]:outline-[var(--highlight)]" : "has-[:focus-visible]:outline-focus"} ${
              theme === o.value
                ? "bg-surface text-text"
                : onBoard
                  ? "text-on-board-muted hover:text-on-board"
                  : "text-muted hover:text-text"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={theme === o.value}
              onChange={() => setTheme(o.value)}
              className="sr-only"
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
