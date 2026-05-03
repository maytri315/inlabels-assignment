from django.urls import path

from .views import (
    feed_view,
    health_view,
    media_view,
    run_cycle_view,
    text_fact_check_view,
    user_preferences_view,
    verdicts_view,
    categories_view,
)

urlpatterns = [
    path("health", health_view, name="health"),
    path("run", run_cycle_view, name="run_cycle"),
    path("text-check", text_fact_check_view, name="text_fact_check"),
    path("feed", feed_view, name="feed"),
    path("media/<path:relative_path>", media_view, name="media"),
    # Personalization endpoints
    path("preferences", user_preferences_view, name="user_preferences"),
    path("verdicts", verdicts_view, name="verdicts"),
    path("categories", categories_view, name="categories"),
]
