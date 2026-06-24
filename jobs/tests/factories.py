import factory

from jobs.models import Job


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job

    job_type = "property_csv_import"
    payload = factory.LazyFunction(lambda: {"source": "s3://bucket/sample.csv"})
