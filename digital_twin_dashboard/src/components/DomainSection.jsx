import MetricTile from './MetricTile'
import TimeSeriesChart from './TimeSeriesChart'
import './DomainSection.css'

export default function DomainSection({ tiles, charts }) {
  return (
    <div className="domain-section">
      <div className="domain-section__tiles">
        {tiles.map((t) => (
          <MetricTile key={t.label} {...t} />
        ))}
      </div>
      <div className="domain-section__charts">
        {charts.map((c) => (
          <div key={c.title} className="domain-section__chart">
            <div className="domain-section__chart-title">{c.title}</div>
            <TimeSeriesChart data={c.data} series={c.series} unit={c.unit} />
          </div>
        ))}
      </div>
    </div>
  )
}
