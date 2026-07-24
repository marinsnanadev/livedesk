import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import AgentDashboard from './pages/AgentDashboard'
import ClientWidget from './pages/ClientWidget'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AgentDashboard />} />
        <Route path="/widget" element={<ClientWidget />} />
        <Route
          path="*"
          element={
            <div style={{ padding: 24, fontFamily: 'sans-serif', color: '#e8edef' }}>
              Page not found. <Link to="/">Back to dashboard</Link>
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
