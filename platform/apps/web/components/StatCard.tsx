export function StatCard({
  label,
  value,
  accent = "jade",
  sublabel,
}: {
  label: string;
  value: string;
  accent?: "jade" | "ember" | "gold";
  sublabel?: string;
}) {
  const accentClass = { jade: "text-jade-400", ember: "text-ember-400", gold: "text-gold-400" }[accent];

  return (
    <div className="panel p-5">
      <p className="label">{label}</p>
      <p className={`stat-value ${accentClass}`}>{value}</p>
      {sublabel && <p className="mt-1 text-xs text-ink-400">{sublabel}</p>}
    </div>
  );
}
