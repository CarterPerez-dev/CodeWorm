// ©AngelaMos | 2026
// useRepos.ts

import type { UseQueryResult } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import type { RepoStatus } from '@/api/types'
import { API_ENDPOINTS, QUERY_CONFIG, QUERY_KEYS } from '@/config'
import { apiClient } from '@/core/api'

export const repoQueries = {
  all: () => QUERY_KEYS.REPOS,
} as const

const fetchRepos = async (): Promise<RepoStatus[]> => {
  const response = await apiClient.get<RepoStatus[]>(API_ENDPOINTS.REPOS)
  return response.data
}

export const useRepos = (): UseQueryResult<RepoStatus[], Error> => {
  return useQuery({
    queryKey: repoQueries.all(),
    queryFn: fetchRepos,
    staleTime: QUERY_CONFIG.STALE_TIME.STATIC,
  })
}
