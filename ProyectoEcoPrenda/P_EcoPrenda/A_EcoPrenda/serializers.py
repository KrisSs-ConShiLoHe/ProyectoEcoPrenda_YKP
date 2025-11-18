from rest_framework import serializers
from .models import (
    Usuario, Prenda, Transaccion, TipoTransaccion,
    Fundacion, Mensaje, ImpactoAmbiental, Logro, UsuarioLogro, CampanaFundacion
)

# --- Serializers básicos ---

class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Usuario"""
    class Meta:
        model = Usuario
        exclude = ['contrasena']  # Seguridad: NUNCA enviar la contraseña por defecto
        read_only_fields = ['id_usuario', 'fecha_registro']

class TipoTransaccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoTransaccion
        fields = '__all__'

class FundacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fundacion
        fields = '__all__'

class ImpactoAmbientalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactoAmbiental
        fields = '__all__'

class LogroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Logro
        fields = '__all__'

class UsuarioLogroSerializer(serializers.ModelSerializer):
    logro = LogroSerializer(read_only=True)
    class Meta:
        model = UsuarioLogro
        fields = ['id_usuario_logro', 'usuario', 'logro', 'fecha_desbloqueo']

class CampanaFundacionSerializer(serializers.ModelSerializer):
    fundacion_nombre = serializers.CharField(source='id_fundacion.nombre', read_only=True)
    class Meta:
        model = CampanaFundacion
        fields = [
            'id_campana', 'id_fundacion', 'fundacion_nombre', 'nombre',
            'descripcion', 'imagen', 'fecha_inicio', 'fecha_fin', 'objetivo_prendas', 'activa', 'categorias_solicitadas'
        ]


# --- Serializers anidados / personalizados ---

class PrendaSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='id_usuario.nombre', read_only=True)
    usuario_apellido = serializers.CharField(source='id_usuario.apellido', read_only=True)
    fundacion_nombre = serializers.CharField(source='id_usuario.fundacion_asignada.nombre', read_only=True)
    impactoambiental = ImpactoAmbientalSerializer(source='impactoambiental_set', many=True, read_only=True)
    class Meta:
        model = Prenda
        fields = [
            'id_prenda', 'id_usuario', 'usuario_nombre', 'usuario_apellido', 'fundacion_nombre',
            'nombre', 'descripcion', 'categoria', 'talla', 'estado',
            'disponibilidad', 'fecha_publicacion', 'imagen_prenda', 'impactoambiental'
        ]
        read_only_fields = ['id_prenda', 'fecha_publicacion']

class PrendaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prenda
        fields = ['id_prenda', 'nombre', 'categoria', 'talla', 'estado']

class TransaccionSerializer(serializers.ModelSerializer):
    prenda = PrendaSimpleSerializer(source='id_prenda', read_only=True)
    tipo_nombre = serializers.CharField(source='id_tipo.nombre_tipo', read_only=True)
    usuario_origen_nombre = serializers.CharField(source='id_usuario_origen.nombre', read_only=True)
    usuario_destino_nombre = serializers.CharField(source='id_usuario_destino.nombre', read_only=True)
    fundacion_nombre = serializers.CharField(source='id_fundacion.nombre', read_only=True)
    campana_nombre = serializers.CharField(source='id_campana.nombre', read_only=True)
    class Meta:
        model = Transaccion
        fields = [
            'id_transaccion', 'id_prenda', 'prenda', 'id_tipo', 'tipo_nombre',
            'id_usuario_origen', 'usuario_origen_nombre', 'id_usuario_destino', 'usuario_destino_nombre',
            'id_fundacion', 'fundacion_nombre', 'id_campana', 'campana_nombre',
            'fecha_transaccion', 'estado'
        ]
        read_only_fields = ['id_transaccion', 'fecha_transaccion']

class MensajeSerializer(serializers.ModelSerializer):
    emisor_nombre = serializers.CharField(source='id_emisor.nombre', read_only=True)
    receptor_nombre = serializers.CharField(source='id_receptor.nombre', read_only=True)
    class Meta:
        model = Mensaje
        fields = [
            'id_mensaje', 'id_emisor', 'emisor_nombre', 'id_receptor', 'receptor_nombre',
            'contenido', 'fecha_envio'
        ]
        read_only_fields = ['id_mensaje', 'fecha_envio']

# --- Serializers para reportes y dashboard ---

class EstadisticasSerializer(serializers.Serializer):
    total_usuarios = serializers.IntegerField()
    total_prendas = serializers.IntegerField()
    total_transacciones = serializers.IntegerField()
    total_donaciones = serializers.IntegerField()
    carbono_evitado_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    energia_ahorrada_total = serializers.DecimalField(max_digits=10, decimal_places=2)

class ImpactoTotalSerializer(serializers.Serializer):
    total_carbono = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_energia = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_prendas_impactadas = serializers.IntegerField()
