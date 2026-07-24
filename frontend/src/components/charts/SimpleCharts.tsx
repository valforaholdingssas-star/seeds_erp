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

/** Barras +/- compactas con monto visible (auditoría de validación). */
export function SignedBarChart({
  series,
  height = 220,
  formatValue,
}: {
  series: SeriesPoint[];
  height?: number;
  formatValue?: (n: number) => string;
}) {
  const fmt =
    formatValue ||
    ((n: number) => {
      const sign = n < 0 ? "-" : "";
      const abs = Math.abs(n);
      if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
      if (abs >= 1_000) return `${sign}$${Math.round(abs / 1_000)}K`;
      return `${sign}$${Math.round(abs)}`;
    });

  const absMax = Math.max(...series.map((s) => Math.abs(s.value)), 1);
  const leftPad = 52;
  const rightPad = 8;
  const topPad = 28;
  const bottomPad = 28;
  const plotH = height - topPad - bottomPad;
  const mid = topPad + plotH / 2;
  const gap = 10;
  const barW = Math.min(28, Math.max(14, Math.floor(420 / Math.max(series.length, 1)) - gap));
  const plotW = Math.max(series.length * (barW + gap), 200);
  const width = leftPad + plotW + rightPad;

  const ticks = [-absMax, -absMax / 2, 0, absMax / 2, absMax];

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="mx-auto block h-auto max-h-[240px] w-full max-w-3xl"
        role="img"
      >
        {ticks.map((t) => {
          const y = mid - (t / absMax) * (plotH / 2 - 4);
          return (
            <g key={t}>
              <line
                x1={leftPad}
                y1={y}
                x2={width - rightPad}
                y2={y}
                stroke={t === 0 ? "#B8B4A8" : "#E8E4D8"}
                strokeWidth={t === 0 ? 1.2 : 0.8}
                strokeDasharray={t === 0 ? undefined : "3 3"}
              />
              <text
                x={leftPad - 6}
                y={y + 3}
                textAnchor="end"
                style={{ fontSize: 9, fill: "#6B7280", fontFamily: "ui-sans-serif, system-ui" }}
              >
                {fmt(t)}
              </text>
            </g>
          );
        })}

        {series.map((s, i) => {
          const h = (Math.abs(s.value) / absMax) * (plotH / 2 - 8);
          const x = leftPad + i * (barW + gap) + gap / 2;
          const y = s.value >= 0 ? mid - h : mid;
          const labelY = s.value >= 0 ? y - 4 : y + h + 11;
          const fill = s.color || (s.value >= 0 ? "#62986C" : "#93403A");
          return (
            <g key={`${s.label}-${i}`}>
              <title>{`${s.label}: ${fmt(s.value)}`}</title>
              <rect x={x} y={y} width={barW} height={Math.max(h, 2)} rx={3} fill={fill} />
              <text
                x={x + barW / 2}
                y={labelY}
                textAnchor="middle"
                style={{
                  fontSize: 8,
                  fill: "#1D2D1B",
                  fontWeight: 600,
                  fontFamily: "ui-sans-serif, system-ui",
                }}
              >
                {fmt(s.value)}
              </text>
              <text
                x={x + barW / 2}
                y={height - 8}
                textAnchor="middle"
                style={{ fontSize: 9, fill: "#6B7280", fontFamily: "ui-sans-serif, system-ui" }}
              >
                {s.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
