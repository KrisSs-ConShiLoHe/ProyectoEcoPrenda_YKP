from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django import forms  # Agregado para forms
import hashlib
import json
import logging  # Agregado para logging

from .models import (
    Usuario, Prenda, Transaccion, TipoTransaccion, 
    Fundacion, Mensaje, ImpactoAmbiental, 
    Logro, UsuarioLogro, CampanaFundacion
)
from .decorators import (
    login_required_custom, 
    anonymous_required,
    ajax_login_required, 
    session_valid,
    admin_required,
    representante_fundacion_required,
    moderador_required,
    cliente_only,
    role_required,
)
from django.conf import settings

from .cloudinary_utils import (
    subir_imagen_prenda,
    subir_imagen_usuario,
    subir_logo_fundacion,
    subir_imagen_campana,
    validar_imagen,
    eliminar_imagen_cloudinary,
    extraer_public_id_de_url
)

from .carbon_utils import (
    calcular_impacto_prenda,
    calcular_impacto_transaccion,
    obtener_impacto_total_usuario,
    obtener_impacto_total_plataforma,
    generar_informe_impacto,
    formatear_equivalencia
)

# Configuración de logging
logger = logging.getLogger(__name__)


# Forms para validaciones (agrega a forms.py si prefieres separar)
class RegistroForm(forms.ModelForm):
    contrasena = forms.CharField(widget=forms.PasswordInput, min_length=8)
    
    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'correo', 'telefono', 'comuna', 'rol']
    
    def clean_correo(self):
        correo = self.cleaned_data.get('correo')
        if Usuario.objects.filter(correo=correo).exists():
            raise forms.ValidationError('El correo ya está registrado.')
        return correo

class PerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'telefono', 'comuna', 'imagen_usuario']

# Forms para prendas (agrega a forms.py si prefieres separar)
class PrendaForm(forms.ModelForm):
    imagen_prenda = forms.ImageField(required=False, validators=[validar_imagen])  # Validación de imagen
    condicion = forms.ChoiceField(choices=[  # Campo para condición de conservación (agrega a models si no existe)
        ('Nuevo', 'Nuevo'),
        ('Excelente', 'Excelente'),
        ('Bueno', 'Bueno'),
        ('Usado', 'Usado'),
    ], required=True)
    
    class Meta:
        model = Prenda
        fields = ['nombre', 'descripcion', 'categoria', 'talla', 'imagen_prenda']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }