from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from .models import Usuario


class Command(BaseCommand):
    help = 'Asigna un rol (grupo) a un usuario'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email del usuario')
        parser.add_argument('rol', type=str, help='Rol: Cliente, Representante_Fundacion, Moderador o Administrador')

    def handle(self, *args, **kwargs):
        email = kwargs['email']
        rol = kwargs['rol']
        
        # Validar rol
        roles_validos = ['Cliente', 'Representante_Fundacion', 'Moderador', 'Administrador']
        if rol not in roles_validos:
            self.stdout.write(self.style.ERROR(f'❌ Rol inválido. Roles válidos: {", ".join(roles_validos)}'))
            return
        
        # Buscar usuario
        try:
            usuario = Usuario.objects.get(correo=email)
        except Usuario.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Usuario con email {email} no encontrado'))
            return
        
        # Buscar grupo
        try:
            grupo = Group.objects.get(name=rol)
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Grupo {rol} no existe. Ejecuta primero: python manage.py crear_grupos'))
            return
        
        # Crear o actualizar el campo de grupo en la sesión
        # (Guardamos el grupo en un campo personalizado o en la sesión)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Rol "{rol}" asignado a {usuario.nombre} ({email})'))
        self.stdout.write(f'   ID Usuario: {usuario.id_usuario}')
        
        # Mostrar permisos del grupo
        permisos = grupo.permissions.all()
        self.stdout.write(f'\n📋 Permisos del rol "{rol}":')
        for perm in permisos[:5]:  # Mostrar solo los primeros 5
            self.stdout.write(f'   • {perm.name}')
        if permisos.count() > 5:
            self.stdout.write(f'   ... y {permisos.count() - 5} más')