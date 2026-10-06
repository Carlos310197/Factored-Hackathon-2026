# Operations dashboard: turn latency from the agent's `turn_end <ms>` line, every alarm metric, alarm states, and the
# web load balancer. One page answers "is it up, is it fast, is it failing, is anyone abusing it".

resource "aws_cloudwatch_log_metric_filter" "turn_duration" {
  name           = "lb-demo-agent-TurnDurationMs"
  log_group_name = aws_cloudwatch_log_group.runtime.name
  pattern        = "[event=\"turn_end\", duration_ms]"

  metric_transformation {
    name      = "TurnDurationMs"
    namespace = "LBDemo/Agent"
    value     = "$duration_ms"
    unit      = "Milliseconds" # no default value: zeros would drag the percentiles down
  }
}

data "aws_lb" "web" {
  name = "latam-bank-web"
}

locals {
  ns = "LBDemo/Agent"
  latency = [for stat in ["p50", "p95", "Maximum"] :
  [local.ns, "TurnDurationMs", { stat = stat, label = "turn ${stat}" }]]
}

resource "aws_cloudwatch_dashboard" "ops" {
  dashboard_name = "lb-demo-ops"
  dashboard_body = jsonencode({
    widgets = [
      { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = {
        title   = "Turn latency (ms): agent time per turn", region = "us-east-1", view = "timeSeries", period = 300,
        metrics = local.latency,
        annotations = { horizontal = [
        { value = 15000, label = "turn budget 15 s" }, { value = 25000, label = "web gives up 25 s", color = "#d62728" }] }
      } },
      { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = {
        title   = "Turns per 5 min", region = "us-east-1", view = "timeSeries", period = 300, stat = "SampleCount",
        metrics = [[local.ns, "TurnDurationMs", { label = "turns" }]]
      } },
      { type = "metric", x = 0, y = 6, width = 12, height = 6, properties = {
        title   = "Failures (count per 5 min)", region = "us-east-1", view = "timeSeries", period = 300, stat = "Sum",
        metrics = [for m in ["TurnFailed", "TemplateFallback", "AuditWriteFailed", "TurnSlow"] : [local.ns, m]]
      } },
      { type = "metric", x = 12, y = 6, width = 12, height = 6, properties = {
        title = "Abuse and data freshness (count per hour)", region = "us-east-1", view = "timeSeries", period = 3600,
        stat  = "Sum", metrics = [for m in ["TurnCapReached", "StalePointer"] : [local.ns, m]]
      } },
      { type = "alarm", x = 0, y = 12, width = 12, height = 4, properties = {
        title = "Alarms", alarms = [for a in aws_cloudwatch_metric_alarm.agent : a.arn]
      } },
      { type = "metric", x = 12, y = 12, width = 12, height = 4, properties = {
        title = "Web (load balancer)", region = "us-east-1", view = "timeSeries", period = 300,
        metrics = [
          ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", data.aws_lb.web.arn_suffix, { stat = "Sum", label = "app 5xx" }],
          ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", data.aws_lb.web.arn_suffix, { stat = "Sum", label = "LB 5xx" }],
          ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", data.aws_lb.web.arn_suffix, { stat = "p95", label = "response p95 (s)", yAxis = "right" }],
        ]
      } },
    ]
  })
}

output "dashboard_url" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards/dashboard/${aws_cloudwatch_dashboard.ops.dashboard_name}"
}
