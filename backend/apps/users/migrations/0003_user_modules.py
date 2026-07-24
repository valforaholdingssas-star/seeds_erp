# Generated manually for modules field on User

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_password_reset_and_monthly_goal"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="modules",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
