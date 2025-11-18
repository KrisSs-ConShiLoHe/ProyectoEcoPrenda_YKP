from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from .models import Prenda, Transaccion, Fundacion, Mensaje

class Command(BaseCommand):
    help = 'Crea los grupos de usuarios y asigna permisos automáticamente para EcoPrenda'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Creando grupos y asignando permisos...'))

        roles = {
            'Cliente': [
                ('view_prenda', Prenda),
                ('view_transaccion', Transaccion),
                ('add_mensaje', Mensaje),
                ('view_mensaje', Mensaje),
            ],
            'Representante de Fundación': [
                ('view_prenda', Prenda),
                ('view_transaccion', Transaccion),
                ('change_transaccion', Transaccion),
                ('view_fundacion', Fundacion),
                ('add_mensaje', Mensaje),
                ('view_mensaje', Mensaje),
            ],
            'Moderador': [
                ('view_prenda', Prenda),
                ('change_prenda', Prenda),
                ('delete_prenda', Prenda),
                ('view_transaccion', Transaccion),
                ('change_transaccion', Transaccion),
                ('view_fundacion', Fundacion),
                ('change_fundacion', Fundacion),
            ],
            'Administrador': Permission.objects.all(),
        }

        for nombre_grupo, permisos in roles.items():
            grupo, creado = Group.objects.get_or_create(name=nombre_grupo)
            if creado:
                self.stdout.write(self.style.SUCCESS(f'✓ Grupo "{nombre_grupo}" creado'))
            else:
                self.stdout.write(self.style.WARNING(f'Grupo "{nombre_grupo}" ya existe'))

            if nombre_grupo == 'Administrador':
                grupo.permissions.set(permisos)
            else:
                count_asignados = 0
                for codename, modelo in permisos:
                    ct = ContentType.objects.get_for_model(modelo)
                    try:
                        permiso = Permission.objects.get(codename=codename, content_type=ct)
                        grupo.permissions.add(permiso)
                        count_asignados += 1
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'  Permiso {codename} no encontrado para modelo {modelo.__name__}'))
                self.stdout.write(self.style.SUCCESS(f'  → {count_asignados} permisos asignados a {nombre_grupo}'))

        self.stdout.write(self.style.SUCCESS('¡Grupos y permisos listos para EcoPrenda!'))
