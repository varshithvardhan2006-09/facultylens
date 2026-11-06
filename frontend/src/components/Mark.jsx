/** FacultyLens mark: two tilted notes, praise over criticism, taped to the deep board. */
export function Mark({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="7" fill="var(--board)" />
      <g transform="rotate(-7 13 18)">
        <rect x="6" y="11" width="15" height="14" rx="1.5" fill="var(--note-criticism)" />
      </g>
      <g transform="rotate(6 19 13)">
        <rect x="11.5" y="6" width="15" height="14" rx="1.5" fill="var(--note-praise)" />
        <rect x="16" y="4.2" width="7" height="3" rx="0.6" fill="var(--highlight)" />
      </g>
    </svg>
  );
}
