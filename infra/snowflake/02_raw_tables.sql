-- uv run python -m pipeline.setup 02_raw_tables.sql ; SETUP_DATABASE=LATAM_FIXTURE uv run python -m pipeline.setup 02_raw_tables.sql
use role PIPELINE_ROLE;
use database ${DATABASE};
create table if not exists RAW.CUSTOMERS (
  customer_id varchar, document_number varchar, document_type varchar, first_name varchar, last_name varchar,
  date_of_birth varchar, gender varchar, email varchar, mobile_phone varchar, landline_phone varchar, address varchar,
  city varchar, state varchar, country varchar, postal_code varchar, detected_accent varchar, segment varchar,
  credit_score varchar, estimated_monthly_income varchar, occupation varchar, marital_status varchar,
  education_level varchar, registration_date varchar, registration_branch_id varchar, customer_status varchar,
  last_updated varchar, accepts_marketing varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.PRODUCTS (
  product_id varchar, customer_id varchar, product_type varchar, product_number varchar, currency varchar,
  current_balance varchar, credit_limit varchar, interest_rate varchar, opening_date varchar, expiration_date varchar,
  opening_branch_id varchar, product_status varchar, opening_channel varchar, has_linked_app varchar,
  days_past_due varchar, last_transaction_date varchar, last_updated varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.TRANSACTIONS (
  transaction_id varchar, transaction_date varchar, process_date varchar, product_id varchar, customer_id varchar,
  transaction_type varchar, transaction_category varchar, amount varchar, currency varchar, amount_usd varchar,
  channel varchar, branch_id varchar, merchant_name varchar, merchant_category varchar, transaction_country varchar,
  transaction_city varchar, transaction_status varchar, response_code varchar, is_fraud varchar, fraud_score varchar,
  latitude varchar, longitude varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.COMPLAINTS (
  complaint_id varchar, creation_date varchar, process_date varchar, customer_id varchar, case_type varchar,
  category varchar, subcategory varchar, reception_channel varchar, affected_product_id varchar,
  related_branch_id varchar, origin_interaction_id varchar, description varchar, claimed_amount varchar,
  currency varchar, priority varchar, status varchar, assigned_agent_id varchar, assignment_date varchar,
  first_response_date varchar, resolution_date varchar, closing_date varchar, sla_breached varchar,
  resolution_days varchar, resolution varchar, compensation_granted varchar, resolution_satisfaction varchar,
  is_repeat_complainer varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists RAW.INTERACTIONS (
  interaction_id varchar, interaction_date varchar, process_date varchar, customer_id varchar, agent_id varchar,
  interaction_type varchar, channel varchar, contact_reason varchar, reason_category varchar,
  duration_seconds varchar, wait_time_seconds varchar, was_resolved varchar, requires_followup varchar,
  detected_sentiment varchar, sentiment_score varchar, customer_detected_accent varchar, agent_used_accent varchar,
  was_escalated varchar, mentioned_products varchar, has_transcript varchar, has_recording varchar,
  _source_file varchar, _file_row number, _file_last_modified timestamp_ntz, _loaded_at timestamp_ntz
) enable_schema_evolution = true;
create table if not exists META.RUN_MANIFEST (
  run_id varchar, table_name varchar, file_path varchar, etag varchar, mode varchar, rows_loaded number,
  loaded_at timestamp_ntz default current_timestamp()
);
create table if not exists META.DQ_RESULTS (
  run_id varchar, test_name varchar, model varchar, severity varchar, status varchar, failures number,
  ran_at timestamp_ntz
);
