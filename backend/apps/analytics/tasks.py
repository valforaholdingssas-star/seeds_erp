from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def sync_bigquery_analytics(self):
    """Nightly (or manual) full refresh of reporting tables → BigQuery."""
    from apps.analytics.services.bigquery_export import sync_analytics_to_bigquery

    try:
        return sync_analytics_to_bigquery()
    except Exception as exc:
        logger.exception("BigQuery sync failed")
        raise self.retry(exc=exc)
