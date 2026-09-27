# Materialize small/medium tables from S3 to local parquet (data/ is gitignored), then
# print the evidence needed to pick a workflow: contact reasons, product mix, complaint mix.
import os, duckdb
env = dict(l.strip().split("=", 1) for l in open(".env") if "=" in l and not l.startswith("#"))
B = env["DATA_BUCKET"]
c = duckdb.connect()
c.sql(f"create secret (type s3, key_id '{env['AWS_ACCESS_KEY_ID']}', secret '{env['AWS_SECRET_ACCESS_KEY']}', region '{env['AWS_DEFAULT_REGION']}')")

def mat(name, glob, out):
    if not os.path.exists(out):
        c.sql(f"copy (select * from read_csv('s3://{B}/{glob}', hive_partitioning=true, union_by_name=true, all_varchar=true)) to '{out}'")
    c.sql(f"create view {name} as select * from '{out}'")

mat("i", "data/call_center_interactions/**/*.csv", "data/interactions.parquet")
mat("q", "data/complaints/**/*.csv", "data/complaints.parquet")
mat("p", "data/products.csv", "data/products.parquet")
mat("t", "data/transactions/year=2026/month=05/**/*.csv", "data/transactions_2026_05_sample.parquet")  # ponytail: one-month sample, full table is 808MB

def s(title, sql):
    print(f"\n=== {title} ==="); print(c.sql(sql).fetchdf().to_string(index=False))

s("contact_reason x category", """
select reason_category, contact_reason, count(*) n, round(100*count(*)/sum(count(*)) over(),1) pct,
  round(100*avg((was_resolved='True')::int),1) fcr, round(100*avg((requires_followup='True')::int),1) followup,
  round(100*avg((has_transcript='True')::int),1) transcript_pct, round(median(try_cast(duration_seconds as int))/60,1) med_min,
  round(100*avg((detected_sentiment ilike '%negativ%')::int),1) neg_pct
from i group by all order by n desc""")

s("product type mentioned per category (exploded mentioned_products)", """
with m as (select reason_category, trim(pid) pid from (select reason_category, unnest(string_split(mentioned_products, ',')) pid from i where mentioned_products is not null and mentioned_products<>'')),
 g as (select reason_category, p.product_type, count(*) n from m left join p on m.pid=p.product_id group by 1,2)
select reason_category, product_type, n, round(100*n/sum(n) over(partition by reason_category),1) pct_in_cat from g order by reason_category, n desc""")

s("mentioned_products coverage", "select round(100*avg((mentioned_products is not null and mentioned_products<>'')::int),1) has_products_pct from i")

s("complaints case_type x category x subcategory", """
select case_type, category, subcategory, count(*) n, round(100*count(*)/sum(count(*)) over(),1) pct,
  round(100*avg((sla_breached='True')::int),1) sla_breach, round(median(try_cast(resolution_days as int)),0) med_days,
  round(100*avg((claimed_amount is not null and claimed_amount<>'')::int),1) has_amount_pct,
  round(100*avg((origin_interaction_id is not null and origin_interaction_id<>'')::int),1) from_call_pct
from q group by all order by n desc""")

s("complaints by affected product type", """
select product_type, n, round(100*n/sum(n) over(),1) pct from (select p.product_type, count(*) n from q left join p on q.affected_product_id=p.product_id group by 1) order by n desc""")

s("products dim mix", "select product_type, count(*) n, round(100*count(*)/sum(count(*)) over(),1) pct from p group by 1 order by n desc")

s("transactions sample: type x status (May 2026 only)", """
select transaction_type, transaction_status, count(*) n, round(100*count(*)/sum(count(*)) over(),2) pct from t group by all order by n desc""")
s("transactions sample: response_code", "select transaction_status, response_code, count(*) n from t group by all order by n desc limit 15")
