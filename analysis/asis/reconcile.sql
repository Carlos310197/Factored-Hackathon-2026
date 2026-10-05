-- Run in Snowflake (role PIPELINE_ROLE) once the curated marts exist. Save the single JSON value as
-- analysis/asis/out/curated_counts.json and pass it with `python -m asis.run --curated-counts`.
select object_construct(
  'interactions_n', (select count(*) from LATAM_BANK.CURATED.FCT_INTERACTION
                     where process_date between '2025-06-17' and '2026-06-17'),
  'complaints_n', (select count(*) from LATAM_BANK.CURATED.FCT_COMPLAINT
                   where process_date between '2025-06-17' and '2026-06-17'),
  'transaccional_fcr', (select avg(iff(was_resolved, 1, 0)) from LATAM_BANK.CURATED.FCT_INTERACTION
                        where process_date between '2025-06-17' and '2026-06-17'
                          and reason_category = 'Transaccional')) as counts;
