-- Read-only. Run with `uv run python analysis/asis/curated_counts.py` from the repo root (writes
-- analysis/asis/out/curated_counts.json), then pass it with `python -m asis.run --curated-counts`.
select object_construct(
  'interactions_n', (select count(*) from LATAM_BANK.CURATED.FCT_INTERACTION
                     where process_date between '2025-06-17' and '2026-06-17'),
  'complaints_n', (select count(*) from LATAM_BANK.CURATED.FCT_COMPLAINT
                   where process_date between '2025-06-17' and '2026-06-17'),
  'transaccional_fcr', (select avg(iff(was_resolved, 1, 0)) from LATAM_BANK.CURATED.FCT_INTERACTION
                        where process_date between '2025-06-17' and '2026-06-17'
                          and reason_category = 'Transaccional'),
  'disputes_n', (select count(*) from LATAM_BANK.CURATED.FCT_COMPLAINT
                 where process_date between '2025-06-17' and '2026-06-17'
                   and subcategory in ('Cargo no reconocido', 'Cobro indebido')),
  'cargo_no_reconocido_n', (select count(*) from LATAM_BANK.CURATED.FCT_COMPLAINT
                            where process_date between '2025-06-17' and '2026-06-17'
                              and subcategory = 'Cargo no reconocido'),
  -- context: what the pipeline dropped between the raw load and the marts
  'quarantine_rows', (select count(*) from LATAM_BANK.STAGING.QUARANTINE),
  'raw_interactions_n', (select count(*) from LATAM_BANK.RAW.INTERACTIONS
                         where process_date between '2025-06-17' and '2026-06-17'),
  'raw_complaints_n', (select count(*) from LATAM_BANK.RAW.COMPLAINTS
                       where process_date between '2025-06-17' and '2026-06-17')) as counts;
