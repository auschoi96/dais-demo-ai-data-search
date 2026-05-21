export const CATALOG = 'ac_demo';
export const SCHEMA = 'agents';

export type AgentKind = 'vibe' | 'ready';

export interface AgentToolCall {
  call_id: string;
  name: string;
  args: Record<string, unknown>;
  output?: string;
  is_error?: boolean;
  started_at: number;
}

export interface AgentRunState {
  agent: AgentKind;
  status: 'idle' | 'running' | 'ok' | 'error';
  tool_calls: AgentToolCall[];
  text: string;
  tokens: number;
  cost_usd: number;
  latency_ms: number;
  started_at: number;
  finished_at?: number;
  error?: string;
}

export type StreamEvent =
  | { type: 'session_start'; agent: AgentKind; ts: number }
  | { type: 'text_delta'; agent: AgentKind; text: string }
  | { type: 'tool_call'; agent: AgentKind; call_id: string; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; agent: AgentKind; call_id: string; output: string; is_error: boolean }
  | { type: 'done'; agent: AgentKind; tokens: number; cost_usd: number; latency_ms: number; num_tool_calls: number }
  | { type: 'error'; agent: AgentKind; message: string; latency_ms?: number };
