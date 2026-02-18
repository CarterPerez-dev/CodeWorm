// ©AngelaMos | 2026
// useRecent.ts

import type { UseQueryResult } from '@tanstack/react-query'
import { useQuery } from '@tanstack/react-query'
import type { RecentDoc } from '@/api/types'
import { API_ENDPOINTS, QUERY_CONFIG, QUERY_KEYS } from '@/config'
import { apiClient } from '@/core/api'

export const recentQueries = {
  list: (limit: number, repo?: string, docType?: string) =>
    QUERY_KEYS.RECENT(limit, repo, docType),
} as const

const fetchRecent = async (
  limit: number,
  repo?: string,
  docType?: string
): Promise<RecentDoc[]> => {
  const params: Record<string, string | number> = { limit }
  if (repo) params.repo = repo
  if (docType) params.doc_type = docType

  const response = await apiClient.get<RecentDoc[]>(API_ENDPOINTS.RECENT, {
    params,
  })
  return response.data
}

export const useRecent = (
  limit = 50,
  repo?: string,
  docType?: string
): UseQueryResult<RecentDoc[], Error> => {
  return useQuery({
    queryKey: recentQueries.list(limit, repo, docType),
    queryFn: () => fetchRecent(limit, repo, docType),
    staleTime: QUERY_CONFIG.STALE_TIME.FREQUENT,
  })
}
