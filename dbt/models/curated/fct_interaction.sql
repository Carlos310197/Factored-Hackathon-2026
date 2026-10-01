select interaction_id, interaction_ts, process_date, customer_id, channel, interaction_type, reason_category, duration_seconds,
       wait_time_seconds, was_resolved, requires_followup, was_escalated, detected_sentiment, sentiment_score,
       customer_detected_accent, has_transcript
from {{ ref('stg_interactions') }}
