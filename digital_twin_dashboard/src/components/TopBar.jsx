import { useEffect, useState } from 'react'
import './TopBar.css'

export default function TopBar() {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="top-bar">
      <div className="top-bar__brand">
        <span className="top-bar__mark">✣</span>
        <div className="top-bar__title">
          <span className="top-bar__eyebrow">Antarctic</span>
          <span className="top-bar__title-main">Digital Twin</span>
        </div>
      </div>
      <div className="top-bar__meta">
        <span className="top-bar__connection"><i /> API connection&nbsp; Operational</span>
        <span className="top-bar__clock num">◷&nbsp; {now.toLocaleTimeString([], { hour12: false })} UTC</span>
        <span className="top-bar__bell">♧</span>
      </div>
    </div>
  )
}
