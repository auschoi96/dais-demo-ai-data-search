-- Placeholder summary query; benchmark results are computed by eval/run_benchmark.py
-- and can be loaded into a results table before demo day.
SELECT
  'tier0' AS tier,
  0.35 AS hit_at_4,
  0.22 AS mrr,
  5 AS avg_latency_ms
UNION ALL
SELECT 'tier1', 0.45, 0.28, 120
UNION ALL
SELECT 'tier2', 0.90, 0.72, 130
UNION ALL
SELECT 'tier3', 0.50, 0.31, 2500;
