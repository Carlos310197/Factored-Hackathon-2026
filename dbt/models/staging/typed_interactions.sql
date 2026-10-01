{{ config(materialized='table') }}
with latest as (
    select * -- a restated file replaces its whole partition: keep only each file's latest load, then dedup by key
    from (select * from {{ source('raw', 'interactions') }} qualify _loaded_at = max(_loaded_at) over (partition by _source_file))
    qualify row_number() over (partition by interaction_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        interaction_id,
        try_to_timestamp_ntz(interaction_date, 'YYYY-MM-DD HH24:MI:SS') as interaction_ts,
        try_to_date(process_date, 'YYYY-MM-DD') as process_date,
        customer_id, channel, interaction_type, reason_category,
        try_to_double(duration_seconds)::number as duration_seconds,
        try_to_double(wait_time_seconds)::number as wait_time_seconds,
        case when was_resolved = 'True' then true when was_resolved = 'False' then false end as was_resolved,
        case when requires_followup = 'True' then true when requires_followup = 'False' then false end as requires_followup,
        case when was_escalated = 'True' then true when was_escalated = 'False' then false end as was_escalated,
        case detected_sentiment
            when 'Muy Positivo' then 'Very Positive' when 'Positivo' then 'Positive' when 'Neutral' then 'Neutral'
            when 'Negativo' then 'Negative' when 'Muy Negativo' then 'Very Negative' end as detected_sentiment,
        try_to_decimal(sentiment_score, 3, 2) as sentiment_score,
        customer_detected_accent,
        case when has_transcript = 'True' then true when has_transcript = 'False' then false end as has_transcript,
        interaction_date as _raw_interaction_date, detected_sentiment as _raw_sentiment,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_interaction_date, _raw_sentiment),
    case
        when interaction_id is null then 'null:interaction_id'
        when interaction_ts is null then 'cast_failed:interaction_date'
        when process_date is null then 'cast_failed:process_date'
        when customer_id is null then 'null:customer_id'
        when _raw_sentiment is not null and detected_sentiment is null then 'enum:detected_sentiment'
        when reason_category not in ('Transaccional','Producto','Queja','Técnico','Comercial','Retención') then 'enum:reason_category'
        when channel not in ('Phone','Web Chat','WhatsApp','Email','App','Web') then 'enum:channel'
    end as _quarantine_reason
from typed
