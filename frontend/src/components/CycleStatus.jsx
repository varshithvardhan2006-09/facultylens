const STATUS = {
  draft: ["pill-neutral", "Draft"],
  open: ["pill-positive", "Open"],
  closed: ["pill-neutral", "Closed"],
};

export function CycleStatus({ status }) {
  const [cls, text] = STATUS[status] ?? STATUS.draft;
  return <span className={`pill ${cls}`}>{text}</span>;
}
