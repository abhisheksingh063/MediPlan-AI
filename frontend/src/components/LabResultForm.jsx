import { useState } from 'react'

import { createLabResult } from '../services/patients.js'
import { Field, FormActions } from './Field.jsx'

export function LabResultForm({ patientId, recordId, onSaved, onCancel }) {
  const [values, setValues] = useState({
    test_name: '',
    value: '',
    unit: '',
    reference_range: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function handleChange(event) {
    setValues((prev) => ({ ...prev, [event.target.name]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!values.test_name.trim()) {
      setError('Test name is required.')
      return
    }
    if (values.value === '' || Number.isNaN(Number(values.value))) {
      setError('A numeric value is required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await createLabResult(patientId, recordId, {
        test_name: values.test_name.trim(),
        value: Number(values.value),
        unit: values.unit.trim() || null,
        reference_range: values.reference_range.trim() || null,
      })
      onSaved?.(result)
    } catch (err) {
      setError(err.message || 'Could not save the lab result.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="card form" onSubmit={handleSubmit}>
      <h3 className="form__title">Add lab result</h3>
      <Field label="Test name" required>
        <input
          type="text"
          name="test_name"
          value={values.test_name}
          onChange={handleChange}
        />
      </Field>
      <Field label="Value" required>
        <input
          type="number"
          step="any"
          name="value"
          value={values.value}
          onChange={handleChange}
        />
      </Field>
      <Field label="Unit">
        <input
          type="text"
          name="unit"
          value={values.unit}
          onChange={handleChange}
        />
      </Field>
      <Field label="Reference range">
        <input
          type="text"
          name="reference_range"
          value={values.reference_range}
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
          {saving ? 'Saving…' : 'Save lab result'}
        </button>
      </FormActions>
    </form>
  )
}