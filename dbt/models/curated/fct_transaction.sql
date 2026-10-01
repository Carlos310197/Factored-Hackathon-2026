select t.transaction_id, t.transaction_ts, t.process_date, t.product_id, t.customer_id, t.transaction_type, t.transaction_category,
       t.amount, t.currency, t.amount_usd, t.channel, t.merchant_name, t.merchant_category, t.transaction_country, t.transaction_city,
       t.transaction_status, t.response_code,
       case when t.transaction_status = 'Approved' then null else d.reason_key end as decline_reason_key,
       t.is_fraud, t.fraud_score
from {{ ref('stg_transactions') }} t
left join {{ ref('seed_decline_reason') }} d on d.response_code = t.response_code
