select complaint_id, creation_ts, process_date, customer_id, case_type, category, subcategory, reception_channel, affected_product_id,
       claimed_amount, currency, priority, status, sla_breached, resolution_days, resolution_satisfaction, is_repeat_complainer,
       first_response_ts, resolution_ts, closing_ts
from {{ ref('stg_complaints') }}
