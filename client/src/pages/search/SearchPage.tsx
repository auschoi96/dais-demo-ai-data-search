import { useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Skeleton,
} from '@databricks/appkit-ui/react';
import { HERO_QUERIES, TIER_LABELS, runSearch } from '../../lib/search-api';
import type { SearchResponse, SearchTier } from '../../../../shared/search-types';

const TIERS: SearchTier[] = ['0', '1', '2', '3'];

export function SearchPage() {
  const [query, setQuery] = useState('I want to save money');
  const [tier, setTier] = useState<SearchTier>('0');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);

  async function handleSearch(nextTier = tier) {
    setLoading(true);
    setError(null);
    try {
      const result = await runSearch({ query, tier: nextTier, limit: 4 });
      setResponse(result);
      setTier(nextTier);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Yape Service Search</h2>
        <p className="text-muted-foreground mt-1">
          Compare four search maturity tiers — the hero moment is intent queries that fail on raw data.
        </p>
      </div>

      <Card className="shadow-lg border-[#742284]/20">
        <CardHeader>
          <CardTitle>Search</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="query">Query</Label>
            <Input
              id="query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Try: I want to save money"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {HERO_QUERIES.map((hero) => (
              <Button key={hero} variant="outline" size="sm" onClick={() => setQuery(hero)}>
                {hero}
              </Button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            {TIERS.map((value) => (
              <Button
                key={value}
                variant={tier === value ? 'default' : 'outline'}
                size="sm"
                className={tier === value ? 'bg-[#742284] hover:bg-[#5a1a68]' : ''}
                disabled={loading}
                onClick={() => handleSearch(value)}
              >
                {TIER_LABELS[value as keyof typeof TIER_LABELS]}
              </Button>
            ))}
          </div>

          <Button
            className="bg-[#742284] hover:bg-[#5a1a68]"
            disabled={loading || !query.trim()}
            onClick={() => handleSearch()}
          >
            {loading ? 'Searching…' : 'Run search'}
          </Button>

          {error && (
            <div className="text-destructive bg-destructive/10 p-3 rounded-md text-sm">{error}</div>
          )}
        </CardContent>
      </Card>

      <Card className="shadow-lg">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Results</CardTitle>
          {response && (
            <Badge variant="secondary">{response.latency_ms} ms</Badge>
          )}
        </CardHeader>
        <CardContent>
          {loading && (
            <div className="space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          )}

          {!loading && response && response.results.length === 0 && (
            <p className="text-muted-foreground">No matches — raw data often misses intent phrasing.</p>
          )}

          {!loading && response && response.results.length > 0 && (
            <ul className="space-y-3">
              {response.results.map((item: SearchResponse['results'][number]) => (
                <li
                  key={`${item.service_id}-${item.name}`}
                  className="border rounded-lg p-4 flex gap-3 items-start"
                >
                  <span className="text-2xl">{item.icon ?? '🔎'}</span>
                  <div className="min-w-0">
                    <div className="font-semibold">{item.name}</div>
                    <div className="text-sm text-muted-foreground">{item.category}</div>
                    <div className="text-sm mt-1">{item.description}</div>
                    {item.score != null && (
                      <div className="text-xs text-muted-foreground mt-1">
                        score: {item.score.toFixed(3)}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

          {response?.trace_url && (
            <p className="text-sm mt-4">
              <a
                href={response.trace_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#742284] underline underline-offset-4"
              >
                View Supervisor trace in MLflow →
              </a>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
