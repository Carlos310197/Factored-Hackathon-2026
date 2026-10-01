{{ config(materialized='table') }}
with latest as (
    select * -- a restated file replaces its whole partition: keep only each file's latest load, then dedup by key
    from (select * from {{ source('raw', 'complaints') }} qualify _loaded_at = max(_loaded_at) over (partition by _source_file))
    -- null keys get a per-row identity (each reaches quarantine); newer file version wins, scan order only breaks ties
    qualify row_number() over (partition by coalesce(complaint_id, _source_file || ':' || _file_row)
        order by _file_last_modified desc nulls last, _loaded_at desc, _source_file desc, _file_row desc) = 1
), typed as (
    select
        complaint_id,
        try_to_timestamp_ntz(creation_date, 'YYYY-MM-DD HH24:MI:SS') as creation_ts,
        try_to_date(process_date, 'YYYY-MM-DD') as process_date,
        customer_id, case_type, category, subcategory, reception_channel, affected_product_id,
        try_to_decimal(claimed_amount, 15, 2) as claimed_amount,
        currency, priority, status,
        case when sla_breached = 'True' then true when sla_breached = 'False' then false end as sla_breached,
        try_to_double(resolution_days)::number as resolution_days,
        try_to_double(resolution_satisfaction)::number as resolution_satisfaction,
        case when is_repeat_complainer = 'True' then true when is_repeat_complainer = 'False' then false end as is_repeat_complainer,
        try_to_timestamp_ntz(first_response_date, 'YYYY-MM-DD HH24:MI:SS') as first_response_ts,
        try_to_timestamp_ntz(resolution_date, 'YYYY-MM-DD HH24:MI:SS') as resolution_ts,
        try_to_timestamp_ntz(closing_date, 'YYYY-MM-DD HH24:MI:SS') as closing_ts,
        creation_date as _raw_creation_date, claimed_amount as _raw_claimed_amount,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_creation_date, _raw_claimed_amount),
    case
        when complaint_id is null then 'null:complaint_id'
        when creation_ts is null then 'cast_failed:creation_date'
        when process_date is null then 'cast_failed:process_date'
        when customer_id is null then 'null:customer_id'
        when _raw_claimed_amount is not null and claimed_amount is null then 'cast_failed:claimed_amount'
        when case_type not in ('Complaint','Claim','Request','Suggestion') then 'enum:case_type'
        when status not in ('Open','In Process','Escalated','Resolved','Closed','Rejected') then 'enum:status'
        when priority not in ('Low','Medium','High','Critical') then 'enum:priority'
    end as _quarantine_reason
from typed
