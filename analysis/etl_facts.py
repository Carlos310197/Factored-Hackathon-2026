# Facts the ETL design depends on: file layout, late arrivals (data vs backup), schema evolution, duplicates, type parse rates.
import duckdb, re
env = dict(l.strip().split("=", 1) for l in open(".env") if "=" in l and not l.startswith("#"))
B = env["DATA_BUCKET"]
c = duckdb.connect()
c.sql(f"create secret (type s3, key_id '{env['AWS_ACCESS_KEY_ID']}', secret '{env['AWS_SECRET_ACCESS_KEY']}', region '{env['AWS_DEFAULT_REGION']}')")
def s(title, sql): print(f"\n=== {title} ==="); print(c.sql(sql).fetchdf().to_string(index=False))

c.sql(f"create table files as select file from glob('s3://{B}/**')")
c.sql("""create table f as select file,
  regexp_extract(file, 's3://[^/]+/([^/]+)/', 1) root,
  regexp_extract(file, 's3://[^/]+/[^/]+/([^/]+?)(?:\\.csv|/)', 1) tbl,
  regexp_extract(file, 'year=(\\d+)/month=(\\d+)/day=(\\d+)', ['y','m','d']) part from files""")
s("files per root/table + partition span", """
select root, tbl, count(*) n_files, min(part.y||'-'||part.m||'-'||part.d) first_part, max(part.y||'-'||part.m||'-'||part.d) last_part
from f group by all order by 1,2""")
s("partitions only in data/ vs only in backup/ (transactions + interactions)", """
with a as (select tbl, part.y||'-'||part.m||'-'||part.d p from f where root='data' and part.y<>''),
     b as (select tbl, part.y||'-'||part.m||'-'||part.d p from f where root like 'data_backup%' and part.y<>'')
select tbl, count(*) filter (where b.p is null) only_in_data, count(*) filter (where a.p is null) only_in_backup, count(*) filter (where a.p is not null and b.p is not null) in_both,
  min(a.p) filter (where b.p is null) first_only_data, max(b.p) filter (where a.p is null) last_only_backup
from a full join b using(tbl,p) group by 1 order by 1""")
s("files per partition (multiple files per day = late arrivals?)", """
select tbl, root, count(*) n_files, count(distinct part.y||part.m||part.d) n_parts, round(count(*)*1.0/count(distinct part.y||part.m||part.d),2) files_per_part from f where part.y<>'' group by all order by 1,2""")
s("example filenames in one partition", "select file from f where tbl='transactions' and root='data' order by file limit 4")

# schema evolution: columns of earliest vs latest file per fact table, plus backup's latest
def cols(path): return [r[0] for r in c.sql(f"describe select * from read_csv('{path}', all_varchar=true)").fetchall()]
tbls = [r[0] for r in c.sql("select distinct tbl from f where part.y<>''").fetchall()]
print("\n=== schema evolution (earliest vs latest file) ===")
for t in tbls:
    first, last = c.sql(f"select min(file), max(file) from f where tbl='{t}' and root='data'").fetchone()
    a, b = cols(first), cols(last)
    bk = c.sql(f"select max(file) from f where tbl='{t}' and root like 'data_backup%'").fetchone()[0]
    bc = cols(bk) if bk else None
    print(f"{t}: {len(a)} cols first, {len(b)} cols last; added={sorted(set(b)-set(a))} removed={sorted(set(a)-set(b))}" + (f"; backup_last diff vs data_last: +{sorted(set(bc)-set(b))} -{sorted(set(b)-set(bc))}" if bc else "; no backup"))
print("dims:", [(t, len(cols(f"s3://{B}/data/{t}.csv"))) for t in ['customers','products','branches','service_agents','marketing_campaigns','daily_exchange_rates']])

# duplicates + types on local parquet
for n,fp in [("i","data/interactions.parquet"),("q","data/complaints.parquet"),("p","data/products.parquet"),("x","data/transactions_2026_05_sample.parquet")]: c.sql(f"create view {n} as select * from '{fp}'")
s("duplicates: exact-row (excluding partition cols) and same-content-different-id", """
select 'interactions' t, count(*) n,
 count(*) - (select count(*) from (select distinct * exclude(year,month,day) from i)) exact_dups,
 count(*) - (select count(*) from (select distinct * exclude(interaction_id,year,month,day) from i)) dups_ignoring_id,
 count(*) - count(distinct interaction_id) dup_ids from i
union all select 'complaints', count(*), count(*) - (select count(*) from (select distinct * exclude(year,month,day) from q)),
 count(*) - (select count(*) from (select distinct * exclude(complaint_id,year,month,day) from q)), count(*) - count(distinct complaint_id) from q
union all select 'products', count(*), count(*) - (select count(*) from (select distinct * from p)),
 count(*) - (select count(*) from (select distinct * exclude(product_id) from p)), count(*) - count(distinct product_id) from p
union all select 'transactions(May26)', count(*), count(*) - (select count(*) from (select distinct * exclude(year,month,day) from x)),
 count(*) - (select count(*) from (select distinct * exclude(transaction_id,year,month,day) from x)), count(*) - count(distinct transaction_id) from x""")
s("interactions: same customer+timestamp+reason with different ids (near-dups)", """
select count(*) - count(distinct (customer_id, interaction_date, reason_category, channel)) near_dups from i""")
s("type parse failures (non-null values that fail cast)", """
select 'i.interaction_date' col, count(*) filter (where interaction_date<>'' and try_cast(interaction_date as timestamp) is null) bad, count(*) filter (where interaction_date='' or interaction_date is null) n_null from i
union all select 'i.duration_seconds', count(*) filter (where duration_seconds<>'' and try_cast(duration_seconds as int) is null), count(*) filter (where duration_seconds='' or duration_seconds is null) from i
union all select 'i.was_resolved', count(*) filter (where was_resolved not in ('True','False','')), count(*) filter (where was_resolved='' or was_resolved is null) from i
union all select 'x.amount', count(*) filter (where amount<>'' and try_cast(amount as double) is null), count(*) filter (where amount='' or amount is null) from x
union all select 'x.transaction_date', count(*) filter (where transaction_date<>'' and try_cast(transaction_date as timestamp) is null), count(*) filter (where transaction_date='' or transaction_date is null) from x
union all select 'x.customer_id→customers?', 0, 0
union all select 'q.claimed_amount', count(*) filter (where claimed_amount<>'' and try_cast(claimed_amount as double) is null), count(*) filter (where claimed_amount='' or claimed_amount is null) from q
union all select 'q.creation_date', count(*) filter (where creation_date<>'' and try_cast(creation_date as timestamp) is null), count(*) filter (where creation_date='' or creation_date is null) from q""")
s("partition key vs event date (late arrival inside data/): process_date != partition", """
select round(100*avg((process_date <> year||'-'||month||'-'||day)::int),2) pct_partition_mismatch, round(100*avg((cast(try_cast(interaction_date as timestamp) as date) <> try_cast(process_date as date))::int),2) pct_event_vs_process_diff from i""")
s("transactions sample: process_date vs transaction_date lag", """
select date_diff('day', cast(try_cast(transaction_date as timestamp) as date), try_cast(process_date as date)) lag_days, count(*) n from x group by 1 order by 1 limit 8""")
s("customers/products snapshot fields", "select column_name from (describe select * from read_csv('s3://%s/data/customers.csv', all_varchar=true))" % B)

# --- where do the documented 2% duplicates / late arrivals live? ---
s("schema evolution via union_by_name: column counts in local caches", """
select 'interactions' t, (select count(*) from (describe select * from i)) n_cols union all select 'complaints', (select count(*) from (describe select * from q))""")
print("\n=== transactions/digital_events header check on one file per quarter ===")
for t in ['transactions','digital_events']:
    rows = c.sql(f"select file from f where tbl='{t}' and root='data' and part.d='01' and part.m in ('01','04','07','10') order by file").fetchall()
    base = None
    for (fp,) in rows:
        cc = cols(fp)
        if base is None: base = cc; print(t, "baseline", len(cc), "cols")
        elif cc != base: print("  DIFF at", fp.split('/')[-1], "+", sorted(set(cc)-set(base)), "-", sorted(set(base)-set(cc)))
    print(t, "checked", len(rows), "files")
s("same transactions partition in data/ vs backup/: row and id overlap (3 partitions)", f"""
with d as (select * exclude(filename), regexp_extract(filename,'(\\d{{8}})',1) part from read_csv('s3://{B}/data/transactions/year=2024/month=0[3-5]/day=15/*.csv', all_varchar=true, filename=true)),
     b as (select * exclude(filename), regexp_extract(filename,'(\\d{{8}})',1) part from read_csv('s3://{B}/data_backup_20260831/transactions/year=2024/month=0[3-5]/day=15/*.csv', all_varchar=true, filename=true))
select part, (select count(*) from d d2 where d2.part=x.part) rows_data, (select count(*) from b b2 where b2.part=x.part) rows_backup,
  (select count(*) from (select * from d d2 where d2.part=x.part except select * from b b2 where b2.part=x.part)) rows_only_data,
  (select count(*) from (select * from b b2 where b2.part=x.part except select * from d d2 where d2.part=x.part)) rows_only_backup
from (select distinct part from d) x order by 1""")
s("digital_events one week: duplicates", f"""
with e as (select * from read_csv('s3://{B}/data/digital_events/year=2026/month=05/day=0[1-7]/*.csv', all_varchar=true, union_by_name=true))
select count(*) n, count(*)-count(distinct event_id) dup_ids, count(*)-(select count(*) from (select distinct * from e)) exact_dups from e""")
s("campaign_sends one week: duplicates", f"""
with e as (select * from read_csv('s3://{B}/data/campaign_sends/year=2026/month=05/day=0[1-7]/*.csv', all_varchar=true, union_by_name=true))
select count(*) n, count(*)-count(distinct send_id) dup_ids, count(*)-(select count(*) from (select distinct * from e)) exact_dups from e""")
s("satisfaction_surveys one week: duplicates", f"""
with e as (select * from read_csv('s3://{B}/data/satisfaction_surveys/year=2026/month=05/day=0[1-7]/*.csv', all_varchar=true, union_by_name=true))
select count(*) n, count(*)-count(distinct survey_id) dup_ids, count(*)-(select count(*) from (select distinct * from e)) exact_dups from e""")
s("customers: dup ids + snapshot columns", f"""
select count(*) n, count(*)-count(distinct customer_id) dup_ids from read_csv('s3://{B}/data/customers.csv', all_varchar=true)""")
s("referential integrity: interactions/complaints/txn → customers & products", f"""
with cu as (select distinct customer_id from read_csv('s3://{B}/data/customers.csv', all_varchar=true))
select 'interactions.customer_id' fk, round(100*avg((cu.customer_id is null)::int),2) orphan_pct from i left join cu using(customer_id)
union all select 'complaints.customer_id', round(100*avg((cu.customer_id is null)::int),2) from q left join cu using(customer_id)
union all select 'transactions.customer_id(May26)', round(100*avg((cu.customer_id is null)::int),2) from x left join cu using(customer_id)
union all select 'transactions.product_id(May26)', round(100*avg((p.product_id is null)::int),2) from x left join p using(product_id)
union all select 'products.customer_id', round(100*avg((cu.customer_id is null)::int),2) from p left join cu using(customer_id)""")
s("transactions(May26): product belongs to same customer?", "select round(100*avg((p.customer_id=x.customer_id)::int),2) product_owner_matches from x join p using(product_id)")
