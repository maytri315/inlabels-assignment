from django.db import models


class UserPreferences(models.Model):
    """Store user preferences for news categories and filtering."""
    
    CATEGORY_CHOICES = [
        ("general", "General"),
        ("entertainment", "Entertainment"),
        ("tech", "Technology"),
        ("political", "Political"),
        ("sports", "Sports"),
        ("business", "Business"),
        ("science", "Science"),
    ]
    
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    preferred_categories = models.JSONField(
        default=list,
        help_text="List of preferred news categories"
    )
    filter_by_confidence = models.CharField(
        max_length=20,
        choices=[
            ("all", "Show All"),
            ("high", "High Confidence Only"),
            ("medium_high", "Medium & High Confidence"),
        ],
        default="all"
    )
    show_red_flags = models.BooleanField(
        default=True,
        help_text="Show warnings for red flags (FIR, criminal records, etc.)"
    )
    min_confidence_score = models.FloatField(
        default=0.0,
        help_text="Minimum confidence score (0.0-1.0) to display news"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "user_preferences"
    
    def __str__(self):
        return f"Preferences for {self.session_id}"


class NewsVerdict(models.Model):
    """Store verdict history for news stories."""
    
    VERDICT_CHOICES = [
        ("verified", "Verified"),
        ("uncertain", "Uncertain"),
        ("likely_fake", "Likely Fake"),
    ]
    
    headline = models.TextField()
    summary = models.TextField()
    category = models.CharField(max_length=50, default="general")
    source = models.CharField(max_length=255)
    source_link = models.URLField()
    verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES)
    confidence_score = models.FloatField()  # 0.0-1.0
    confidence_level = models.CharField(
        max_length=20,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium"
    )
    red_flags = models.JSONField(default=list, help_text="List of detected red flags")
    key_claim = models.TextField()
    reason = models.TextField()
    evidence_count = models.IntegerField(default=0)
    evidence = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "news_verdicts"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.headline} - {self.verdict}"
