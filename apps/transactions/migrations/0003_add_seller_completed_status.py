# Generated migration to add seller_completed status to SaleProcess

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0002_add_seller_lead'),
    ]

    operations = [
        migrations.AlterField(
            model_name='saleprocess',
            name='status',
            field=models.CharField(
                choices=[
                    ('seller_completed', 'Vendedor completado'),
                    ('contacto_inicial', 'Contacto inicial'),
                    ('evaluacion', 'Evaluación'),
                    ('valuacion', 'Valuación'),
                    ('presentacion', 'Presentación'),
                    ('firma_contrato', 'Firma de contrato'),
                    ('marketing', 'Marketing'),
                    ('publicacion', 'Publicación'),
                    ('cancelado', 'Cancelado'),
                ],
                default='seller_completed',
                max_length=20,
            ),
        ),
    ]
