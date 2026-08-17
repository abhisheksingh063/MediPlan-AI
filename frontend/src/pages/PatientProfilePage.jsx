import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { listFacilities } from '../services/facilities.js'
import {
  getPatient,
  listClinicalRecords,
  updatePatient,
} from '../services/patients.js'
import { SyntheticBanner } from '../components/Banners.jsx'
import { ClinicalRecordForm } from '../components/ClinicalRecordForm.jsx'
import { Field, FormActions } from '../components/Field.jsx'
import { LabResultForm } from '../components/LabResultForm.jsx'
import { EmptyState, ErrorState, LoadingState } from '../components/States.jsx'
import { displayNumber, formatDateTime } from '../lib/format.js'

const SEX_OPTIONS = ['M', 'F', 'O']

export function PatientProfilePage() {
  const { patientId } = useParams()
  const [patient, setPatient] = useState(null)
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [facilities, setFacilities] = useState([])

  const [editing, setEditing] = useState(false)
  const [editValues, setEditValues] = useState(null)
  const [editErrors, setEditErrors] = useState({})
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

  const [showingRecordForm, setShowingRecordForm] = useState(false)
  const [labFormRecordId, setLabFormRecordId] = useState(null)

  const reloadPatient = useCallback(() => {
    return getPatient(patientId).then(setPatient)
  }, [patientId])

  const reloadRecords = useCallback(() => {
    return listClinicalRecords(patientId).then(setRecords)
  }, [patientId])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([reloadPatient(), reloadRecords()])
      .catch((err) => {
        if (active) setError(err.message || 'Could not load this patient.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [reloadPatient, reloadRecords])

  useEffect(() => {
    let active = true
    listFacilities()
      .then((rows) => {
        if (active) setFacilities(rows)
      })
      .catch(() => {
        // Facility list is a convenience; the profile still renders.
      })
    return () => {
      active = false
    }
  }, [])

  function startEdit() {
    setEditValues({
      external_reference: patient.external_reference,
      age: patient.age ?? '',
      sex: patient.sex || '',
      height: patient.height ?? '',
      weight: patient.weight ?? '',
      current_facility_id: patient.current_facility_id ?? '',
    })
    setEditErrors({})
    setEditError('')
    setEditing(true)
  }

  function handleEditChange(event) {
    const { name, value } = event.target
    setEditValues((prev) => ({ ...prev, [name]: value }))
  }

  async function handleEditSubmit(event) {
    event.preventDefault()
    const payload = {
      external_reference: editValues.external_reference.trim(),
      age: editValues.age === '' ? null : Number(editValues.age),
      sex: editValues.sex || null,
      height: editValues.height === '' ? null : Number(editValues.height),
      weight: editValues.weight === '' ? null : Number(editValues.weight),
      current_facility_id:
        editValues.current_facility_id === ''
          ? null
          : Number(editValues.current_facility_id),
    }
    setEditSaving(true)
    setEditError('')
    try {
      await updatePatient(patientId, payload)
      await reloadPatient()
      setEditing(false)
    } catch (err) {
      setEditError(err.message || 'Could not save the changes.')
    } finally {
      setEditSaving(false)
    }
  }

  function handleRecordSaved() {
    setShowingRecordForm(false)
    reloadRecords()
  }

  function handleLabSaved() {
    setLabFormRecordId(null)
    reloadRecords()
  }

  if (loading) return <LoadingState>Loading patient…</LoadingState>

  if (!loading && error) {
    return (
      <ErrorState title="No synthetic patient matches this reference." message={error}>
        <Link to="/patients" className="button">
          Back to patients
        </Link>
      </ErrorState>
    )
  }

  return (
    <section className="page" aria-labelledby="profile-title">
      <div className="page__header">
        <div>
          <h1 id="profile-title" className="page__title">
            {patient.external_reference}
          </h1>
          <p className="page__subtitle">
            <Link to="/patients">Patients</Link> / {patient.external_reference} /
            Overview
          </p>
        </div>
        <Link to="/patients" className="button button--secondary">
          Back to patients
        </Link>
      </div>

      <SyntheticBanner />

      <section className="card" aria-labelledby="basic-info-title">
        <div className="card__header">
          <h2 id="basic-info-title" className="card__title">
            Basic information
          </h2>
          {!editing ? (
            <button type="button" className="button button--small" onClick={startEdit}>
              Edit
            </button>
          ) : null}
        </div>

        {editing ? (
          <form className="form" onSubmit={handleEditSubmit}>
            <div className="form__grid">
              <Field label="Synthetic reference" required error={editErrors.external_reference}>
                <input
                  type="text"
                  name="external_reference"
                  maxLength={32}
                  value={editValues.external_reference}
                  onChange={handleEditChange}
                />
              </Field>
              <Field label="Age">
                <input
                  type="number"
                  min="0"
                  max="130"
                  step="1"
                  name="age"
                  value={editValues.age}
                  onChange={handleEditChange}
                />
              </Field>
              <Field label="Sex">
                <select name="sex" value={editValues.sex} onChange={handleEditChange}>
                  <option value="">Not recorded</option>
                  {SEX_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Height (cm)">
                <input
                  type="number"
                  step="any"
                  name="height"
                  value={editValues.height}
                  onChange={handleEditChange}
                />
              </Field>
              <Field label="Weight (kg)">
                <input
                  type="number"
                  step="any"
                  name="weight"
                  value={editValues.weight}
                  onChange={handleEditChange}
                />
              </Field>
              <Field label="Current facility">
                <select
                  name="current_facility_id"
                  value={editValues.current_facility_id}
                  onChange={handleEditChange}
                >
                  <option value="">No facility</option>
                  {facilities.map((facility) => (
                    <option key={facility.id} value={facility.id}>
                      {facility.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {editError ? (
              <p className="form__error" role="alert">
                {editError}
              </p>
            ) : null}
            <FormActions onCancel={() => setEditing(false)}>
              <button type="submit" className="button" disabled={editSaving}>
                {editSaving ? 'Saving…' : 'Save changes'}
              </button>
            </FormActions>
          </form>
        ) : (
          <dl className="definition-list">
            <div>
              <dt>Reference</dt>
              <dd className="table__numeric">{patient.external_reference}</dd>
            </div>
            <div>
              <dt>Age</dt>
              <dd className="table__numeric">{patient.age ?? '—'}</dd>
            </div>
            <div>
              <dt>Sex</dt>
              <dd>{patient.sex || '—'}</dd>
            </div>
            <div>
              <dt>Height</dt>
              <dd className="table__numeric">
                {patient.height === null || patient.height === undefined
                  ? '—'
                  : `${displayNumber(patient.height)} cm`}
              </dd>
            </div>
            <div>
              <dt>Weight</dt>
              <dd className="table__numeric">
                {patient.weight === null || patient.weight === undefined
                  ? '—'
                  : `${displayNumber(patient.weight)} kg`}
              </dd>
            </div>
            <div>
              <dt>Current facility</dt>
              <dd>{patient.current_facility?.name || '—'}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(patient.created_at)}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="card" aria-labelledby="clinical-data-title">
        <div className="card__header">
          <h2 id="clinical-data-title" className="card__title">
            Clinical data
          </h2>
          {!showingRecordForm ? (
            <button
              type="button"
              className="button button--small"
              onClick={() => setShowingRecordForm(true)}
            >
              Add clinical record
            </button>
          ) : null}
        </div>

        {showingRecordForm ? (
          <ClinicalRecordForm
            patientId={patient.id}
            onSaved={handleRecordSaved}
            onCancel={() => setShowingRecordForm(false)}
          />
        ) : null}

        {records.length === 0 ? (
          <EmptyState title="No clinical records have been added yet.">
            <button
              type="button"
              className="button"
              onClick={() => setShowingRecordForm(true)}
            >
              Add clinical record
            </button>
          </EmptyState>
        ) : (
          records.map((record) => (
            <article className="record" key={record.id}>
              <div className="record__header">
                <h3 className="record__title">{record.condition || 'Clinical record'}</h3>
                <span className="badge badge--neutral">
                  {formatDateTime(record.recorded_at)}
                </span>
              </div>
              <dl className="definition-list definition-list--compact">
                {record.history_text ? (
                  <div>
                    <dt>History</dt>
                    <dd>{record.history_text}</dd>
                  </div>
                ) : null}
                {record.allergies ? (
                  <div>
                    <dt>Allergies</dt>
                    <dd>{record.allergies}</dd>
                  </div>
                ) : null}
                {record.current_medications ? (
                  <div>
                    <dt>Current medications</dt>
                    <dd>{record.current_medications}</dd>
                  </div>
                ) : null}
                {record.previous_treatments ? (
                  <div>
                    <dt>Previous treatments</dt>
                    <dd>{record.previous_treatments}</dd>
                  </div>
                ) : null}
              </dl>

              <h4 className="record__subsection">Laboratory results</h4>
              {record.lab_results.length === 0 ? (
                <p className="record__empty">No lab results on this record.</p>
              ) : (
                <table className="table table--compact">
                  <thead>
                    <tr>
                      <th>Test</th>
                      <th>Value</th>
                      <th>Unit</th>
                      <th>Reference range</th>
                      <th>Recorded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {record.lab_results.map((result) => (
                      <tr key={result.id}>
                        <td>{result.test_name}</td>
                        <td className="table__numeric">{displayNumber(result.value)}</td>
                        <td>{result.unit || '—'}</td>
                        <td>{result.reference_range || '—'}</td>
                        <td className="table__numeric">{formatDateTime(result.recorded_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {labFormRecordId === record.id ? (
                <LabResultForm
                  patientId={patient.id}
                  recordId={record.id}
                  onSaved={handleLabSaved}
                  onCancel={() => setLabFormRecordId(null)}
                />
              ) : (
                <button
                  type="button"
                  className="button button--small button--secondary"
                  onClick={() => setLabFormRecordId(record.id)}
                >
                  Add lab result
                </button>
              )}
            </article>
          ))
        )}
      </section>
    </section>
  )
}