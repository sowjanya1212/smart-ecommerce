from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/export/<str:report>.<str:fmt>", views.export_report, name="export_report"),
]
