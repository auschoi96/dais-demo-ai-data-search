export const CATALOG = 'ac_demo';
export const SCHEMA = 'agents';

export const TABLES = {
  raw: `${CATALOG}.${SCHEMA}.yape_services_raw`,
  enriched: `${CATALOG}.${SCHEMA}.yape_services_enriched`,
  eval: `${CATALOG}.${SCHEMA}.yape_search_eval`,
} as const;

export const INDEXES = {
  raw: `${CATALOG}.${SCHEMA}.yape_services_raw_idx`,
  enriched: `${CATALOG}.${SCHEMA}.yape_services_enriched_idx`,
} as const;

export const VS_ENDPOINT = 'yape-search-demo-endpoint';
export const LLM_MODEL = 'databricks-claude-opus-4-7';
export const UC_FUNCTION = `${CATALOG}.${SCHEMA}.search_yape_services`;

export const TRACE_DESTINATION = {
  catalog_name: CATALOG,
  schema_name: SCHEMA,
  table_prefix: 'yape_search',
};

export type SearchTier = '0' | '1' | '2' | '3';
export type IndexVariant = 'raw' | 'enriched';

export interface SearchResult {
  service_id: string;
  name: string;
  category: string;
  description: string;
  icon?: string;
  score?: number;
  tier: SearchTier;
  latency_ms: number;
}

export interface SearchRequest {
  query: string;
  tier: SearchTier;
  limit?: number;
}

export interface SearchResponse {
  query: string;
  tier: SearchTier;
  results: SearchResult[];
  latency_ms: number;
  trace_url?: string;
}
