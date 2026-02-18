// ©AngelaMos | 2026
// api.config.ts

import axios from 'axios'

const getBaseURL = (): string => {
  return import.meta.env.VITE_API_URL ?? '/api'
}

export const apiClient = axios.create({
  baseURL: getBaseURL(),
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})
