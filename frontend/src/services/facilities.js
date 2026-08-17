import { api } from './client.js'

export function listFacilities() {
  return api.get('/api/v1/facilities')
}