import { useState } from 'react'
import TopBar from './components/TopBar'
import FleetView from './components/FleetView'
import StationDetail from './components/StationDetail'
import './theme.css'

export default function App() {
  const [openStation, setOpenStation] = useState(null)

  return (
    <div className="app-shell">
      <TopBar />
      {openStation ? (
        <StationDetail station={openStation} onBack={() => setOpenStation(null)} />
      ) : (
        <FleetView onOpen={setOpenStation} />
      )}
    </div>
  )
}
