from django.urls import path

from .views import feed_view, health_view, media_view, run_cycle_view

urlpatterns = [
    path("health", health_view, name="health"),
    path("run", run_cycle_view, name="run_cycle"),
    path("feed", feed_view, name="feed"),
    path("media/<path:relative_path>", media_view, name="media"),
]
