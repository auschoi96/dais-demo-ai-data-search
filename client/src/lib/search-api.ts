import type { SearchRequest, SearchResponse } from '../../../shared/search-types';

export async function runSearch(request: SearchRequest): Promise<SearchResponse> {
  const response = await fetch('/api/search/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(payload.error ?? `Search failed (${response.status})`);
  }

  return response.json() as Promise<SearchResponse>;
}

export const TIER_LABELS = {
  '0': 'Tier 0 — Keyword (vibe-coded)',
  '1': 'Tier 1 — Vector Search on raw data',
  '2': 'Tier 2 — Vector Search on AI-ready data',
  '3': 'Tier 3 — Supervisor API + Opus 4.7 (raw)',
} as const;

export const HERO_QUERIES = ['I want to save money', 'quiero ahorrar'] as const;
