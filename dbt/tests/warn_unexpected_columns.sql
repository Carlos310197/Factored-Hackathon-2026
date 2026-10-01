{{ config(severity = 'warn') }}
-- RAW columns not declared in sources.yml (schema evolution landed something new).
{% set expected = [] %}
{% for src in graph.sources.values() if src.source_name == 'raw' %}
  {% for col in src.columns.values() %}
    {% do expected.append("('" ~ src.name | upper ~ "','" ~ col.name | upper ~ "')") %}
  {% endfor %}
{% endfor %}
with declared as (
  select column1 as table_name, column2 as column_name from values {{ expected | join(', ') }}
), actual as (
  select table_name, column_name
  from {{ target.database }}.information_schema.columns
  where table_schema = 'RAW' and table_name in ('CUSTOMERS','PRODUCTS','TRANSACTIONS','COMPLAINTS','INTERACTIONS')
    and left(column_name, 1) <> '_'
)
select a.table_name, a.column_name
from actual a left join declared d using (table_name, column_name)
where d.column_name is null
