import { Plugin, toPlugin, ResourceType, getExecutionContext, type PluginManifest } from '@databricks/appkit';
import type { IAppRouter } from '@databricks/appkit';
import type { Request, Response } from 'express';
import {
  LLM_MODEL,
  TRACE_DESTINATION,
  UC_FUNCTIONS,
  type AgentKind,
  type AgentRequest,
  type AgentResponse,
  type AgentToolCall,
} from './search-config.js';

const VIBE_INSTRUCTIONS =
  'You are a Yape fintech assistant. You only have access to a single tool that performs ' +
  'a keyword/semantic lookup over the raw service catalog (name + category + description). ' +
  'You CANNOT answer analytical questions (top services by region, average ticket size, ' +
  'adoption metrics) because you do not have a metric/aggregation tool. If asked an ' +
  'analytical question, do your best with what the search tool returns and be honest about ' +
  'the limits. Answer in the user\'s language. Be concise.';

const READY_INSTRUCTIONS =
  'You are a Yape fintech assistant with access to AI-ready data on the Databricks platform. ' +
  'You have three tools:\n' +
  '- search_yape_services_enriched(query): semantic catalog search backed by enriched embeddings (intent tags, bilingual phrases). Use to resolve user questions and look up service ids/names.\n' +
  '- top_services_by_region(region, months_back): governed metric view returning services ranked by distinct-user adoption. Use for "what is popular in X?" / "top services in Lima this month".\n' +
  '- avg_ticket_by_cohort(service_id): governed metric view returning avg/median ticket size by age cohort for a specific service. Use for "what do users spend on X?" / "ticket size by age".\n\n' +
  'For analytical questions, ALWAYS prefer the metric-view tools over the search tool. ' +
  'For "popular service in Lima" → top_services_by_region. For "ticket size for loans by age" → ' +
  'first resolve the service id via search_yape_services_enriched, then call avg_ticket_by_cohort. ' +
  'Answer in the user\'s language. Include numbers from the tool output verbatim and explain briefly.';

const VIBE_TOOLS = [
  {
    type: 'uc_function',
    uc_function: {
      name: UC_FUNCTIONS.searchRaw,
      description:
        'Search the Yape service catalog over RAW name + category + description fields.',
    },
  },
];

const READY_TOOLS = [
  {
    type: 'uc_function',
    uc_function: {
      name: UC_FUNCTIONS.searchEnriched,
      description:
        'Search the AI-READY enriched Yape catalog (semantic descriptions, intent tags, bilingual phrases). Best for intent-style queries.',
    },
  },
  {
    type: 'uc_function',
    uc_function: {
      name: UC_FUNCTIONS.topServicesByRegion,
      description:
        'Rank Yape services by distinct-user adoption in a region over the trailing N months. Backed by governed metric view.',
    },
  },
  {
    type: 'uc_function',
    uc_function: {
      name: UC_FUNCTIONS.avgTicketByCohort,
      description:
        'Get avg / median ticket size for a service broken out by age cohort. Backed by governed metric view.',
    },
  },
];

class SearchPlugin extends Plugin {
  static manifest = {
    name: 'search',
    displayName: 'Yape Agents',
    description: 'Two-agent comparison: vibe-coded vs AI-ready data',
    resources: {
      required: [
        {
          type: ResourceType.SQL_WAREHOUSE,
          alias: 'warehouse',
          resourceKey: 'sqlWarehouse',
          description: 'SQL warehouse for catalog reads',
          permission: 'CAN_USE',
          fields: {
            id: { env: 'DATABRICKS_WAREHOUSE_ID', description: 'Warehouse ID' },
          },
        },
      ],
      optional: [],
    },
  } satisfies PluginManifest<'search'>;

  injectRoutes(router: IAppRouter): void {
    this.route(router, {
      name: 'agentRun',
      method: 'post',
      path: '/agents/run',
      handler: async (req, res) => {
        await this.asUser(req).handleAgentRun(req, res);
      },
    });
  }

  private async handleAgentRun(req: Request, res: Response): Promise<void> {
    const body = req.body as AgentRequest;
    const query = body?.query?.trim();
    const agent: AgentKind = body?.agent === 'ready' ? 'ready' : 'vibe';

    if (!query) {
      res.status(400).json({ error: 'query is required' });
      return;
    }

    const started = Date.now();
    try {
      const result = await this.runAgent(query, agent);
      const response: AgentResponse = {
        query,
        agent,
        final_answer: result.final_answer,
        tool_calls: result.tool_calls,
        latency_ms: Date.now() - started,
        trace_url: result.trace_url,
      };
      res.json(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Agent failed';
      const response: AgentResponse = {
        query,
        agent,
        final_answer: '',
        tool_calls: [],
        latency_ms: Date.now() - started,
        error: message,
      };
      res.status(502).json(response);
    }
  }

  private async runAgent(
    query: string,
    agent: AgentKind,
  ): Promise<{ final_answer: string; tool_calls: AgentToolCall[]; trace_url?: string }> {
    const client = getExecutionContext().client;
    const isReady = agent === 'ready';
    const payload = {
      model: LLM_MODEL,
      input: query,
      instructions: isReady ? READY_INSTRUCTIONS : VIBE_INSTRUCTIONS,
      tools: isReady ? READY_TOOLS : VIBE_TOOLS,
      max_output_tokens: 1024,
      trace_destination: TRACE_DESTINATION,
      metadata: { agent_kind: agent },
    };

    const response = (await client.apiClient.request({
      path: '/ai-gateway/mlflow/v1/responses',
      method: 'POST',
      headers: new Headers({ 'Content-Type': 'application/json' }),
      raw: false,
      payload,
    })) as Record<string, unknown>;

    const { final_answer, tool_calls } = this.parseSupervisorOutput(response);
    const traceId =
      typeof response.trace_id === 'string'
        ? response.trace_id
        : typeof response.id === 'string'
          ? response.id
          : undefined;
    const host = await client.apiClient.host;
    const trace_url = traceId
      ? `${host.origin}/ml/experiments/traces?query=trace_id='${traceId}'`
      : undefined;

    return { final_answer, tool_calls, trace_url };
  }

  private parseSupervisorOutput(payload: Record<string, unknown>): {
    final_answer: string;
    tool_calls: AgentToolCall[];
  } {
    const output = Array.isArray(payload.output) ? (payload.output as Array<Record<string, unknown>>) : [];
    const tool_calls: AgentToolCall[] = [];
    const pendingCalls = new Map<string, AgentToolCall>();
    let final_answer = '';

    for (const item of output) {
      if (!item || typeof item !== 'object') continue;
      const t = item.type;
      if (t === 'function_call' && typeof item.name === 'string') {
        const callId = String(item.call_id ?? item.id ?? `${item.name}-${pendingCalls.size}`);
        const call: AgentToolCall = {
          name: String(item.name),
          arguments: typeof item.arguments === 'string' ? item.arguments : JSON.stringify(item.arguments ?? {}),
          status: 'ok',
        };
        pendingCalls.set(callId, call);
        tool_calls.push(call);
      } else if (t === 'function_call_output') {
        const callId = String(item.call_id ?? '');
        const out = typeof item.output === 'string' ? item.output : JSON.stringify(item.output ?? '');
        const matched = pendingCalls.get(callId);
        if (matched) matched.output = out;
        else tool_calls.push({ name: 'unknown', arguments: '', output: out, status: 'ok' });
      } else if (t === 'message') {
        const content = Array.isArray(item.content) ? item.content : [];
        for (const part of content) {
          if (part && typeof part === 'object' && 'text' in part) {
            const text = String((part as Record<string, unknown>).text ?? '');
            if (text) final_answer += (final_answer ? '\n' : '') + text;
          }
        }
      }
    }

    if (!final_answer && tool_calls.length > 0) {
      final_answer = '(agent returned tool output without a final message)';
    }

    return { final_answer, tool_calls };
  }
}

export const searchPlugin = toPlugin(SearchPlugin);
