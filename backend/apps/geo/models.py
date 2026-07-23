from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.common.models import BaseModel


class GeoCatalog(BaseModel):
    municipality = models.CharField(max_length=128, db_index=True)
    municipality_code = models.CharField(max_length=16, unique=True)  # DANE
    department = models.CharField(max_length=128)
    department_iso = models.CharField(max_length=8, db_index=True)
    point = gis_models.PointField(null=True, blank=True, srid=4326)
    search = models.CharField(max_length=256, db_index=True)

    class Meta:
        ordering = ["department", "municipality"]
        indexes = [
            models.Index(fields=["search"]),
            models.Index(fields=["department_iso", "municipality"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipality} ({self.municipality_code})"
