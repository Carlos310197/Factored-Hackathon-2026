mock_provider "aws" {
  mock_data "aws_s3_bucket" {
    defaults = {
      id     = "latam-bank-serving-762197749808-use1"
      arn    = "arn:aws:s3:::latam-bank-serving-762197749808-use1"
      bucket = "latam-bank-serving-762197749808-use1"
    }
  }
}

# plan only: prevent_destroy would fail the teardown of an applied test

run "six_tables_on_demand_with_pitr_and_deletion_protection" {
  command = plan

  assert {
    condition     = toset(keys(aws_dynamodb_table.this)) == toset(["checkpoints", "disputes", "handoffs", "decision_records", "sessions", "conversation_messages"])
    error_message = "six tables keyed by their spec name"
  }
  assert {
    condition     = alltrue([for k, t in aws_dynamodb_table.this : t.name == "lb-demo-${k}" && t.billing_mode == "PAY_PER_REQUEST" && t.deletion_protection_enabled && t.point_in_time_recovery[0].enabled])
    error_message = "lb-demo-* names, on-demand, deletion protection and PITR on every table"
  }
}

run "ttl_and_streams_match_the_specs" {
  command = plan

  assert {
    condition     = alltrue([for k in ["checkpoints", "decision_records", "conversation_messages"] : aws_dynamodb_table.this[k].ttl[0].enabled && aws_dynamodb_table.this[k].ttl[0].attribute_name == "ttl"])
    error_message = "ttl attribute on checkpoints, decision_records, conversation_messages"
  }
  assert {
    condition     = alltrue([for k in ["disputes", "handoffs", "sessions"] : length(aws_dynamodb_table.this[k].ttl) == 0 || !aws_dynamodb_table.this[k].ttl[0].enabled])
    error_message = "no TTL on the other tables (unit 78 adds sessions later)"
  }
  assert {
    condition     = toset(keys(output.stream_arns)) == toset(["handoffs", "decision_records", "conversation_messages"])
    error_message = "stream_arns has exactly the three stream tables"
  }
  assert {
    condition     = alltrue([for k in ["handoffs", "decision_records", "conversation_messages"] : aws_dynamodb_table.this[k].stream_enabled && aws_dynamodb_table.this[k].stream_view_type == "NEW_IMAGE"])
    error_message = "NEW_IMAGE streams on the three stream tables"
  }
  assert {
    condition     = alltrue([for k in ["checkpoints", "disputes", "sessions"] : !aws_dynamodb_table.this[k].stream_enabled])
    error_message = "no streams elsewhere"
  }
}

run "keys_and_indexes_match_tables_json" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.this["checkpoints"].hash_key == "PK" && aws_dynamodb_table.this["checkpoints"].range_key == "SK"
    error_message = "checkpoints PK/SK"
  }
  assert {
    condition     = aws_dynamodb_table.this["disputes"].hash_key == "transaction_id" && one([for g in aws_dynamodb_table.this["disputes"].global_secondary_index : g.name]) == "by_customer"
    error_message = "disputes keyed by transaction_id with by_customer"
  }
  assert {
    condition     = one([for g in aws_dynamodb_table.this["handoffs"].global_secondary_index : g.range_key]) == "created_at"
    error_message = "handoffs by_status sorts on created_at"
  }
  assert {
    condition     = aws_dynamodb_table.this["conversation_messages"].hash_key == "session_id" && aws_dynamodb_table.this["conversation_messages"].range_key == "sk"
    error_message = "conversation_messages session_id/sk"
  }
}

run "serving_bucket_is_read_not_managed" {
  command = plan

  assert {
    condition     = output.serving_bucket == "latam-bank-serving-762197749808-use1"
    error_message = "serving bucket referenced by name"
  }
  assert {
    condition     = output.serving_bucket_arn == "arn:aws:s3:::latam-bank-serving-762197749808-use1"
    error_message = "arn comes from the data source (no bucket resource or policy in this root)"
  }
}

run "image_repositories_are_immutable_and_scanned" {
  command = plan

  assert {
    condition     = alltrue([for r in [aws_ecr_repository.agent, aws_ecr_repository.identity] : r.image_tag_mutability == "IMMUTABLE" && r.image_scanning_configuration[0].scan_on_push])
    error_message = "immutable tags and scan on push"
  }
  assert {
    condition     = aws_ecr_repository.agent.name == "lb-demo-agent" && aws_ecr_repository.identity.name == "lb-demo-identity"
    error_message = "repository names"
  }
  assert {
    condition     = alltrue([for l in [aws_ecr_lifecycle_policy.agent, aws_ecr_lifecycle_policy.identity] : jsondecode(l.policy).rules[0].selection.countNumber == 10])
    error_message = "keep the last 10 images"
  }
}

run "image_parameters_ignore_value_changes" {
  command = plan

  assert {
    condition     = aws_ssm_parameter.agent_image.name == "/fh26/agent/image" && aws_ssm_parameter.identity_image.name == "/fh26/identity/image"
    error_message = "parameter names"
  }
  assert {
    condition     = aws_ssm_parameter.agent_image.type == "String" && aws_ssm_parameter.identity_image.type == "String"
    error_message = "String parameters"
  }
}
