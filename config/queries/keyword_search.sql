-- @param query STRING
-- @param limit INT
SELECT
  service_id,
  name,
  category,
  description,
  search_text AS searchable_text
FROM ac_demo.agents.yape_services_raw
WHERE
  lower(search_text) LIKE concat('%', lower(:query), '%')
  OR lower(name) LIKE concat('%', lower(:query), '%')
ORDER BY
  CASE WHEN lower(name) LIKE concat('%', lower(:query), '%') THEN 0 ELSE 1 END,
  name
LIMIT :limit;
