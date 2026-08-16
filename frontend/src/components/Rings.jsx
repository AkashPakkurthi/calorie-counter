import { fmt } from "./ui.jsx";

/** Hero number with a progress ring. The ring is the headline, so it gets a
 *  direct label rather than a legend. */
export function CalorieRing({ consumed, target, burned, net }) {
  const size = 190;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = target > 0 ? Math.min(consumed / target, 1) : 0;
  const over = target > 0 && consumed > target;
  const color = over ? "var(--color-over)" : "var(--color-series-1)";
  const remaining = Math.round(target - consumed);

  return (
    <div className="flex flex-col items-center gap-3 sm:flex-row sm:gap-6">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-ink-800)"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - pct)}
            style={{ transition: "stroke-dashoffset .5s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="tnum text-4xl font-semibold">{fmt(consumed)}</span>
          <span className="text-xs text-ink-500">of {fmt(target)} kcal</span>
          <span
            className={`mt-1 tnum text-sm font-medium ${
              over ? "text-over" : "text-good"
            }`}
          >
            {over ? `${fmt(-remaining)} over` : `${fmt(remaining)} left`}
          </span>
        </div>
      </div>

      <dl className="grid w-full grid-cols-3 gap-2 text-center sm:text-left">
        <Stat label="Eaten" value={fmt(consumed)} unit="kcal" />
        <Stat label="Burned" value={fmt(burned)} unit="kcal" tone="text-series-3" />
        <Stat label="Net" value={fmt(net)} unit="kcal" />
      </dl>
    </div>
  );
}

function Stat({ label, value, unit, tone = "" }) {
  return (
    <div className="rounded-xl bg-ink-850 px-3 py-2">
      <dt className="text-[11px] tracking-wide text-ink-500 uppercase">{label}</dt>
      <dd className={`tnum text-lg font-semibold ${tone}`}>
        {value} <span className="text-xs font-normal text-ink-500">{unit}</span>
      </dd>
    </div>
  );
}

export function MacroBar({ label, value, target, unit = "g", color }) {
  const pct = target > 0 ? Math.min((value / target) * 100, 100) : 0;
  const over = target > 0 && value > target;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="flex items-center gap-1.5 text-ink-300">
          <span
            className="h-2.5 w-2.5 rounded-sm"
            style={{ background: color }}
            aria-hidden
          />
          {label}
        </span>
        <span className="tnum text-ink-100">
          {Math.round(value)}
          <span className="text-ink-500">
            /{Math.round(target)}
            {unit}
          </span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ink-800">
        <div
          className="h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: over ? "var(--color-over)" : color,
            transition: "width .4s ease",
          }}
        />
      </div>
    </div>
  );
}

export function MicroStat({ label, value, unit }) {
  return (
    <div className="rounded-xl bg-ink-850 px-3 py-2">
      <div className="text-[11px] tracking-wide text-ink-500 uppercase">{label}</div>
      <div className="tnum text-base font-semibold">
        {Math.round(value)}
        <span className="ml-0.5 text-xs font-normal text-ink-500">{unit}</span>
      </div>
    </div>
  );
}
