import { useState } from 'react'

import { createClinicalRecord } from '../services/patients.js'
import { Field, FormActions } from './Field.jsx'

export function ClinicalRecordForm({ patientId, onSaved, onCancel }) {
  const [values, setValues] = useState({
    condition: '',
    history_text: '',
    allergies: '',
    current_medications: '',
    previous_treatments: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function handleChange(event) {
    setValues((prev) => ({ ...prev, [event.target.name]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const record = await createClinicalRecord(patientId, values)
      onSaved?.(record)
    } catch (err) {
      setError(err.message || 'Could not save the clinical record.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="card form" onSubmit={handleSubmit}>
      <h3 className="form__title">Add clinical record</h3>
      <Field label="Condition" hint="Example: Type 2 Diabetes">
        <input
          type="text"
          name="condition"
          value={values.condition}
          onChange={handleChange}
        />
      </Field>
      <Field label="History text">
        <textarea
          name="history_text"
          rows="3"
          value={values.history_text}
          onChange={handleChange}
        />
      </Field>
      <Field label="Allergies">
        <textarea
          name="allergies"
          rows="2"
          value={values.allergies}
          onChange={handleChange}
        />
      </Field>
      <Field label="Current medications">
        <textarea
          name="current_medications"
          rows="2"
          value={values.current_medications}
          onChange={handleChange}
        />
      </Field>
      <Field label="Previous treatments">
        <textarea
          name="previous_treatments"
          rows="2"
          value={values.previous_treatments}
          onChange={handleChange}
        />
      </Field>
      {error ? (
        <p className="form__error" role="alert">
          {error}
        </p>
      ) : null}
      <FormActions onCancel={onCancel}>
        <button type="submit" className="button" disabled={saving}>
          {saving ? 'Saving…' : 'Save clinical record'}
        </button>
      </FormActions>
    </form>
  )
}