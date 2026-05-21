import { Plugin, toPlugin, ResourceType, getExecutionContext, type PluginManifest } from '@databricks/appkit';
import type { IAppRouter } from '@databricks/appkit';
import type { Request, Response } from 'express';
import {
  INDEXES,
  LLM_MODEL,
  TABLES,
  TRACE_DESTINATION,
  UC_FUNCTION,
  type IndexVariant,
  type SearchRequest,
  type SearchResponse,
  type SearchResult,
} from './search-config.js';

const DEFAULT_LIMIT = 4;
const RESULT_COLUMNS = ['service_id', 'name', 'category', 'description', 'icon'];

function escapeSql(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "''");
}

class SearchPlugin extends Plugin {
  static manifest = {
    name: 'search',
    displayName: 'Yape Search',
    description: 'Four-tier search demo routes (keyword, vector, supervisor)',
    resources: {
      required: [
        {
          type: ResourceType.SQL_WAREHOUSE,
          alias: 'warehouse',
          resourceKey: 'sqlWarehouse',
          description: 'SQL warehouse for keyword search and catalog reads',
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
      name: 'search',
      method: 'post',
      path: '/query',
      handler: async (req, res) => {
        await this.asUser(req).handleSearch(req, res);
      },
    });
  }

  private async handleSearch(req: Request, res: Response): Promise<void> {
    const body = req.body as SearchRequest;
    const query = body?.query?.trim();
    const tier = body?.tier ?? '0';
    const limit = body?.limit ?? DEFAULT_LIMIT;

    if (!query) {
      res.status(400).json({ error: 'query is required' });
      return;
    }

    const started = Date.now();
    try {
      let results: SearchResult[] = [];
      let trace_url: string | undefined;

      switch (tier) {
        case '0':
          results = await this.keywordSearch(query, limit);
          break;
        case '1':
          results = await this.vectorSearch(query, 'raw', limit);
          break;
        case '2':
          results = await this.vectorSearch(query, 'enriched', limit);
          break;
        case '3':
          ({ results, trace_url } = await this.supervisorSearch(query, limit));
          break;
        default:
          res.status(400).json({ error: `Unknown tier: ${tier}` });
          return;
      }

      const response: SearchResponse = {
        query,
        tier,
        results,
        latency_ms: Date.now() - started,
        trace_url,
      };
      res.json(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Search failed';
      res.status(502).json({ error: message });
    }
  }

  private warehouseId(): string {
    const id = process.env.DATABRICKS_WAREHOUSE_ID;
    if (!id) {
      throw new Error('DATABRICKS_WAREHOUSE_ID is not configured');
    }
    return id;
  }

  private async keywordSearch(query: string, limit: number): Promise<SearchResult[]> {
    const w = getExecutionContext().client;
    const sql = `
      SELECT service_id, name, category, icon, description
      FROM ${TABLES.raw}
      WHERE lower(search_text) LIKE '%${escapeSql(query.toLowerCase())}%'
         OR lower(name) LIKE '%${escapeSql(query.toLowerCase())}%'
      ORDER BY CASE WHEN lower(name) LIKE '%${escapeSql(query.toLowerCase())}%' THEN 0 ELSE 1 END
      LIMIT ${limit}
    `;
    const resp = await w.statementExecution.executeStatement({
      warehouse_id: this.warehouseId(),
      statement: sql,
      wait_timeout: '30s',
    });
    return this.rowsFromStatement(resp, '0');
  }

  private async vectorSearch(
    query: string,
    variant: IndexVariant,
    limit: number,
  ): Promise<SearchResult[]> {
    const indexName = variant === 'enriched' ? INDEXES.enriched : INDEXES.raw;
    const tier: '1' | '2' = variant === 'enriched' ? '2' : '1';
    const client = getExecutionContext().client;

    const result = await client.vectorSearchIndexes.queryIndex({
      index_name: indexName,
      query_text: query,
      columns: RESULT_COLUMNS,
      num_results: limit,
    });

    const columnNames = (result.manifest?.columns ?? []).map((c) => c.name ?? '');
    const rows = result.result?.data_array ?? [];

    return rows.map((row) => {
      const record: Record<string, string> = {};
      columnNames.forEach((col, idx) => {
        record[col] = row[idx] ?? '';
      });
      const scoreIdx = columnNames.findIndex((c) => c === 'score' || c === '_score' || c === 'search_score');
      const scoreRaw = scoreIdx >= 0 ? row[scoreIdx] : row[row.length - 1];
      const score = typeof scoreRaw === 'number' ? scoreRaw : Number(scoreRaw);

      return {
        service_id: record.service_id ?? '',
        name: record.name ?? '',
        category: record.category ?? '',
        description: record.description ?? '',
        icon: record.icon || undefined,
        score: Number.isFinite(score) ? score : undefined,
        tier,
        latency_ms: 0,
      };
    });
  }

  private async supervisorSearch(
    query: string,
    limit: number,
  ): Promise<{ results: SearchResult[]; trace_url?: string }> {
    const client = getExecutionContext().client;
    const payload = {
      model: LLM_MODEL,
      input: query,
      instructions:
        'You are a Yape fintech assistant. Use the search_yape_services tool to find relevant services for the user intent. Return concise ranked results.',
      tools: [
        {
          type: 'uc_function',
          uc_function: {
            name: UC_FUNCTION,
            description:
              'Search Yape service catalog by user intent. Returns ranked services from Vector Search.',
          },
        },
      ],
      tool_choice: 'required',
      max_output_tokens: 1024,
      trace_destination: TRACE_DESTINATION,
      metadata: { demo_tier: '3', index_variant: 'raw' },
    };

    const response = (await client.apiClient.request({
      path: '/ai-gateway/mlflow/v1/responses',
      method: 'POST',
      headers: new Headers({ 'Content-Type': 'application/json' }),
      raw: false,
      payload,
    })) as Record<string, unknown>;

    const results = this.parseSupervisorResults(response, limit);
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

    return { results, trace_url };
  }

  private parseSupervisorResults(payload: Record<string, unknown>, limit: number): SearchResult[] {
    const output = payload.output;
    if (!Array.isArray(output)) {
      return [];
    }

    const parsed: SearchResult[] = [];
    for (const item of output) {
      if (!item || typeof item !== 'object') continue;
      const record = item as Record<string, unknown>;
      if (record.type === 'function_call_output' && typeof record.output === 'string') {
        try {
          const toolResult = JSON.parse(record.output) as Array<Record<string, unknown>>;
          for (const row of toolResult) {
            parsed.push({
              service_id: String(row.service_id ?? ''),
              name: String(row.name ?? ''),
              category: String(row.category ?? ''),
              description: String(row.description ?? ''),
              score: typeof row.score === 'number' ? row.score : undefined,
              tier: '3',
              latency_ms: 0,
            });
          }
        } catch {
          // ignore malformed tool output
        }
      }
    }

    if (parsed.length > 0) {
      return parsed.slice(0, limit);
    }

    const textBlock = output.find(
      (item) =>
        item &&
        typeof item === 'object' &&
        (item as Record<string, unknown>).type === 'message',
    ) as Record<string, unknown> | undefined;

    if (textBlock && Array.isArray(textBlock.content)) {
      const text = textBlock.content
        .map((part) =>
          part && typeof part === 'object' && 'text' in part
            ? String((part as Record<string, unknown>).text ?? '')
            : '',
        )
        .join('\n');
      if (text) {
        parsed.push({
          service_id: 'agent',
          name: 'Supervisor response',
          category: 'Agent',
          description: text.slice(0, 500),
          tier: '3',
          latency_ms: 0,
        });
      }
    }

    return parsed.slice(0, limit);
  }

  private rowsFromStatement(resp: { manifest?: { schema?: { columns?: Array<{ name?: string }> } }; result?: { data_array?: Array<Array<string | null>> } }, tier: '0' | '1' | '2' | '3'): SearchResult[] {
    const columns = resp.manifest?.schema?.columns?.map((c) => c.name ?? '') ?? [];
    const rows = resp.result?.data_array ?? [];
    return rows.map((row) => {
      const record: Record<string, string> = {};
      columns.forEach((col, idx) => {
        record[col] = row[idx] ?? '';
      });
      return {
        service_id: record.service_id ?? '',
        name: record.name ?? '',
        category: record.category ?? '',
        description: record.description ?? '',
        icon: record.icon || undefined,
        tier,
        latency_ms: 0,
      };
    });
  }
}

export const searchPlugin = toPlugin(SearchPlugin);
