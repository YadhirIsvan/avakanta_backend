# Generated migration to add created_by_membership field to SellerLead

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0003_add_seller_completed_status'),
        ('users', '0003_otpcode'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerlead',
            name='created_by_membership',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='created_seller_leads',
                to='users.tenantmembership',
                null=True, blank=True
            ),
        ),
    ]
