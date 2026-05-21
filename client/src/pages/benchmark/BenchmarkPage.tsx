import {
  useAnalyticsQuery,
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@databricks/appkit-ui/react';

interface BenchmarkRow {
  tier: string;
  hit_at_4: number;
  mrr: number;
  avg_latency_ms: number;
}

const TIER_META = [
  { tier: 'tier0', label: 'Tier 0 — Keyword', note: 'Vibe-coded substring search' },
  { tier: 'tier1', label: 'Tier 1 — VS Raw', note: 'Vector Search on thin catalog copy' },
  { tier: 'tier2', label: 'Tier 2 — VS Enriched', note: 'AI-ready embedding_text column' },
  { tier: 'tier3', label: 'Tier 3 — Supervisor', note: 'Opus 4.7 + UC function on raw index' },
];

export function BenchmarkPage() {
  const { data, loading, error } = useAnalyticsQuery('benchmark_summary');
  const rows = (data ?? []) as BenchmarkRow[];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Search Benchmark</h2>
        <p className="text-muted-foreground mt-1">
          Hit@4 and MRR on labeled queries — run <code>python eval/run_benchmark.py</code> to refresh live numbers.
        </p>
      </div>

      {error && (
        <div className="text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {TIER_META.map((meta) => {
          const row = rows.find((item) => item.tier === meta.tier);
          return (
            <Card key={meta.tier} className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-lg">{meta.label}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{meta.note}</p>
                {loading && <Skeleton className="h-20 w-full" />}
                {!loading && row && (
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">Hit@4: {(Number(row.hit_at_4) * 100).toFixed(0)}%</Badge>
                    <Badge variant="secondary">MRR: {Number(row.mrr).toFixed(2)}</Badge>
                    <Badge variant="outline">{Number(row.avg_latency_ms)} ms avg</Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Presenter notes</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>Hero queries: <strong>I want to save money</strong> and <strong>quiero ahorrar</strong> → fail T0/T1/T3, succeed T2.</p>
          <p>Tier 3 proves the agent stack works — the bottleneck is AI-ready data, not the model.</p>
        </CardContent>
      </Card>
    </div>
  );
}
