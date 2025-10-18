from django.db import models

class Listing(models.Model):
    source_url     = models.URLField(unique=True)
    title          = models.CharField(max_length=255, blank=True)
    price          = models.CharField(max_length=64, blank=True)
    currency       = models.CharField(max_length=16, blank=True)
    address        = models.CharField(max_length=512, blank=True)
    latitude       = models.FloatField(null=True, blank=True)
    longitude      = models.FloatField(null=True, blank=True)
    rooms          = models.CharField(max_length=32, blank=True)
    total_area_m2  = models.FloatField(null=True, blank=True)
    living_area_m2 = models.FloatField(null=True, blank=True)
    kitchen_area_m2= models.FloatField(null=True, blank=True)
    floor          = models.CharField(max_length=16, blank=True)
    floors_total   = models.CharField(max_length=16, blank=True)
    year_built     = models.CharField(max_length=16, blank=True)
    description    = models.TextField(blank=True)
    images         = models.JSONField(default=list, blank=True)   # список URLов
    raw            = models.JSONField(default=dict, blank=True)   # полный «сырой» dict на всякий

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title or 'Объявление'} — {self.source_url[:48]}"

    class Meta:
        ordering = ['-created_at']
