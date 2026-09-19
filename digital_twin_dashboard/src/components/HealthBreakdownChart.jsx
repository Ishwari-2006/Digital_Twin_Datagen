import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./HealthBreakdownChart.css";

const SERIES = [
  ["normal", "Normal", "#3f7d52"],
  ["warning", "Warning", "#a66100"],
  ["critical", "Critical", "#b83b2a"],
  ["comms_blackout", "Comms blackout", "#415568"],
  ["backfilled", "Backfilled", "#6f42a1"],
];

function formatHour(value) {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function HealthBreakdownChart({ data }) {
  if (!data?.length)
    return (
      <div className="health-breakdown__empty">No health history yet.</div>
    );
  return (
    <section className="health-breakdown">
      <div className="health-breakdown__heading">
        <h2>24-hour station state</h2>
        <span>Telemetry readings per hour</span>
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
        >
          <CartesianGrid stroke="#1a2f42" vertical={false} />
          <XAxis
            dataKey="hour"
            tickFormatter={formatHour}
            stroke="#5d7688"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: "#223a4e" }}
            minTickGap={32}
          />
          <YAxis
            allowDecimals={false}
            stroke="#5d7688"
            fontSize={11}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip labelFormatter={formatHour} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {SERIES.map(([key, name, fill]) => (
            <Bar
              key={key}
              dataKey={key}
              name={name}
              stackId="state"
              fill={fill}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
