SELECT
  service_id,
  name,
  category,
  icon,
  description,
  semantic_description,
  intent_tags,
  user_intent_phrases,
  synonyms,
  target_segments,
  embedding_text
FROM ac_demo.agents.yape_services_enriched
ORDER BY service_id;
