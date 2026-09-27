import duckdb
c=duckdb.connect()
c.sql("create view i as select * from read_csv('data/raw/call_center_interactions/**/*.csv', hive_partitioning=true, union_by_name=true, all_varchar=true)")
c.sql("create view q as select * from read_csv('data/raw/complaints/**/*.csv', hive_partitioning=true, union_by_name=true, all_varchar=true)")
def s(x): print(c.sql(x).fetchdf().to_string(index=False) if False else c.sql(x)); 
print(c.sql("describe i").fetchall().__len__(), "cols interactions")
s("""select count(*) n, count(distinct "interaction_id") uniq_ids, count(*)-count(distinct "interaction_id") dup_ids,
  min(interaction_date), max(interaction_date) from i""")
s("""select contact_reason, count(*) n, round(100*count(*)/sum(count(*)) over(),1) pct,
  round(100*avg((was_resolved='True')::int),1) fcr_pct, round(100*avg((was_escalated='True')::int),1) esc_pct,
  round(100*avg((requires_followup='True')::int),1) followup_pct,
  round(median(try_cast(duration_seconds as int))/60,1) med_min, round(median(try_cast(wait_time_seconds as int))/60,1) med_wait_min,
  round(100*avg((detected_sentiment in ('Negative','Very Negative'))::int),1) neg_pct
  from i group by 1 order by n desc""")
s("select channel, count(*) n from i group by 1 order by n desc")
s("select customer_detected_accent, count(*) n from i group by 1 order by n desc")
s("select year, count(*) n from i group by 1 order by 1")
s("select count(*) filter (where was_resolved is null or was_resolved='') null_resolved, count(*) filter (where agent_id is null or agent_id='') null_agent, count(*) filter (where duration_seconds is null or duration_seconds='') null_dur from i")
print("describe i columns:"); print([r[0] for r in c.sql("describe i").fetchall()])
s("""select count(*) n, count(*)-count(distinct "complaint_id") dup_ids from q""")
s("""select category, subcategory, count(*) n, round(100*count(*)/sum(count(*)) over(),1) pct,
  round(100*avg((sla_breached='True')::int),1) sla_breach_pct, round(median(try_cast(resolution_days as int)),1) med_days,
  round(avg(try_cast(resolution_satisfaction as int)),2) sat, round(100*avg((status='Escalated')::int),1) esc_pct
  from q group by all order by n desc limit 25""")
s("select priority, count(*) from q group by 1 order by 2 desc")
s("select description, count(*) n from q group by 1 order by n desc limit 8")
s("select resolution, count(*) n from q group by 1 order by n desc limit 6")
