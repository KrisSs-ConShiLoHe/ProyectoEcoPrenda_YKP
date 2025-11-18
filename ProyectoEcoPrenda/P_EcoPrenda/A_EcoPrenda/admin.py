from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import (
    Usuario, Prenda, Transaccion, TipoTransaccion,
    Fundacion, Mensaje, ImpactoAmbiental,
    Logro, UsuarioLogro, CampanaFundacion
)

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('id_usuario', 'nombre', 'apellido', 'correo', 'comuna', 'rol', 'fecha_registro')
    search_fields = ('nombre', 'apellido', 'correo')
    list_filter = ('comuna', 'rol', 'fecha_registro')
    ordering = ('-fecha_registro',)
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'correo', 'telefono', 'comuna', 'fecha_registro', 'imagen_usuario')
        }),
        ('Seguridad y Permisos', {
            'fields': ('rol', 'fundacion_asignada', 'es_staff')
        }),
        ('Contraseña', {
            'fields': ('contrasena',),
            'description': 'Ingresa la contraseña en texto plano. Se hasheará automáticamente al guardar.'
        }),
    )
    readonly_fields = ('fecha_registro',)

    def get_fieldsets(self, request, obj=None):
        """Mostrar campo de contraseña solo en creación (no en edición)."""
        fieldsets = super().get_fieldsets(request, obj)
        if obj:  # Edición (obj existe)
            fieldsets = tuple([fs for fs in fieldsets if fs[0] != 'Contraseña'])
        return fieldsets

    def save_model(self, request, obj, form, change):
        """Usar set_password si se proporciona contraseña_raw en creación."""
        if not change:  # Es creación (no edición)
            raw_password = request.POST.get('contrasena_raw')
            if raw_password:
                obj.set_password(raw_password)
        super().save_model(request, obj, form, change)

@admin.register(Prenda)
class PrendaAdmin(admin.ModelAdmin):
    list_display = ('id_prenda', 'nombre', 'categoria', 'talla', 'estado', 'disponibilidad', 'id_usuario', 'fecha_publicacion')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('categoria', 'talla', 'estado', 'disponibilidad', 'fecha_publicacion')
    ordering = ('-fecha_publicacion',)

@admin.register(TipoTransaccion)
class TipoTransaccionAdmin(admin.ModelAdmin):
    list_display = ('id_tipo', 'nombre_tipo', 'descripcion')
    search_fields = ('nombre_tipo',)

@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('id_transaccion', 'id_tipo', 'id_prenda', 'id_usuario_origen', 'id_usuario_destino', 'id_fundacion', 'id_campana', 'estado', 'fecha_transaccion')
    search_fields = ('id_prenda__nombre',)
    list_filter = ('id_tipo', 'estado', 'fecha_transaccion', 'id_fundacion', 'id_campana')
    ordering = ('-fecha_transaccion',)

@admin.register(Fundacion)
class FundacionAdmin(admin.ModelAdmin):
    list_display = ('id_fundacion', 'nombre', 'correo_contacto', 'telefono', 'direccion', 'activa')
    search_fields = ('nombre', 'correo_contacto')
    list_filter = ('activa',)

@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('id_mensaje', 'id_emisor', 'id_receptor', 'contenido_corto', 'fecha_envio')
    search_fields = ('contenido',)
    list_filter = ('fecha_envio',)
    ordering = ('-fecha_envio',)
    def contenido_corto(self, obj):
        return obj.contenido[:50] + '...' if len(obj.contenido) > 50 else obj.contenido
    contenido_corto.short_description = 'Contenido'

@admin.register(ImpactoAmbiental)
class ImpactoAmbientalAdmin(admin.ModelAdmin):
    list_display = ('id_impacto', 'id_prenda', 'carbono_evitar_kg', 'energia_ahorrada_kwh', 'fecha_calculo')
    search_fields = ('id_prenda__nombre',)
    list_filter = ('fecha_calculo',)
    ordering = ('-fecha_calculo',)

@admin.register(Logro)
class LogroAdmin(admin.ModelAdmin):
    list_display = ('id_logro', 'nombre', 'tipo', 'icono', 'codigo', 'requisito_valor')
    search_fields = ('nombre', 'descripcion', 'codigo')
    list_filter = ('tipo',)

@admin.register(UsuarioLogro)
class UsuarioLogroAdmin(admin.ModelAdmin):
    list_display = ('id_usuario_logro', 'usuario', 'logro', 'fecha_desbloqueo')
    search_fields = ('usuario__nombre', 'logro__nombre')
    list_filter = ('fecha_desbloqueo', 'logro__tipo')
    ordering = ('-fecha_desbloqueo',)

@admin.register(CampanaFundacion)
class CampanaFundacionAdmin(admin.ModelAdmin):
    list_display = ('id_campana', 'nombre', 'id_fundacion', 'fecha_inicio', 'fecha_fin', 'objetivo_prendas', 'activa')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('activa', 'id_fundacion', 'fecha_inicio', 'fecha_fin')
    ordering = ('-fecha_inicio',)
