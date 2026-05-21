import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@databricks/appkit-ui/react';
import { TIER_LABELS } from '../../lib/search-api';
import type { TierRun } from '../../lib/search-api';
import type { SearchResult } from '../../../../shared/search-types';

export function TierResultColumn({ run }: { run: TierRun }) {
  return (
    <Card className="flex flex-col min-h-[300px]">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <div className="flex items-center gap-2">
            <Badge variant={run.tier === '2' ? 'default' : 'outline'}>T{run.tier}</Badge>
            <span className="text-foreground">{TIER_LABELS[run.tier]}</span>
          </div>
          {run.status === 'ok' && run.response && (
            <Badge variant="secondary" className="font-mono text-xs">
              {run.response.latency_ms}ms
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1">
        {run.status === 'pending' && (
          <div className="space-y-3">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        )}

        {run.status === 'error' && (
          <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
            {run.error}
          </div>
        )}

        {run.status === 'ok' && run.response && run.response.results.length === 0 && (
          <div className="text-sm text-muted-foreground italic py-6 text-center">
            No matches — raw data often misses intent phrasing.
          </div>
        )}

        {run.status === 'ok' && run.response && run.response.results.length > 0 && (
          <ul className="space-y-2">
            {run.response.results.map((item, idx) => (
              <ResultRow key={`${item.service_id}-${idx}`} item={item} rank={idx + 1} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ResultRow({ item, rank }: { item: SearchResult; rank: number }) {
  return (
    <li className="border rounded-md p-2.5 flex gap-2.5 items-start hover:bg-muted/50 transition-colors">
      <span className="text-xs font-mono text-muted-foreground pt-0.5 w-4">{rank}</span>
      <span className="text-xl leading-none">{item.icon ?? '🔎'}</span>
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-sm truncate">{item.name}</div>
        <div className="text-xs text-muted-foreground truncate">{item.category}</div>
        <div className="text-xs mt-1 line-clamp-2">{item.description}</div>
        {item.score != null && (
          <div className="text-[10px] text-muted-foreground mt-1 font-mono">
            {item.score.toFixed(3)}
          </div>
        )}
      </div>
    </li>
  );
}
