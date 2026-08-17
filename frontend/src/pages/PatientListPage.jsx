import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { listPatients } from '../services/patients.js'
import { EmptyState, ErrorState, LoadingState } from '../components/States.jsx'
import { formatDate } from '../lib/format.js'

const SEARCH_DELAY_MS = 400

export function PatientListPage() {
  const [patients, setPatients] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const debounceRef = useRef(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      let active = true
      setLoading(true)
      setError('')
      listPatients(search.trim())
        .then((result) => {
          if (active) setPatients(result.items)
        })
        .catch((err) => {
          if (active) setError(err.message || 'Could not load patients.')
        })
        .finally(() => {
          if (active) {
            setLoading(false)
            setLoaded(true)
          }
        })
      return () => {
        active = false
      }
    }, SEARCH_DELAY_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search, refreshKey])

  return (
    <section className="page" aria-labelledby="patient-list-title">
      <div className="page__header">
        <div>
          <h1 id="patient-list-title" className="page__title">
            Patients
          </h1>
          <p className="page__subtitle">
            Synthetic demo records for clinician review.
          </p>
        </div>
        <Link to="/patients/new" className="button">
          Create synthetic patient
        </Link>
      </div>

      <label className="field">
        <span className="field__label">Search reference / facility</span>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Type to filter patients"
        />
      </label>

      {loading ? <LoadingState>Searching patients…</LoadingState> : null}

      {!loading && error ? (
        <ErrorState title="Could not load patients." message={error}>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => setRefreshKey((value) => value + 1)}
          >
            Retry
          </button>
        </ErrorState>
      ) : null}

      {!loading && !error && loaded && patients.length === 0 ? (
        <EmptyState
          title={
            search.trim()
              ? 'No synthetic patients match this reference.'
              : 'No synthetic patients have been added yet.'
          }
        >
          <Link to="/patients/new" className="button">
            Create synthetic patient
          </Link>
        </EmptyState>
      ) : null}

      {!loading && !error && patients.length > 0 ? (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Age</th>
                <th>Sex</th>
                <th>Current facility</th>
                <th>Created</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {patients.map((patient) => (
                <tr key={patient.id}>
                  <td className="table__reference">{patient.external_reference}</td>
                  <td className="table__numeric">
                    {patient.age === null || patient.age === undefined
                      ? '—'
                      : patient.age}
                  </td>
                  <td>{patient.sex || '—'}</td>
                  <td>{patient.current_facility?.name || '—'}</td>
                  <td className="table__numeric">{formatDate(patient.created_at)}</td>
                  <td>
                    <Link
                      to={`/patients/${patient.id}`}
                      className="button button--small button--secondary"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}