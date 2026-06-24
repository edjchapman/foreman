import uuid

from django.db import models


class Job(models.Model):
    """A unit of asynchronous work.

    M1 only ever creates jobs in PENDING (there is no worker yet). The non-PENDING
    states and the `idempotency_key` / `attempts` fields are present from the start so
    the M2 outbox/worker and M3 reliability work don't churn the schema.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        DEAD_LETTER = "DEAD_LETTER", "Dead-letter"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_type = models.CharField(max_length=64, default="property_csv_import")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payload = models.JSONField(default=dict)
    # Unique-or-absent: a NULL means "no key supplied"; an empty string would collide
    # on the unique constraint, so null=True is the correct pattern here.
    idempotency_key = models.CharField(  # noqa: DJ001
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )
    progress = models.PositiveSmallIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Job {self.id} [{self.status}]"
