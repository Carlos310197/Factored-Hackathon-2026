variable "appsync_log_level" {
  type        = string
  default     = "ERROR"
  description = "Event API log level. ALL is only for the unit-53 identity probe; revert afterwards (payloads may hold message text)."

  validation {
    condition     = contains(["NONE", "ERROR", "INFO", "DEBUG", "ALL"], var.appsync_log_level)
    error_message = "appsync_log_level must be NONE, ERROR, INFO, DEBUG or ALL."
  }
}
