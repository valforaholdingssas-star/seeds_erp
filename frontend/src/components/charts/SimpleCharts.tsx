type SeriesPoint = { label: string; value: number; color?: string };

const SEEDS = ["#112918", "#62986C", "#93403A", "#5E0604", "#CA9697", "#1D2D1B"];

export function BarChart({
  series,
  height = 180,
}: {
  series: SeriesPoint[];
  height?: number;
}) {
  const max = Math.max(...series.map((s) => s.value), 1);
  const barW = Math.max(12, Math.floor(280 / Math.max(series.length, 1)) - 6);
  const width = Math.max(280, series.length * (barW + 10));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img">
      {series.map((s, i) => {
        const h = (s.value / max) * (height - 40);
        const x = i * (barW + 10) + 8;
        const y = height - 28 - h;
        return (
          <g key={s.label}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={h}
              rx={6}
              fill={s.color || SEEDS[i % SEEDS.length]}
            />
            <text
              x={x + barW / 2}
              y={height - 10}
              textAnchor="middle"
              className="fill-current"
              style={{ fontSize: 9, fill: "#6B7280" }}
            >
              {s.label.slice(0, 8)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function LineChart({
  points,
  height = 180,
  seriesKeys,
}: {
  points: Array<Record<string, string | number>>;
  height?: number;
  seriesKeys: Array<{ key: string; color: string; label: string }>;
}) {
  const width = 520;
  const pad = 24;
  const values = points.flatMap((p) =>
    seriesKeys.map((s) => Number(p[s.key] || 0)),
  );
  const max = Math.max(...values, 1);
  const step = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0;

  function pathFor(key: string) {
    return points
      .map((p, i) => {
        const x = pad + i * step;
        const y = height - pad - (Number(p[key] || 0) / max) * (height - pad * 2);
        return `${i === 0 ? "M" : "L"}${x},${y}`;
      })
      .join(" ");
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img">
      {seriesKeys.map((s) => (
        <path
          key={s.key}
          d={pathFor(s.key)}
          fill="none"
          stroke={s.color}
          strokeWidth={2.2}
          strokeLinejoin="round"
        />
      ))}
      <g transform={`translate(${pad},12)`}>
        {seriesKeys.map((s, i) => (
          <g key={s.key} transform={`translate(${i * 110},0)`}>
            <rect width={10} height={10} rx={2} fill={s.color} />
            <text x={14} y={9} style={{ fontSize: 10, fill: "#6B7280" }}>
              {s.label}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}

export function DonutChart({
  series,
  size = 180,
}: {
  series: SeriesPoint[];
  size?: number;
}) {
  const total = series.reduce((a, s) => a + s.value, 0) || 1;
  const r = 60;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex items-center gap-6">
      <svg viewBox="0 0 160 160" width={size} height={size} role="img">
        <g transform="translate(80,80)">
          {series.map((s, i) => {
            const len = (s.value / total) * c;
            const el = (
              <circle
                key={s.label}
                r={r}
                fill="transparent"
                stroke={s.color || SEEDS[i % SEEDS.length]}
                strokeWidth={22}
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
                transform="rotate(-90)"
              />
            );
            offset += len;
            return el;
          })}
          <circle r={42} fill="#FDF9F0" />
        </g>
      </svg>
      <ul className="space-y-2 text-sm">
        {series.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 text-text-muted">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: s.color || SEEDS[i % SEEDS.length] }}
            />
            {s.label}
            <span className="text-text-soft">
              ({Math.round((s.value / total) * 100)}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Barras con valores positivos/negativos (auditoría de validación). */
export function SignedBarChart({
  series,
  height = 180,
}: {
  series: SeriesPoint[];
  height?: number;
}) {
  const absMax = Math.max(...series.map((s) => Math.abs(s.value)), 1);
  const barW = Math.max(10, Math.floor(320 / Math.max(series.length, 1)) - 4);
  const width = Math.max(320, series.length * (barW + 8));
  const mid = height / 2;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img">
      <line x1={0} y1={mid} x2={width} y2={mid} stroke="#D6D3C8" strokeWidth={1} />
      {series.map((s, i) => {
        const h = (Math.abs(s.value) / absMax) * (mid - 24);
        const x = i * (barW + 8) + 6;
        const y = s.value >= 0 ? mid - h : mid;
        return (
          <g key={`${s.label}-${i}`}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 1)}
              rx={4}
              fill={s.color || (s.value >= 0 ? "#62986C" : "#93403A")}
            />
            <text
              x={x + barW / 2}
              y={height - 8}
              textAnchor="middle"
              style={{ fontSize: 9, fill: "#6B7280" }}
            >
              {s.label.slice(0, 4)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
