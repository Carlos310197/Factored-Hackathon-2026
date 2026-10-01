select customer_id, country, city, state, segment, detected_accent, customer_status, registration_date, accepts_marketing, last_updated
from {{ ref('stg_customers') }}
