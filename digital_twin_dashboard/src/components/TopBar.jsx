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
      <div className="top-bar__title">
        <span className="top-bar__title-main">Antarctic Digital Twin</span>
        <span className="top-bar__title-sub">Maitri &amp; Bharati research stations</span>
      </div>
      <div className="top-bar__clock num">
        {now.toLocaleTimeString([], { hour12: false })}
      </div>
    </div>
  )
}
