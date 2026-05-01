from django.urls import include, path
from api.views import frontend_view

urlpatterns = [
    path("", frontend_view, name="frontend"),
    path("api/", include("api.urls")),
]
