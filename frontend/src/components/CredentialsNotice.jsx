import { downloadText, toCsv } from "../lib/csv";

const COLUMNS = [
  { key: "name", label: "Name" },
  { key: "role", label: "Role" },
  { key: "login", label: "Sign in with" },
  { key: "temp_password", label: "Temporary password" },
];

/**
 * Temporary passwords are returned once by the API and never stored in plain text, so this
 * panel is the only place they appear. It stays until the admin confirms they saved them.
 */
export function CredentialsNotice({ credentials, onDone }) {
  const rows = credentials.map((c) => ({ ...c, login: c.email || c.roll_no }));
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");

  return (
    <section className="card" aria-labelledby="creds-h">
      <div className="flex flex-col gap-3 border-b border-rule px-[var(--card-pad)] py-4 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1">
          <h2 id="creds-h" className="m-0 text-section font-medium">
            {rows.length === 1 ? "Temporary password" : `${rows.length} temporary passwords`}
          </h2>
          <p className="m-0 text-small text-warning">
            Shown once. Download or copy them now; FacultyLens can&apos;t show them again. Each
            person must choose a new password at first sign-in.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() =>
              downloadText(`facultylens-credentials-${stamp}.csv`, toCsv(COLUMNS, rows))
            }
          >
            Download CSV
          </button>
          <button type="button" className="btn btn-secondary" onClick={onDone}>
            I&apos;ve saved them
          </button>
        </div>
      </div>
      <div className="max-h-80 overflow-auto">
        <table className="w-full border-collapse text-body">
          <thead>
            <tr className="text-left text-small text-muted">
              <th scope="col" className="h-9 px-[var(--card-pad)] font-medium">
                Name
              </th>
              <th scope="col" className="h-9 px-3 font-medium">
                Sign in with
              </th>
              <th scope="col" className="h-9 px-[var(--card-pad)] font-medium">
                Temporary password
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.login} className="border-t border-rule">
                <td className="h-10 px-[var(--card-pad)]">{r.name}</td>
                <td className="px-3 text-muted">{r.login}</td>
                <td className="px-[var(--card-pad)] font-mono text-[13px] select-all">
                  {r.temp_password}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
