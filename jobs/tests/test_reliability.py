"""M3 reliability tests: idempotent re-import (exactly-once effect).

Retries, dead-letter, and lease recovery land in later M3 PRs; this file grows
with them.
"""

import pytest

from jobs.models import Job, PropertyRecord
from jobs.tasks import process_job
from jobs.tests.factories import JobFactory

pytestmark = pytest.mark.django_db


def test_reprocessing_a_job_does_not_duplicate_rows():
    """A redelivered job re-imports onto the same rows, not duplicates.

    The PENDING-guard already no-ops a redelivered *terminal* job, so to exercise the
    data-level guard directly we force the job back to PENDING and run it again. The
    unique (job, external_id) constraint + bulk_create(ignore_conflicts=True) keep the
    row count stable — exactly-once effect even if the status guard is ever bypassed.
    """
    job = JobFactory()  # sample:properties.csv → 5 rows

    assert process_job(str(job.id)) == "succeeded"
    assert PropertyRecord.objects.filter(job=job).count() == 5

    Job.objects.filter(pk=job.id).update(status=Job.Status.PENDING)
    assert process_job(str(job.id)) == "succeeded"

    assert PropertyRecord.objects.filter(job=job).count() == 5  # no duplicates


def test_distinct_jobs_may_share_external_ids():
    """Uniqueness is scoped per-job, so two imports of the same source never collide."""
    job_a = JobFactory()
    job_b = JobFactory()

    assert process_job(str(job_a.id)) == "succeeded"
    assert process_job(str(job_b.id)) == "succeeded"

    assert PropertyRecord.objects.filter(job=job_a).count() == 5
    assert PropertyRecord.objects.filter(job=job_b).count() == 5
    assert PropertyRecord.objects.count() == 10  # same external_ids, different jobs
