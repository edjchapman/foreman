from django.db import connection
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from .models import Job
from .serializers import JobCreateSerializer, JobSerializer


class JobViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Submit (POST), retrieve, and list jobs.

    Submitting only records the job as PENDING — M1 has no worker yet (that's M2).
    An optional `Idempotency-Key` header makes resubmission safe at the API edge;
    worker-side exactly-once processing lands in M3.
    """

    queryset = Job.objects.all()

    def get_serializer_class(self):
        return JobCreateSerializer if self.action == "create" else JobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            existing = Job.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                data = JobSerializer(existing, context=self.get_serializer_context()).data
                return Response(data, status=status.HTTP_200_OK)

        job = Job.objects.create(
            idempotency_key=idempotency_key,
            **serializer.validated_data,
        )
        data = JobSerializer(job, context=self.get_serializer_context()).data
        location = reverse("job-detail", args=[job.id], request=request)
        return Response(data, status=status.HTTP_202_ACCEPTED, headers={"Location": location})


class HealthView(APIView):
    """Liveness probe that also confirms the database is reachable."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return Response({"status": "unhealthy"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "ok"})
