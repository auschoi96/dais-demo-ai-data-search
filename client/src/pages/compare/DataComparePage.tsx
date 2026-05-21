import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  Badge,
} from '@databricks/appkit-ui/react';

interface ServiceRow {
  service_id: string;
  name: string;
  category: string;
  description: string;
  icon?: string;
  intent_tags?: string[];
  user_intent_phrases?: string[];
}

interface ApiResult {
  ok: boolean;
  error?: string;
  columns: string[];
  rows: (string | number | null)[][];
}

function shapeRows(payload: ApiResult): ServiceRow[] | null {
  if (!payload?.ok) return null;
  const cols = payload.columns;
  return payload.rows.map((row) => {
    const rec: Record<string, unknown> = {};
    cols.forEach((c, i) => {
      rec[c] = row[i];
    });
    const tags = rec.intent_tags;
    const phrases = rec.user_intent_phrases;
    return {
      service_id: String(rec.service_id ?? ''),
      name: String(rec.name ?? ''),
      category: String(rec.category ?? ''),
      description: String(rec.description ?? ''),
      icon: rec.icon ? String(rec.icon) : undefined,
      intent_tags: Array.isArray(tags) ? (tags as string[]) : undefined,
      user_intent_phrases: Array.isArray(phrases) ? (phrases as string[]) : undefined,
    };
  });
}

function useServices(endpoint: string) {
  const [rows, setRows] = useState<ServiceRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(endpoint);
        const payload = (await res.json()) as ApiResult;
        if (cancelled) return;
        if (!payload.ok) {
          setError(payload.error ?? `HTTP ${res.status}`);
          setRows(null);
        } else {
          setRows(shapeRows(payload));
          setError(null);
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
  }, [endpoint]);

  return { rows, loading, error };
}

export function DataComparePage() {
  const raw = useServices('/api/services/raw');
  const enriched = useServices('/api/services/enriched');

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Raw vs AI-Ready Data</h2>
        <p className="text-muted-foreground mt-1">
          Same 20 services — enriched rows add intent tags and bilingual user phrases for
          embedding and metric joins.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <ServiceColumn title="Raw catalog" loading={raw.loading} error={raw.error} rows={raw.rows} mode="raw" />
        <ServiceColumn
          title="AI-ready enriched"
          loading={enriched.loading}
          error={enriched.error}
          rows={enriched.rows}
          mode="enriched"
        />
      </div>
    </div>
  );
}

function ServiceColumn({
  title,
  loading,
  error,
  rows,
  mode,
}: {
  title: string;
  loading: boolean;
  error: string | null;
  rows: ServiceRow[] | null;
  mode: 'raw' | 'enriched';
}) {
  return (
    <Card className="shadow-lg min-h-[480px]">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {error && <div className="text-destructive text-sm">{error}</div>}
        {loading && (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}
        {!loading && rows && (
          <ul className="space-y-4 max-h-[640px] overflow-y-auto pr-2">
            {rows.map((row) => (
              <li key={row.service_id} className="border rounded-lg p-3">
                <div className="flex items-center gap-2 font-semibold">
                  <span>{row.icon ?? '📦'}</span>
                  {row.name}
                  <Badge variant="outline" className="ml-auto">{row.service_id}</Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-1">{row.category}</div>
                <p className="text-sm mt-2">{row.description}</p>
                {mode === 'enriched' && row.intent_tags && row.intent_tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {row.intent_tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                    ))}
                  </div>
                )}
                {mode === 'enriched' && row.user_intent_phrases && row.user_intent_phrases.length > 0 && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Phrases: {row.user_intent_phrases.slice(0, 3).join(' · ')}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
