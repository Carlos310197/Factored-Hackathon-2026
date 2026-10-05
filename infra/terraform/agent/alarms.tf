# Alarms on the agent's own log lines (runtime log group). A spike in template fallbacks is what a stale Bedrock token
# or a Jev outage looks like from the customer's side; turn failures are uncaught errors; an audit write failure means
# a decision record is missing from the trace.

variable "alarm_email" {
  description = "Optional address subscribed to the alarm topic (confirm the SNS email). Empty: alarms show in the console only."
  type        = string
  default     = ""
}

locals {
  alarms = {
    TurnFailed       = { pattern = "\"turn failed\"", threshold = 3, period = 300, what = "uncaught errors in a turn" }
    TemplateFallback = { pattern = "\"reply fell back to template\"", threshold = 5, period = 900, what = "replies that fell back to the fixed template (LLM or Jev failing)" }
    AuditWriteFailed = { pattern = "\"decision record write failed\"", threshold = 1, period = 300, what = "decision records that could not be written" }
    TurnSlow         = { pattern = "\"slow turn\"", threshold = 3, period = 900, what = "turns over 20 s (the web app gives up at 25 s)" }
    StalePointer     = { pattern = "\"serving pointer is stale\"", threshold = 1, period = 3600, what = "reads of a serving export older than 2 days (daily pipeline stopped)" }
    TurnCapReached   = { pattern = "\"session turn cap reached\"", threshold = 20, period = 3600, what = "turns refused by the per-session cap (possible abuse of the public demo identities)" }
  }
}

resource "aws_cloudwatch_log_metric_filter" "agent" {
  for_each       = local.alarms
  name           = "lb-demo-agent-${each.key}"
  log_group_name = aws_cloudwatch_log_group.runtime.name
  pattern        = each.value.pattern

  metric_transformation {
    name          = each.key
    namespace     = "LBDemo/Agent"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_sns_topic" "alarms" {
  count = var.alarm_email == "" ? 0 : 1
  name  = "lb-demo-agent-alarms"
}

resource "aws_sns_topic_subscription" "alarms" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "agent" {
  for_each            = local.alarms
  alarm_name          = "lb-demo-agent-${each.key}"
  alarm_description   = "${each.value.threshold} or more ${each.value.what} in ${each.value.period / 60} minutes"
  namespace           = "LBDemo/Agent"
  metric_name         = each.key
  statistic           = "Sum"
  period              = each.value.period
  evaluation_periods  = 1
  threshold           = each.value.threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = aws_sns_topic.alarms[*].arn
  ok_actions          = aws_sns_topic.alarms[*].arn

  depends_on = [aws_cloudwatch_log_metric_filter.agent]
}

variable "monthly_budget_usd" {
  description = "AWS Budget for this account; emails alarm_email at 80 % actual and 100 % forecast spend."
  type        = number
  default     = 100
}

# Spend guard for the public demo (Bedrock inference itself bills to the account that owns the Bedrock role).
resource "aws_budgets_budget" "account" {
  count        = var.alarm_email == "" ? 0 : 1
  name         = "lb-demo-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alarm_email]
  }
}
