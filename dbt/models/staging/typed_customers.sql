{{ config(materialized='table') }}
with latest as (
    select * -- a restated file replaces its whole partition: keep only each file's latest load, then dedup by key
    from (select * from {{ source('raw', 'customers') }} qualify _loaded_at = max(_loaded_at) over (partition by _source_file))
    -- null keys get a per-row identity (each reaches quarantine); newer file version wins, scan order only breaks ties
    qualify row_number() over (partition by coalesce(customer_id, _source_file || ':' || _file_row)
        order by _file_last_modified desc nulls last, _loaded_at desc, _source_file desc, _file_row desc) = 1
), typed as (
    select
        customer_id, city, state, country, detected_accent, segment, customer_status,
        try_to_timestamp_ntz(registration_date, 'YYYY-MM-DD HH24:MI:SS')::date as registration_date,
        case when accepts_marketing = 'True' then true when accepts_marketing = 'False' then false end as accepts_marketing,
        try_to_timestamp_ntz(last_updated, 'YYYY-MM-DD HH24:MI:SS') as last_updated,
        registration_date as _raw_registration_date, last_updated as _raw_last_updated,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_registration_date, _raw_last_updated),
    case
        when customer_id is null then 'null:customer_id'
        when country is null then 'null:country'
        when _raw_registration_date is not null and registration_date is null then 'cast_failed:registration_date'
        when _raw_last_updated is not null and last_updated is null then 'cast_failed:last_updated'
        when customer_status is null then 'null:customer_status'
    end as _quarantine_reason
from typed
