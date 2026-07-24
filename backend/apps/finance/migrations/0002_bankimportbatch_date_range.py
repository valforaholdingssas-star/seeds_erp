from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankimportbatch",
            name="date_from",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bankimportbatch",
            name="date_to",
            field=models.DateField(blank=True, null=True),
        ),
    ]
