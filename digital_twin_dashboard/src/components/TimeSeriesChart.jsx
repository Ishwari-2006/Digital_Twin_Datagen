import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import "./TimeSeriesChart.css";

const COLORS = {
  ice: "#1f5d91",
  aurora: "#3f7d52",
  amber: "#a66100",
  flare: "#b83b2a",
};

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="ts-tooltip">
      <div className="ts-tooltip__time">{formatTime(label)}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="ts-tooltip__row">
          <span
            className="ts-tooltip__swatch"
            style={{ background: p.color }}
          />
          {p.name}:{" "}
          <strong className="num">
            {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
            {unit}
          </strong>
        </div>
      ))}
    </div>
  );
}

/**
 * data: array of history rows (already sorted ascending by ts)
 * series: [{ key: 'ambient_temp_c', name: 'Ambient temp', color: 'ice' }]
 */
export default function TimeSeriesChart({
  data,
  series,
  unit = "",
  height = 190,
}) {
  if (!data || data.length < 2) {
    return (
      <div className="ts-empty">
        Not enough history yet — check back in a few minutes.
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart
        data={data}
        margin={{ top: 6, right: 8, left: -12, bottom: 0 }}
      >
        <CartesianGrid stroke="#1a2f42" vertical={false} />
        <XAxis
          dataKey="ts"
          tickFormatter={formatTime}
          stroke="#5d7688"
          fontSize={11}
          tickLine={false}
          axisLine={{ stroke: "#223a4e" }}
          minTickGap={40}
        />
        <YAxis
          stroke="#5d7688"
          fontSize={11}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip content={<CustomTooltip unit={unit} />} />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={COLORS[s.color] || COLORS.ice}
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
