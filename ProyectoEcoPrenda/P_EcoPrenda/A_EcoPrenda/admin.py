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
        ('Ubicación en Mapa', {
            'fields': ('direccion', 'lat', 'lng', 'mostrar_en_mapa')
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
        """Usar set_password si se proporciona contraseña en creación."""
        if not change:  # Es creación (no edición)
            raw_password = form.cleaned_data.get('contrasena')
            if raw_password:
                obj.set_password(raw_password)
        super().save_model(request, obj, form, change)

@admin.register(Prenda)
class PrendaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'categoria', 'talla', 'estado', 'user', 'fecha_publicacion')  # Cambié 'id_prenda' a 'id', 'id_usuario' a 'user', eliminé 'disponibilidad' (unificada en estado).
    search_fields = ('nombre', 'descripcion')
    list_filter = ('categoria', 'talla', 'estado', 'fecha_publicacion')
    ordering = ('-fecha_publicacion',)

@admin.register(TipoTransaccion)
class TipoTransaccionAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_tipo', 'descripcion')  # Cambié 'id_tipo' a 'id'.
    search_fields = ('nombre_tipo',)

@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'prenda', 'user_origen', 'user_destino', 'fundacion', 'campana', 'estado', 'fecha_transaccion')  # Cambié 'id_transaccion' a 'id', 'id_tipo' a 'tipo', 'id_prenda' a 'prenda', etc.
    search_fields = ('prenda__nombre',)  # Ajusté a 'prenda__nombre'.
    list_filter = ('tipo', 'estado', 'fecha_transaccion', 'fundacion', 'campana')
    ordering = ('-fecha_transaccion',)

@admin.register(Fundacion)
class FundacionAdmin(admin.ModelAdmin):
    list_display = ('id_fundacion', 'nombre', 'correo_contacto', 'telefono', 'direccion', 'activa')
    search_fields = ('nombre', 'correo_contacto')
    list_filter = ('activa',)

@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('id', 'emisor', 'receptor', 'contenido_corto', 'fecha_envio')  # Cambié 'id_mensaje' a 'id', 'id_emisor' a 'emisor', 'id_receptor' a 'receptor'.
    search_fields = ('contenido',)
    list_filter = ('fecha_envio',)
    ordering = ('-fecha_envio',)
    
    def contenido_corto(self, obj):
        return obj.contenido[:50] + '...' if len(obj.contenido) > 50 else obj.contenido
    contenido_corto.short_description = 'Contenido'

@admin.register(ImpactoAmbiental)
class ImpactoAmbientalAdmin(admin.ModelAdmin):
    list_display = ('id', 'prenda', 'carbono_evitar_kg', 'energia_ahorrada_kwh', 'fecha_calculo')  # Cambié 'id_impacto' a 'id', 'id_prenda' a 'prenda'.
    search_fields = ('prenda__nombre',)  # Ajusté a 'prenda__nombre'.
    list_filter = ('fecha_calculo',)
    ordering = ('-fecha_calculo',)

@admin.register(Logro)
class LogroAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'tipo', 'icono', 'codigo', 'requisito_valor')  # Cambié 'id_logro' a 'id'.
    search_fields = ('nombre', 'descripcion', 'codigo')
    list_filter = ('tipo',)

@admin.register(UsuarioLogro)
class UsuarioLogroAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'logro', 'fecha_desbloqueo')  # Cambié 'id_usuario_logro' a 'id', 'usuario' a 'user'.
    search_fields = ('user__nombre', 'logro__nombre')  # Ajusté a 'user__nombre'.
    list_filter = ('fecha_desbloqueo', 'logro__tipo')
    ordering = ('-fecha_desbloqueo',)

@admin.register(CampanaFundacion)
class CampanaFundacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'fundacion', 'fecha_inicio', 'fecha_fin', 'objetivo_prendas', 'activa')  # Cambié 'id_campana' a 'id', 'id_fundacion' a 'fundacion'.
    search_fields = ('nombre', 'descripcion')
    list_filter = ('activa', 'fundacion', 'fecha_inicio', 'fecha_fin')
    ordering = ('-fecha_inicio',)
