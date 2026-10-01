{{ config(materialized='table') }}
{% set parts = [('typed_transactions','transaction_id'), ('typed_customers','customer_id'), ('typed_products','product_id'),
                ('typed_complaints','complaint_id'), ('typed_interactions','interaction_id')] %}
{% for model, pk in parts %}
select '{{ model | replace("typed_", "") }}' as table_name, {{ pk }} as pk_value, _quarantine_reason as reason,
       _source_file, _loaded_at, raw_row
from {{ ref(model) }} where _quarantine_reason is not null
{% if not loop.last %}union all{% endif %}
{% endfor %}
