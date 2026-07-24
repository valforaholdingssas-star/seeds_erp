# Generated manually for User.module_permissions

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_user_modules"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="module_permissions",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
