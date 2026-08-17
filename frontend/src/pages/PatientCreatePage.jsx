import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { createPatient } from '../services/patients.js'
import { listFacilities } from '../services/facilities.js'
import { SyntheticBanner } from '../components/Banners.jsx'
import { Field, FormActions } from '../components/Field.jsx'
import { ErrorState } from '../components/States.jsx'

const SEX_OPTIONS = ['M', 'F', 'O']

function validate(values) {
  const errors = {}
  if (!values.external_reference.trim()) {
    errors.external_reference = 'Reference is required.'
  }
  if (values.age !== '' && (values.age < 0 || values.age > 130)) {
    errors.age = 'Age must be between 0 and 130.'
  }
  if (values.sex && !SEX_OPTIONS.includes(values.sex)) {
    errors.sex = 'Select a valid option.'
  }
  if (values.height !== '' && (values.height <= 0 || values.height > 300)) {
    errors.height = 'Height must be between 0 and 300 cm.'
  }
  if (values.weight !== '' && (values.weight <= 0 || values.weight > 600)) {
    errors.weight = 'Weight must be between 0 and 600 kg.'
  }
  return errors
}

export function PatientCreatePage() {
  const navigate = useNavigate()
  const [facilities, setFacilities] = useState([])
  const [facilitiesError, setFacilitiesError] = useState('')
  const [values, setValues] = useState({
    external_reference: '',
    age: '',
    sex: '',
    height: '',
    weight: '',
    current_facility_id: '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [submitError, setSubmitError] = useState('')

  useEffect(() => {
    let active = true
    listFacilities()
      .then((rows) => {
        if (active) setFacilities(rows)
      })
      .catch((err) => {
        if (active)
          setFacilitiesError(err.message || 'Could not load facilities.')
      })
    return () => {
      active = false
    }
  }, [])

  function handleChange(event) {
    const { name, value } = event.target
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const fieldErrors = validate(values)
    setErrors(fieldErrors)
    if (Object.keys(fieldErrors).length > 0) return

    setSaving(true)
    setSubmitError('')
    try {
      const patient = await createPatient({
        external_reference: values.external_reference.trim(),
        age: values.age === '' ? null : Number(values.age),
        sex: values.sex || null,
        height: values.height === '' ? null : Number(values.height),
        weight: values.weight === '' ? null : Number(values.weight),
        current_facility_id:
          values.current_facility_id === ''
            ? null
            : Number(values.current_facility_id),
      })
      navigate(`/patients/${patient.id}`)
    } catch (err) {
      setSubmitError(err.message || 'Could not create the patient.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="page" aria-labelledby="create-patient-title">
      <div className="page__header">
        <div>
          <h1 id="create-patient-title" className="page__title">
            Create synthetic patient
          </h1>
          <p className="page__subtitle">
            <Link to="/patients">Patients</Link> / Create
          </p>
        </div>
      </div>

      <SyntheticBanner />

      {facilitiesError ? (
        <ErrorState title="Could not load facilities." message={facilitiesError} />
      ) : null}

      <form className="card form" onSubmit={handleSubmit}>
        <Field label="Synthetic reference" required error={errors.external_reference}>
          <input
            type="text"
            name="external_reference"
            maxLength={32}
            value={values.external_reference}
            onChange={handleChange}
            placeholder="SYN-…"
          />
        </Field>
        <div className="form__grid">
          <Field label="Age" required error={errors.age}>
            <input
              type="number"
              min="0"
              max="130"
              step="1"
              name="age"
              value={values.age}
              onChange={handleChange}
            />
          </Field>
          <Field label="Sex" required error={errors.sex}>
            <select name="sex" value={values.sex} onChange={handleChange}>
              <option value="">Select…</option>
              {SEX_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Height (cm)" error={errors.height}>
            <input
              type="number"
              step="any"
              min="0"
              max="300"
              name="height"
              value={values.height}
              onChange={handleChange}
            />
          </Field>
          <Field label="Weight (kg)" error={errors.weight}>
            <input
              type="number"
              step="any"
              min="0"
              max="600"
              name="weight"
              value={values.weight}
              onChange={handleChange}
            />
          </Field>
          <Field label="Current facility" required>
            <select
              name="current_facility_id"
              value={values.current_facility_id}
              onChange={handleChange}
            >
              <option value="">Select…</option>
              {facilities.map((facility) => (
                <option key={facility.id} value={facility.id}>
                  {facility.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {submitError ? (
          <p className="form__error" role="alert">
            {submitError}
          </p>
        ) : null}
        <FormActions onCancel={() => navigate('/patients')}>
          <button type="submit" className="button" disabled={saving}>
            {saving ? 'Saving…' : 'Save synthetic patient'}
          </button>
        </FormActions>
      </form>
    </section>
  )
}