import type { SearchRequest, SearchResponse, SearchTier } from '../../../shared/search-types';

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

export interface TierRun {
  tier: SearchTier;
  status: 'pending' | 'ok' | 'error';
  response?: SearchResponse;
  error?: string;
}

export async function runTiers(
  query: string,
  tiers: SearchTier[],
  onUpdate: (run: TierRun) => void,
  limit = 4,
): Promise<void> {
  await Promise.all(
    tiers.map(async (tier) => {
      try {
        const response = await runSearch({ query, tier, limit });
        onUpdate({ tier, status: 'ok', response });
      } catch (err) {
        onUpdate({
          tier,
          status: 'error',
          error: err instanceof Error ? err.message : 'Search failed',
        });
      }
    }),
  );
}

export const TIER_LABELS: Record<SearchTier, string> = {
  '0': 'Keyword (vibe-coded)',
  '1': 'VS on raw data',
  '2': 'VS on AI-ready data',
  '3': 'Supervisor + Opus 4.7',
};

export const TIER_SHORT: Record<SearchTier, string> = {
  '0': 'T0',
  '1': 'T1',
  '2': 'T2',
  '3': 'T3',
};

export const TIER_BLURB: Record<SearchTier, string> = {
  '0': 'SQL LIKE on raw catalog',
  '1': 'Vector Search on raw fields',
  '2': 'Vector Search on enriched embedding_text',
  '3': 'Opus 4.7 + UC function tool',
};

export const HERO_QUERIES = [
  'I want to save money',
  'quiero ahorrar',
  'pagar el alquiler',
  'send money to my mom',
] as const;
