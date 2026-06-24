from django.contrib import admin
from django.urls import include, path

from jobs.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", HealthView.as_view(), name="healthz"),
    path("api/v1/", include("jobs.urls")),
]
