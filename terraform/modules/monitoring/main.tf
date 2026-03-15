resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email != "" ? 1 : 0
  project      = var.project_id
  display_name = "tty-theme alerts"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

locals {
  channel_ids = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

resource "google_monitoring_alert_policy" "latency" {
  project      = var.project_id
  display_name = "${var.service_name} p99 latency > 5s"
  combiner     = "OR"
  notification_channels = local.channel_ids

  conditions {
    display_name = "p99 latency"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["resource.label.service_name"]
      }
    }
  }
}

resource "google_monitoring_alert_policy" "error_rate" {
  project      = var.project_id
  display_name = "${var.service_name} error rate > 5%"
  combiner     = "OR"
  notification_channels = local.channel_ids

  conditions {
    display_name = "error rate"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.service_name"]
      }
    }
  }
}
