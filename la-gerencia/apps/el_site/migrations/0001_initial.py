from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SiteChequeo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plataforma', models.CharField(db_index=True, max_length=40)),
                ('estado', models.CharField(choices=[('ok', 'OK'), ('error', 'Error'), ('no_configurada', 'No configurada')], max_length=20)),
                ('latencia_ms', models.IntegerField(blank=True, null=True)),
                ('mensaje_error', models.TextField(blank=True, null=True)),
                ('origen', models.CharField(choices=[('diario', 'Diario'), ('manual', 'Manual')], max_length=10)),
                ('actor_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('probado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'site_chequeo',
                'ordering': ['-probado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='sitechequeo',
            index=models.Index(fields=['plataforma', '-probado_en'], name='site_chequeo_plat_probado_idx'),
        ),
        migrations.CreateModel(
            name='SiteBackupRemoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archivo', models.CharField(max_length=240)),
                ('destino', models.CharField(default='HAL', max_length=80)),
                ('estado', models.CharField(choices=[('ok', 'OK'), ('error', 'Error')], max_length=10)),
                ('tamano_bytes', models.BigIntegerField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'site_backup_remoto',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='SiteDeploy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('ok', 'OK'), ('rollback', 'Rollback')], max_length=10)),
                ('commit', models.CharField(blank=True, default='', max_length=64)),
                ('nota', models.TextField(blank=True, default='')),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'site_deploy',
                'ordering': ['-creado_en'],
            },
        ),
    ]
