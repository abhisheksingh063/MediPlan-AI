import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import './index.css'
import { PatientCreatePage } from './pages/PatientCreatePage.jsx'
import { PatientListPage } from './pages/PatientListPage.jsx'
import { PatientProfilePage } from './pages/PatientProfilePage.jsx'

function Layout() {
  return (
    <div id="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <span className="sidebar__product">MediPlan AI</span>
          <span className="badge badge--info">Prototype</span>
        </div>
        <nav className="sidebar__nav" aria-label="Main navigation">
          <NavLink to="/patients" className="sidebar__link">
            Patients
          </NavLink>
        </nav>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/patients" replace />} />
        <Route path="/patients" element={<PatientListPage />} />
        <Route path="/patients/new" element={<PatientCreatePage />} />
        <Route path="/patients/:patientId" element={<PatientProfilePage />} />
        <Route path="*" element={<Navigate to="/patients" replace />} />
      </Route>
    </Routes>
  )
}

export default App