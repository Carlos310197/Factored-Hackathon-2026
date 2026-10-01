select product_id, customer_id, product_type, product_last4, currency, current_balance, credit_limit, interest_rate,
       opening_date, expiration_date, product_status, has_linked_app, days_past_due, last_transaction_date, last_updated
from {{ ref('stg_products') }}
