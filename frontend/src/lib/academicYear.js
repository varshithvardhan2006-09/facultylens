/** "2026-27" for dates from June onwards (Indian academic years start in June/July). */
export function currentAcademicYear(date = new Date()) {
  const start = date.getMonth() >= 5 ? date.getFullYear() : date.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}
