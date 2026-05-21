import { useEffect, useState } from 'react';
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@databricks/appkit-ui/react';

interface BenchmarkRow {
  agent: string;
  label: string;
  hit_at_4: number;
  avg_tool_calls: number;
  avg_latency_ms: number;
}

export function BenchmarkPage() {
  const [rows, setRows] = useState<BenchmarkRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/benchmark');
        const payload = await res.json();
        if (cancelled) return;
        if (!payload.ok) {
          setError(payload.error ?? `HTTP ${res.status}`);
        } else {
          setRows(payload.rows as BenchmarkRow[]);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Agent Benchmark</h2>
        <p className="text-muted-foreground mt-1">
          Hit@4, avg tool calls, and avg wall time across the labeled analytical queries.
          Run <code>python eval/run_agent_eval.py</code> to refresh.
        </p>
      </div>

      {error && (
        <div className="text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {loading && (
          <>
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </>
        )}

        {!loading &&
          rows?.map((row) => (
            <Card key={row.agent} className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${row.agent === 'ready' ? 'bg-success' : 'bg-warning'}`}
                  />
                  {row.label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">Hit@4: {(row.hit_at_4 * 100).toFixed(0)}%</Badge>
                  <Badge variant="secondary">Avg tool calls: {row.avg_tool_calls.toFixed(1)}</Badge>
                  <Badge variant="outline">{(row.avg_latency_ms / 1000).toFixed(1)}s avg</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Why the gap</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            Same model (Opus 4.6). Same prompt scaffolding. The vibe-coded agent has to
            discover the schema and iterate on broken SQL. The AI-ready agent calls a
            single governed metric view.
          </p>
          <p>The cost is data work done once, governed in UC, not re-done by every agent.</p>
        </CardContent>
      </Card>
    </div>
  );
}
