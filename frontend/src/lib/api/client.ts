/**
 * TCE v1.1 - Typed HTTP API Client
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

export function mediaUrl(path: string | null | undefined): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const base = BACKEND_URL.endsWith('/') ? BACKEND_URL.slice(0, -1) : BACKEND_URL;
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${cleanPath}`;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const memoryCache = new Map<string, CacheEntry<any>>();
const inFlightRequests = new Map<string, Promise<any>>();
const DEFAULT_TTL_MS = 25000; // 25s fresh window
const STALE_REVALIDATE_MS = 6000; // Background revalidation threshold

export function clearApiCache(prefix?: string) {
  if (!prefix) {
    memoryCache.clear();
  } else {
    memoryCache.forEach((_, key) => {
      if (key.includes(prefix)) {
        memoryCache.delete(key);
      }
    });
  }
}

async function request<T>(
  endpoint: string,
  options?: RequestInit,
  cacheConfig?: { bypassCache?: boolean; ttlMs?: number }
): Promise<T> {
  const method = (options?.method ?? 'GET').toUpperCase();
  const isGet = method === 'GET';
  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

  // If mutation, invalidate related cache
  if (!isGet) {
    clearApiCache();
  }

  const cacheKey = `${method}:${url}`;

  // Check cache for GET requests
  if (isGet && !cacheConfig?.bypassCache) {
    const cached = memoryCache.get(cacheKey);
    const now = Date.now();
    const ttl = cacheConfig?.ttlMs ?? DEFAULT_TTL_MS;

    if (cached) {
      const age = now - cached.timestamp;
      if (age < ttl) {
        // Trigger background revalidation if past stale threshold
        if (age > STALE_REVALIDATE_MS && !inFlightRequests.has(cacheKey)) {
          fetchAndCache<T>(cacheKey, url, options).catch(() => {});
        }
        return cached.data as T;
      }
    }

    // Deduplicate in-flight requests
    if (inFlightRequests.has(cacheKey)) {
      return inFlightRequests.get(cacheKey) as Promise<T>;
    }
  }

  return fetchAndCache<T>(cacheKey, url, options, isGet);
}

async function fetchAndCache<T>(
  cacheKey: string,
  url: string,
  options?: RequestInit,
  shouldCache: boolean = true
): Promise<T> {
  const fetchPromise = (async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        try {
          controller.abort(new DOMException("API request timed out after 30s", "TimeoutError"));
        } catch {
          controller.abort();
        }
      }, 30000);
      const res = await fetch(url, {
        signal: options?.signal ?? controller.signal,
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        let errDetail = `HTTP ${res.status}`;
        try {
          const data = await res.json();
          if (data && data.detail) {
            errDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
          }
        } catch {
          // Non-JSON error body
        }
        throw new Error(errDetail);
      }

      const json = (await res.json()) as T;
      if (shouldCache) {
        memoryCache.set(cacheKey, { data: json, timestamp: Date.now() });
      }
      return json;
    } finally {
      inFlightRequests.delete(cacheKey);
    }
  })();

  if (shouldCache) {
    inFlightRequests.set(cacheKey, fetchPromise);
  }

  return fetchPromise;
}

export const api = {
  jobs: {
    list: (options?: { bypassCache?: boolean }) => request<any[]>('/jobs/', undefined, options),
    get: (id: string, options?: { bypassCache?: boolean }) => request<any>(`/jobs/${id}`, undefined, options),
    cancel: (id: string) => request<any>(`/jobs/${id}/cancel`, { method: 'POST' }),
    reprocess: (id: string) => request<any>(`/jobs/${id}/reprocess`, { method: 'POST' }),
    diagnostics: (id: string) => request<any>(`/jobs/${id}/diagnostics`),
  },
  analytics: (options?: { bypassCache?: boolean }) => request<any>('/analytics/', undefined, options),
  events: {
    list: (params?: { video_id?: string; limit?: string | number }, options?: { bypassCache?: boolean }) => {
      const sp = new URLSearchParams();
      if (params?.video_id) sp.set('video_id', params.video_id);
      if (params?.limit) sp.set('limit', String(params.limit));
      const qs = sp.toString();
      return request<any[]>(`/events/${qs ? `?${qs}` : ''}`, undefined, options);
    },
    get: (id: string) => request<any>(`/events/${id}`),
    preview: (id: string) => request<any>(`/events/${id}/preview`),
    evidence: (id: string) => request<any>(`/events/${id}/evidence`),
  },
  videos: {
    list: (options?: { bypassCache?: boolean }) => request<any[]>('/videos/', undefined, options),
    get: (id: string, options?: { bypassCache?: boolean }) => request<any>(`/videos/${id}`, undefined, options),
  },
  timeline: (videoId: string, options?: { bypassCache?: boolean }) => request<any>(`/timeline/${videoId}`, undefined, options),
  summary: (videoId: string, options?: { bypassCache?: boolean }) => request<any>(`/summary/${videoId}`, undefined, options),
  settings: {
    list: (options?: { bypassCache?: boolean }) => request<any[]>('/settings/', undefined, options),
  },
  stories: (videoId: string, options?: { bypassCache?: boolean }) => request<any>(`/stories/${videoId}`, undefined, options),
  health: (options?: { bypassCache?: boolean }) => request<any>('/health', undefined, options),
  clearCache: clearApiCache,
};

