{{ config(severity = 'warn') }}
select transaction_id, transaction_ts, process_date
from {{ ref('stg_transactions') }}
where abs(datediff('day', transaction_ts::date, process_date)) > 1
