SELECT
  service_id,
  name,
  category,
  icon,
  description,
  search_text
FROM ac_demo.agents.yape_services_raw
ORDER BY service_id;
