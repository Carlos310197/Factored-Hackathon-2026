locals {
  databases = toset(["LATAM_BANK", "LATAM_FIXTURE"])
  schemas   = toset(["RAW", "STAGING", "CURATED", "META"])
  db_schemas = {
    for pair in setproduct(local.databases, local.schemas) : "${pair[0]}.${pair[1]}" => { db = pair[0], schema = pair[1] }
  }
}

resource "snowflake_warehouse" "pipeline" {
  name                = "WH_PIPELINE"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = "true"
  initially_suspended = true
}

resource "snowflake_account_role" "pipeline" {
  name = "PIPELINE_ROLE"
}

resource "snowflake_grant_account_role" "pipeline_to_sysadmin" {
  role_name        = snowflake_account_role.pipeline.name
  parent_role_name = "SYSADMIN"
}

resource "snowflake_database" "db" {
  for_each = local.databases
  name     = each.key
}

resource "snowflake_schema" "s" {
  for_each = local.db_schemas
  database = snowflake_database.db[each.value.db].name
  name     = each.value.schema
}

resource "snowflake_file_format_csv" "csv_header" {
  for_each                       = local.databases
  database                       = snowflake_database.db[each.key].name
  schema                         = snowflake_schema.s["${each.key}.RAW"].name
  name                           = "CSV_HEADER"
  parse_header                   = "true"
  error_on_column_count_mismatch = "false"
  skip_byte_order_mark           = "true"
  field_optionally_enclosed_by   = "\""
  null_if                        = [""]
  empty_field_as_null            = "true"
}

resource "snowflake_storage_integration_aws" "serving" {
  name                      = "SI_SERVING"
  enabled                   = true
  storage_provider          = "S3"
  storage_allowed_locations = [local.serving_url]
  storage_aws_role_arn      = "arn:aws:iam::${local.account_id}:role/${local.snowflake_role_name}"
}

# Organizer's static read-only keys: from SSM, never from GitHub.
resource "snowflake_stage_external_s3" "organizer" {
  database = snowflake_database.db["LATAM_BANK"].name
  schema   = snowflake_schema.s["LATAM_BANK.RAW"].name
  name     = "ORGANIZER_STAGE"
  url      = "s3://${local.organizer_bucket}/data/"
  credentials {
    aws_key_id     = data.aws_ssm_parameter.organizer_key_id.value
    aws_secret_key = data.aws_ssm_parameter.organizer_secret.value
  }
}

resource "snowflake_stage_external_s3" "serving" {
  database            = snowflake_database.db["LATAM_BANK"].name
  schema              = snowflake_schema.s["LATAM_BANK.RAW"].name
  name                = "SERVING_STAGE"
  url                 = local.serving_url
  storage_integration = snowflake_storage_integration_aws.serving.name
  depends_on          = [aws_iam_role_policy.snowflake_serving]
}

resource "snowflake_stage_internal" "fixture" {
  for_each = toset(["FIXTURE_STAGE", "SERVING_STAGE"])
  database = snowflake_database.db["LATAM_FIXTURE"].name
  schema   = snowflake_schema.s["LATAM_FIXTURE.RAW"].name
  name     = each.key
}

# --- grants to PIPELINE_ROLE ---
resource "snowflake_grant_privileges_to_account_role" "warehouse" {
  account_role_name = snowflake_account_role.pipeline.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.pipeline.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database" {
  for_each          = local.databases
  account_role_name = snowflake_account_role.pipeline.name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.db[each.key].name
  }
}

resource "snowflake_grant_privileges_to_account_role" "schema" {
  for_each          = local.db_schemas
  account_role_name = snowflake_account_role.pipeline.name
  all_privileges    = true
  on_schema {
    schema_name = "${snowflake_schema.s[each.key].database}.${snowflake_schema.s[each.key].name}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "integration" {
  account_role_name = snowflake_account_role.pipeline.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "INTEGRATION"
    object_name = snowflake_storage_integration_aws.serving.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "stages_and_formats" {
  for_each          = { for k in setproduct(local.databases, ["STAGES", "FILE FORMATS"]) : "${k[0]}/${k[1]}" => { db = k[0], type = k[1] } }
  account_role_name = snowflake_account_role.pipeline.name
  all_privileges    = true
  on_schema_object {
    all {
      object_type_plural = each.value.type
      in_schema          = "${snowflake_schema.s["${each.value.db}.RAW"].database}.${snowflake_schema.s["${each.value.db}.RAW"].name}"
    }
  }
  depends_on = [snowflake_stage_external_s3.organizer, snowflake_stage_external_s3.serving, snowflake_stage_internal.fixture, snowflake_file_format_csv.csv_header]
}

# --- pipeline service user: same AWS role, workload identity, no secret ---
resource "snowflake_execute" "pipeline_user" {
  execute = "CREATE USER PIPELINE_SVC TYPE = SERVICE WORKLOAD_IDENTITY = (TYPE = AWS ARN = '${local.gha_deploy_arn}') DEFAULT_ROLE = PIPELINE_ROLE DEFAULT_WAREHOUSE = WH_PIPELINE"
  revert  = "DROP USER PIPELINE_SVC"
}

resource "snowflake_grant_account_role" "pipeline_to_svc" {
  role_name  = snowflake_account_role.pipeline.name
  user_name  = "PIPELINE_SVC"
  depends_on = [snowflake_execute.pipeline_user]
}
