{{ config(materialized='table') }}
with latest as (
    select *
    from {{ source('raw', 'transactions') }}
    qualify row_number() over (partition by transaction_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        transaction_id,
        try_to_timestamp_ntz(transaction_date, 'YYYY-MM-DD HH24:MI:SS') as transaction_ts,
        try_to_date(process_date, 'YYYY-MM-DD')                         as process_date,
        product_id,
        customer_id,
        transaction_type,
        transaction_category,
        try_to_decimal(amount, 15, 2)                                    as amount,
        currency,
        try_to_decimal(amount_usd, 15, 2)                                as amount_usd,
        channel,
        merchant_name,
        merchant_category,
        transaction_country,
        transaction_city,
        transaction_status,
        response_code,
        case when is_fraud = 'True' then true when is_fraud = 'False' then false end as is_fraud,
        try_to_decimal(fraud_score, 5, 2)                                as fraud_score,
        -- raw copies kept only to build reasons
        transaction_date as _raw_transaction_date, amount as _raw_amount, is_fraud as _raw_is_fraud,
        _source_file, _file_row, _loaded_at,
        object_construct(*) as raw_row
    from latest
)
select
    * exclude (_raw_transaction_date, _raw_amount, _raw_is_fraud),
    case
        when transaction_id is null then 'null:transaction_id'
        when _raw_transaction_date is null then 'null:transaction_date'
        when transaction_ts is null then 'cast_failed:transaction_date'
        when process_date is null then 'cast_failed:process_date'
        when product_id is null then 'null:product_id'
        when customer_id is null then 'null:customer_id'
        when _raw_amount is null then 'null:amount'
        when amount is null then 'cast_failed:amount'
        when currency is null then 'null:currency'
        when _raw_is_fraud is not null and is_fraud is null then 'cast_failed:is_fraud'
        when transaction_type not in ('Deposit','Withdrawal','Transfer','Payment','Purchase','Adjustment') then 'enum:transaction_type'
        when transaction_status not in ('Approved','Declined','Pending','Reversed') then 'enum:transaction_status'
        when channel not in ('ATM','Branch','Web','App','POS','Transfer') then 'enum:channel'
    end as _quarantine_reason
from typed
