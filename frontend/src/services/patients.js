import { api } from './client.js'

export function listPatients(search = '') {
  const params = search ? `?search=${encodeURIComponent(search)}` : ''
  return api.get(`/api/v1/patients${params}`)
}

export function getPatient(id) {
  return api.get(`/api/v1/patients/${id}`)
}

export function createPatient(data) {
  return api.post('/api/v1/patients', data)
}

export function updatePatient(id, data) {
  return api.patch(`/api/v1/patients/${id}`, data)
}

export function listClinicalRecords(patientId) {
  return api.get(`/api/v1/patients/${patientId}/clinical-records`)
}

export function createClinicalRecord(patientId, data) {
  return api.post(`/api/v1/patients/${patientId}/clinical-records`, data)
}

export function createLabResult(patientId, recordId, data) {
  return api.post(
    `/api/v1/patients/${patientId}/clinical-records/${recordId}/lab-results`,
    data,
  )
}