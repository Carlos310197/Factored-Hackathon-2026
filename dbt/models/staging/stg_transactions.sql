{{ config(materialized='view') }}
select * exclude (_quarantine_reason, raw_row) from {{ ref('typed_transactions') }} where _quarantine_reason is null
