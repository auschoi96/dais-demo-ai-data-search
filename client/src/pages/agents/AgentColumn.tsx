import { useState } from 'react';
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@databricks/appkit-ui/react';
import { AGENT_META } from '../../lib/search-api';
import type { AgentRunState, AgentToolCall } from '../../../../shared/search-types';

export function AgentColumn({ run, now }: { run: AgentRunState; now: number }) {
  const meta = AGENT_META[run.agent];
  const isReady = run.agent === 'ready';
  const elapsedMs =
    run.status === 'ok' || run.status === 'error'
      ? run.latency_ms
      : run.started_at
        ? now - run.started_at
        : 0;

  return (
    <Card className="flex flex-col min-h-[300px] h-full">
      <CardHeader className="pb-3 border-b">
        <CardTitle className="flex items-center justify-between text-base">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isReady ? 'bg-success' : 'bg-warning'
              } ${run.status === 'running' ? 'animate-pulse' : ''}`}
            />
            <span className="text-foreground">{meta.label}</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="font-mono text-xs tabular-nums">
              {(elapsedMs / 1000).toFixed(1)}s
            </Badge>
            {run.tokens > 0 && (
              <Badge variant="outline" className="font-mono text-xs tabular-nums">
                {run.tokens.toLocaleString()} tok
              </Badge>
            )}
            <Badge variant="outline" className="font-mono text-xs tabular-nums">
              {run.tool_calls.length} call{run.tool_calls.length === 1 ? '' : 's'}
            </Badge>
          </div>
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">{meta.blurb}</p>
      </CardHeader>

      <CardContent className="flex-1 pt-3 overflow-auto">
        <div className="space-y-2">
          {run.tool_calls.map((tc) => (
            <ToolCallRow key={tc.call_id || `${tc.name}-${tc.started_at}`} call={tc} />
          ))}

          {run.text && (
            <div className="border-l-2 border-primary/40 pl-3 py-1 mt-3 bg-primary/5 rounded-r-md">
              <div className="text-[10px] uppercase tracking-wider text-primary mb-1">
                Answer
              </div>
              <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                {run.text}
              </div>
            </div>
          )}

          {run.status === 'error' && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
              {run.error}
            </div>
          )}

          {run.status === 'running' && run.tool_calls.length === 0 && !run.text && (
            <div className="text-sm text-muted-foreground italic flex items-center gap-2">
              <Dot /> Thinking…
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ToolCallRow({ call }: { call: AgentToolCall }) {
  const [open, setOpen] = useState(false);
  const shortName = call.name;
  const argsPreview = truncateArgs(JSON.stringify(call.args));
  const pending = call.output === undefined && !call.is_error;
  const errorish = call.is_error || (call.output ?? '').startsWith('Claude requested permissions');

  return (
    <div
      className={`border rounded-md text-xs transition-colors ${
        errorish ? 'border-destructive/30 bg-destructive/5' : ''
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-2 py-1.5 flex items-center gap-2 hover:bg-muted/50 text-left"
      >
        <span className={`transition-transform ${open ? 'rotate-90' : ''}`}>›</span>
        <code className="font-mono font-medium text-foreground">{shortName}</code>
        {pending ? (
          <Dot />
        ) : errorish ? (
          <span className="text-destructive text-[10px]">denied</span>
        ) : (
          <span className="text-success text-[10px]">✓</span>
        )}
        <span className="text-muted-foreground truncate flex-1 font-mono text-[10px]">
          {argsPreview}
        </span>
      </button>
      {open && (
        <div className="px-2 pb-2 pt-1 border-t space-y-1.5">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Arguments
            </div>
            <pre className="font-mono text-[10px] bg-muted/50 p-1.5 rounded overflow-x-auto whitespace-pre-wrap break-all">
              {JSON.stringify(call.args, null, 2)}
            </pre>
          </div>
          {call.output !== undefined && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                Output
              </div>
              <pre className="font-mono text-[10px] bg-muted/50 p-1.5 rounded overflow-x-auto whitespace-pre-wrap max-h-48">
                {prettyJson(call.output)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function truncateArgs(raw: string, n = 80): string {
  const oneLine = raw.replace(/\s+/g, ' ').trim();
  return oneLine.length > n ? oneLine.slice(0, n) + '…' : oneLine;
}

function Dot() {
  return <span className="inline-block w-1.5 h-1.5 rounded-full bg-warning animate-pulse" />;
}
