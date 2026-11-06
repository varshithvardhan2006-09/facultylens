/** Minimal CSV writer (RFC 4180 quoting) and a browser download helper. */
function cell(value) {
  const raw = value === null || value === undefined ? "" : String(value);
  // A spreadsheet would run a cell starting with one of these as a formula.
  const text = /^[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw;
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function toCsv(columns, rows) {
  const lines = [columns.map((c) => cell(c.label)).join(",")];
  for (const row of rows) lines.push(columns.map((c) => cell(row[c.key])).join(","));
  return lines.join("\r\n") + "\r\n";
}

export function downloadText(filename, text, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob(["﻿", text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const BULK_TEMPLATE =
  "name,email,role,department_code,roll_no,gender\r\n" +
  "Dr. Anita Rao,anita.rao@college.edu,faculty,CSE,,female\r\n" +
  "Meena K,,student,CSE,2451-24-733-011,\r\n";
