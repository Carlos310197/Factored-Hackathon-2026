{{ config(materialized='table') }}
with latest as (
    select * from {{ source('raw', 'products') }}
    qualify row_number() over (partition by product_id order by _loaded_at desc, _file_row desc) = 1
), typed as (
    select
        product_id, customer_id, product_type,
        right(product_number, 4) as product_last4,
        currency,
        try_to_decimal(current_balance, 15, 2) as current_balance,
        try_to_decimal(credit_limit, 15, 2) as credit_limit,
        try_to_decimal(interest_rate, 5, 2) as interest_rate,
        try_to_date(opening_date, 'YYYY-MM-DD') as opening_date,
        try_to_date(expiration_date, 'YYYY-MM-DD') as expiration_date,
        product_status,
        case when has_linked_app = 'True' then true when has_linked_app = 'False' then false end as has_linked_app,
        try_to_number(days_past_due) as days_past_due,
        try_to_timestamp_ntz(last_transaction_date, 'YYYY-MM-DD HH24:MI:SS') as last_transaction_date,
        try_to_timestamp_ntz(last_updated, 'YYYY-MM-DD HH24:MI:SS') as last_updated,
        current_balance as _raw_balance, opening_date as _raw_opening_date,
        _source_file, _file_row, _loaded_at, object_construct(*) as raw_row
    from latest
)
select * exclude (_raw_balance, _raw_opening_date),
    case
        when product_id is null then 'null:product_id'
        when customer_id is null then 'null:customer_id'
        when _raw_balance is null then 'null:current_balance'
        when current_balance is null then 'cast_failed:current_balance'
        when _raw_opening_date is not null and opening_date is null then 'cast_failed:opening_date'
        when product_type not in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Crédito','Tarjeta Débito','Préstamo Personal','Préstamo Hipotecario','Inversión','Seguro') then 'enum:product_type'
        when product_status not in ('Active','Blocked','Closed','Suspended') then 'enum:product_status'
    end as _quarantine_reason
from typed
