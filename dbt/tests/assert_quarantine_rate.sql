with q as (select count(*) as n from {{ ref('quarantine') }}),
     t as (select sum(rows_loaded) as n from {{ source('meta', 'run_manifest') }})
select q.n as quarantined, t.n as loaded from q, t where q.n > {{ var('quarantine_max_ratio', 0.01) }} * t.n
