// ©AngelaMos | 2026
// query.config.ts

import { QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { QUERY_CONFIG } from '@/config'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: QUERY_CONFIG.STALE_TIME.STATS,
      gcTime: QUERY_CONFIG.GC_TIME.DEFAULT,
      retry: QUERY_CONFIG.RETRY.DEFAULT,
      refetchOnWindowFocus: true,
      refetchOnMount: true,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: QUERY_CONFIG.RETRY.NONE,
      onError: (error: Error) => {
        toast.error(error.message || 'Operation failed')
      },
    },
  },
})
