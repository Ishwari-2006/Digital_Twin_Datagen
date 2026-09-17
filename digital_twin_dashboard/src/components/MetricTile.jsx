import './MetricTile.css'

export default function MetricTile({ label, value, unit, tone = 'neutral', note }) {
  return (
    <div className="metric-tile">
      <div className="metric-tile__label">{label}</div>
      <div className={`metric-tile__value metric-tile__value--${tone} num`}>
        {value}
        {unit && <span className="metric-tile__unit">{unit}</span>}
      </div>
      {note && <div className="metric-tile__note">{note}</div>}
    </div>
  )
}
