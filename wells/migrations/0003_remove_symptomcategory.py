# Generated manually to remove SymptomCategory table

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wells', '0002_riskassessment_completion_date_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clinicalsymptom',
            name='category',
        ),
        migrations.DeleteModel(
            name='SymptomCategory',
        ),
    ]
