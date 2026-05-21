SELECT
  query,
  language,
  expected_service_ids,
  tier
FROM ac_demo.agents.yape_search_eval
ORDER BY
  CASE tier
    WHEN 'easy' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'hard' THEN 3
    ELSE 4
  END,
  query;
