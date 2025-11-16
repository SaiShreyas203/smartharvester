from django.db import models

class Planting(models.Model):
    crop_name = models.CharField(max_length=100)
    planting_date = models.DateField()
    batch_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to="planting_images/", blank=True, null=True)
    plan = models.JSONField(blank=True, null=True)  # Optionally auto-set on save

    def __str__(self):
        return f"{self.crop_name} ({self.planting_date})"