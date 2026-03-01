import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0002_tenant_city'),
        ('users', '0003_otpcode'),
        ('properties', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseProcess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('lead', 'Lead'), ('visita', 'Visita'), ('interes', 'Interés'),
                        ('pre_aprobacion', 'Pre-aprobación'), ('avaluo', 'Avalúo'),
                        ('credito', 'Crédito'), ('docs_finales', 'Docs finales'),
                        ('escrituras', 'Escrituras'), ('cerrado', 'Cerrado'),
                        ('cancelado', 'Cancelado'),
                    ],
                    default='lead', max_length=20,
                )),
                ('overall_progress', models.PositiveIntegerField(default=0)),
                ('notes', models.TextField(blank=True)),
                ('sale_price', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('payment_method', models.CharField(blank=True, max_length=100)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='purchase_processes',
                    to='tenants.tenant',
                )),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='purchase_processes',
                    to='properties.property',
                )),
                ('client_membership', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='client_purchase_processes',
                    to='users.tenantmembership',
                )),
                ('agent_membership', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='agent_purchase_processes',
                    to='users.tenantmembership',
                )),
            ],
            options={'db_table': 'purchase_processes'},
        ),
        migrations.CreateModel(
            name='SaleProcess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('contacto_inicial', 'Contacto inicial'), ('evaluacion', 'Evaluación'),
                        ('valuacion', 'Valuación'), ('presentacion', 'Presentación'),
                        ('firma_contrato', 'Firma de contrato'), ('marketing', 'Marketing'),
                        ('publicacion', 'Publicación'), ('cancelado', 'Cancelado'),
                    ],
                    default='contacto_inicial', max_length=20,
                )),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sale_processes',
                    to='tenants.tenant',
                )),
                ('property', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sale_processes',
                    to='properties.property',
                )),
                ('client_membership', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='client_sale_processes',
                    to='users.tenantmembership',
                )),
                ('agent_membership', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='agent_sale_processes',
                    to='users.tenantmembership',
                )),
            ],
            options={'db_table': 'sale_processes'},
        ),
        migrations.CreateModel(
            name='ProcessStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('process_type', models.CharField(
                    choices=[('purchase', 'Compra'), ('sale', 'Venta')],
                    max_length=10,
                )),
                ('process_id', models.PositiveIntegerField()),
                ('previous_status', models.CharField(blank=True, max_length=50)),
                ('new_status', models.CharField(max_length=50)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by_membership', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='status_history_changes',
                    to='users.tenantmembership',
                )),
            ],
            options={'db_table': 'process_status_history'},
        ),
    ]
