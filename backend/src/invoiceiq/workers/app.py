"""Celery application. Broker/backend = Redis (docs/02 D2).
RabbitMQ is a config swap via IIQ_REDIS_URL pointing at amqp://.
"""

from celery import Celery

from ..settings import get_settings

settings = get_settings()

celery_app = Celery(
    "invoiceiq",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["invoiceiq.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
