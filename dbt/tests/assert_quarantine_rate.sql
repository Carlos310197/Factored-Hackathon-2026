-- Error when the latest load run quarantined more than quarantine_max_ratio of the rows it loaded
-- (per run, not cumulative: one bad daily partition must trip the gate even against millions of older rows).
with run as (
    select run_id from {{ source('meta', 'run_manifest') }} order by loaded_at desc limit 1
), files as (
    select file_path, rows_loaded from {{ source('meta', 'run_manifest') }} where run_id = (select run_id from run)
), q as (
    select count(*) as n from {{ ref('quarantine') }} qr join files f on endswith(qr._source_file, f.file_path)
), t as (
    select coalesce(sum(rows_loaded), 0) as n from files
)
select q.n as quarantined, t.n as loaded from q, t where t.n > 0 and q.n > {{ var('quarantine_max_ratio', 0.01) }} * t.n
