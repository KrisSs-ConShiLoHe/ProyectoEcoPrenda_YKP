"""
Utilidades para cálculo de impacto ambiental con Carbon Interface API
Proporciona funciones para calcular emisiones de CO₂ evitadas y métricas ambientales
"""

import requests
from django.conf import settings
from decimal import Decimal


# ==============================================================================
# CONSTANTES DE IMPACTO AMBIENTAL - Basadas en estudios textiles
# ==============================================================================

# Emisiones promedio de CO₂ por producir una prenda nueva (kg)
EMISIONES_PRENDAS = {
    'Camiseta': 5.5,        # 5.5 kg CO₂
    'Pantalón': 11.0,       # 11 kg CO₂ (más si es jeans)
    'Vestido': 8.0,         # 8 kg CO₂
    'Chaqueta': 15.0,       # 15 kg CO₂ (más si es sintética)
    'Zapatos': 13.5,        # 13.5 kg CO₂
    'Accesorios': 3.0,      # 3 kg CO₂ (promedio)
    'default': 8.0,         # Valor por defecto
}

# Energía promedio para producir una prenda (kWh)
ENERGIA_PRENDAS = {
    'Camiseta': 2.7,
    'Pantalón': 5.5,
    'Vestido': 4.0,
    'Chaqueta': 8.0,
    'Zapatos': 7.0,
    'Accesorios': 1.5,
    'default': 4.0,
}

# Litros de agua necesarios para producir una prenda
AGUA_PRENDAS = {
    'Camiseta': 2700,       # 2,700 litros (especialmente algodón)
    'Pantalón': 7600,       # 7,600 litros (jeans)
    'Vestido': 4000,
    'Chaqueta': 6000,
    'Zapatos': 8000,
    'Accesorios': 1000,
    'default': 4000,
}


def calcular_impacto_prenda(categoria, peso_kg=None, usar_api=True):
    """
    Calcula el impacto ambiental de reutilizar una prenda.
    
    Args:
        categoria: Categoría de la prenda (Camiseta, Pantalón, etc.)
        peso_kg: Peso de la prenda en kg (opcional)
        usar_api: Si usar Carbon Interface API o valores predefinidos
    
    Returns:
        dict: {
            'carbono_evitado_kg': float,
            'energia_ahorrada_kwh': float,
            'agua_ahorrada_litros': float,
            'equivalencias': dict
        }
    """
    
    # Obtener valores base según categoría
    carbono = EMISIONES_PRENDAS.get(categoria, EMISIONES_PRENDAS['default'])
    energia = ENERGIA_PRENDAS.get(categoria, ENERGIA_PRENDAS['default'])
    agua = AGUA_PRENDAS.get(categoria, AGUA_PRENDAS['default'])
    
    # Si se proporciona peso, ajustar proporcionalente
    if peso_kg:
        factor = peso_kg / 0.5  # 0.5 kg = peso promedio de una prenda
        carbono *= factor
        energia *= factor
        agua *= factor
    
    # Si se solicita usar API y hay key configurada
    if usar_api and settings.CARBON_INTERFACE_API_KEY:
        try:
            # Llamar a API para cálculo más preciso
            resultado_api = calcular_con_api(categoria, peso_kg)
            if resultado_api:
                carbono = resultado_api.get('carbono_kg', carbono)
        except Exception as e:
            print(f"Error al usar Carbon Interface API: {e}")
            # Continuar con valores predefinidos
    
    # Calcular equivalencias comprensibles
    equivalencias = calcular_equivalencias(carbono, energia, agua)
    
    return {
        'carbono_evitado_kg': round(carbono, 2),
        'energia_ahorrada_kwh': round(energia, 2),
        'agua_ahorrada_litros': round(agua, 0),
        'equivalencias': equivalencias
    }


def calcular_con_api(categoria, peso_kg=None):
    """
    Usa Carbon Interface API para cálculo más preciso.
    
    Args:
        categoria: Categoría de la prenda
        peso_kg: Peso estimado
    
    Returns:
        dict con resultados de la API o None si falla
    """
    api_key = settings.CARBON_INTERFACE_API_KEY
    
    if not api_key:
        return None
    
    # Endpoint de Carbon Interface
    url = "https://www.carboninterface.com/api/v1/estimates"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Calcular estimación basada en electricidad (proxy para producción textil)
    # 1 kg de textil ≈ 15 kWh de energía
    kwh_estimado = (peso_kg or 0.5) * 15
    
    data = {
        "type": "electricity",
        "electricity_unit": "kwh",
        "electricity_value": kwh_estimado,
        "country": "cl"  # Chile
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        
        if response.status_code == 201:
            resultado = response.json()
            
            # Extraer datos de la respuesta
            attributes = resultado.get('data', {}).get('attributes', {})
            carbono_kg = attributes.get('carbon_kg', 0)
            
            return {
                'carbono_kg': carbono_kg,
                'metodo': 'api'
            }
        else:
            print(f"Error API Carbon Interface: {response.status_code}")
            return None
    
    except requests.exceptions.Timeout:
        print("Timeout al conectar con Carbon Interface API")
        return None
    except Exception as e:
        print(f"Error en Carbon Interface API: {str(e)}")
        return None


def calcular_equivalencias(carbono_kg, energia_kwh, agua_litros):
    """
    Convierte métricas ambientales en equivalencias comprensibles.
    
    Args:
        carbono_kg: CO₂ evitado en kg
        energia_kwh: Energía ahorrada en kWh
        agua_litros: Agua ahorrada en litros
    
    Returns:
        dict con equivalencias
    """
    
    # Conversiones basadas en promedios científicos
    equivalencias = {}
    
    # === CARBONO ===
    # 1 árbol absorbe ~20 kg CO₂/año
    equivalencias['arboles_año'] = round(carbono_kg / 20, 2)
    
    # Auto promedio emite 0.12 kg CO₂/km
    equivalencias['km_auto'] = round(carbono_kg / 0.12, 1)
    
    # Avión emite ~0.25 kg CO₂/km
    equivalencias['km_avion'] = round(carbono_kg / 0.25, 1)
    
    # === ENERGÍA ===
    # Bombilla LED de 10W encendida 1 hora = 0.01 kWh
    equivalencias['horas_bombilla'] = round(energia_kwh / 0.01, 0)
    
    # Carga de smartphone = 0.01 kWh
    equivalencias['cargas_celular'] = round(energia_kwh / 0.01, 0)
    
    # Hogar promedio usa 300 kWh/mes
    equivalencias['dias_hogar'] = round((energia_kwh / 300) * 30, 1)
    
    # === AGUA ===
    # Ducha de 10 minutos = 100 litros
    equivalencias['duchas'] = round(agua_litros / 100, 1)
    
    # Botella de agua = 0.5 litros
    equivalencias['botellas_agua'] = round(agua_litros / 0.5, 0)
    
    # Persona consume ~2 litros/día
    equivalencias['dias_agua_persona'] = round(agua_litros / 2, 0)
    
    return equivalencias


def calcular_impacto_transaccion(transaccion):
    """
    Calcula el impacto de una transacción completa.
    Incluye impacto de la prenda + impacto del transporte (si aplica).
    
    Args:
        transaccion: Objeto Transaccion
    
    Returns:
        dict con impacto total
    """
    prenda = transaccion.id_prenda
    
    # Impacto base de la prenda
    impacto = calcular_impacto_prenda(
        categoria=prenda.categoria,
        peso_kg=None,
        usar_api=False  # Usar valores predefinidos para transacciones
    )
    
    # Si hay envío, calcular impacto del transporte
    if transaccion.codigo_seguimiento_envio:
        impacto_transporte = calcular_impacto_transporte(transaccion)
        
        # Restar emisiones del transporte
        impacto['carbono_evitado_kg'] -= impacto_transporte.get('carbono_kg', 0)
        impacto['carbono_transporte_kg'] = impacto_transporte.get('carbono_kg', 0)
        
        # Recalcular equivalencias con el nuevo total
        impacto['equivalencias'] = calcular_equivalencias(
            impacto['carbono_evitado_kg'],
            impacto['energia_ahorrada_kwh'],
            impacto['agua_ahorrada_litros']
        )
    
    return impacto


def calcular_impacto_transporte(transaccion):
    """
    Calcula el impacto de CO₂ del transporte/envío.
    
    Args:
        transaccion: Objeto Transaccion con datos de envío
    
    Returns:
        dict con impacto del transporte
    """
    
    # Emisiones promedio por km según transporte
    EMISIONES_TRANSPORTE = {
        'moto': 0.08,      # kg CO₂ por km
        'auto': 0.12,      # kg CO₂ por km
        'van': 0.18,       # kg CO₂ por km
        'camion': 0.25,    # kg CO₂ por km
        'default': 0.12,   # Auto promedio
    }
    
    # Distancia estimada (Santiago promedio: 15 km)
    # En producción, podrías calcular distancia real entre coordenadas
    distancia_km = 15
    
    # Tipo de transporte (inferir de courier o usar default)
    tipo_transporte = 'default'
    if transaccion.courier:
        courier_lower = transaccion.courier.lower()
        if 'moto' in courier_lower:
            tipo_transporte = 'moto'
        elif 'van' in courier_lower or 'furgon' in courier_lower:
            tipo_transporte = 'van'
    
    emisiones_por_km = EMISIONES_TRANSPORTE[tipo_transporte]
    carbono_transporte = distancia_km * emisiones_por_km
    
    return {
        'carbono_kg': round(carbono_transporte, 2),
        'distancia_km': distancia_km,
        'tipo_transporte': tipo_transporte
    }


def obtener_impacto_total_usuario(usuario):
    """
    Calcula el impacto ambiental total de un usuario.
    
    Args:
        usuario: Objeto Usuario
    
    Returns:
        dict con impacto total acumulado
    """
    from .models import ImpactoAmbiental, Transaccion
    
    # Obtener todas las transacciones del usuario
    transacciones = Transaccion.objects.filter(
        id_usuario_origen=usuario,
        estado='COMPLETADA'
    )
    
    # Sumar impactos
    total_carbono = 0
    total_energia = 0
    total_agua = 0
    
    for transaccion in transacciones:
        try:
            impacto = ImpactoAmbiental.objects.get(id_prenda=transaccion.id_prenda)
            total_carbono += float(impacto.carbono_evitar_kg or 0)
            total_energia += float(impacto.energia_ahorrada_kwh or 0)
        except ImpactoAmbiental.DoesNotExist:
            # Calcular si no existe
            categoria = transaccion.id_prenda.categoria
            impacto_calc = calcular_impacto_prenda(categoria)
            total_carbono += impacto_calc['carbono_evitado_kg']
            total_energia += impacto_calc['energia_ahorrada_kwh']
            total_agua += impacto_calc['agua_ahorrada_litros']
    
    # Calcular equivalencias del total
    equivalencias = calcular_equivalencias(total_carbono, total_energia, total_agua)
    
    return {
        'total_carbono_kg': round(total_carbono, 2),
        'total_energia_kwh': round(total_energia, 2),
        'total_agua_litros': round(total_agua, 0),
        'total_transacciones': transacciones.count(),
        'equivalencias': equivalencias
    }


def obtener_impacto_total_plataforma():
    """
    Calcula el impacto ambiental total de toda la plataforma.
    
    Returns:
        dict con impacto global
    """
    from .models import ImpactoAmbiental
    from django.db.models import Sum
    
    # Sumar todos los impactos
    totales = ImpactoAmbiental.objects.aggregate(
        total_carbono=Sum('carbono_evitar_kg'),
        total_energia=Sum('energia_ahorrada_kwh')
    )
    
    carbono = float(totales['total_carbono'] or 0)
    energia = float(totales['total_energia'] or 0)
    
    # Estimar agua basada en carbono (proporción aproximada)
    agua = carbono * 500  # 1 kg CO₂ ≈ 500 litros agua en producción textil
    
    equivalencias = calcular_equivalencias(carbono, energia, agua)
    
    return {
        'total_carbono_kg': round(carbono, 2),
        'total_energia_kwh': round(energia, 2),
        'total_agua_litros': round(agua, 0),
        'equivalencias': equivalencias
    }


def generar_informe_impacto(usuario=None, fundacion=None):
    """
    Genera un informe detallado de impacto ambiental.
    
    Args:
        usuario: Usuario específico (opcional)
        fundacion: Fundación específica (opcional)
    
    Returns:
        dict con informe completo
    """
    from .models import Transaccion, ImpactoAmbiental
    
    if usuario:
        # Informe de usuario
        transacciones = Transaccion.objects.filter(
            id_usuario_origen=usuario,
            estado='COMPLETADA'
        ).select_related('id_prenda', 'id_tipo')
        
        titulo = f"Impacto de {usuario.nombre}"
    
    elif fundacion:
        # Informe de fundación
        transacciones = Transaccion.objects.filter(
            id_fundacion=fundacion,
            estado='COMPLETADA',
            id_tipo__nombre_tipo='Donación'
        ).select_related('id_prenda', 'id_usuario_origen')
        
        titulo = f"Impacto de {fundacion.nombre}"
    
    else:
        # Informe global
        transacciones = Transaccion.objects.filter(
            estado='COMPLETADA'
        ).select_related('id_prenda', 'id_tipo')
        
        titulo = "Impacto Global de EcoPrenda"
    
    # Desglose por tipo de transacción
    desglose = {}
    for trans in transacciones:
        tipo = trans.id_tipo.nombre_tipo
        if tipo not in desglose:
            desglose[tipo] = {
                'cantidad': 0,
                'carbono': 0,
                'energia': 0,
                'agua': 0
            }
        
        try:
            impacto = ImpactoAmbiental.objects.get(id_prenda=trans.id_prenda)
            carbono = float(impacto.carbono_evitar_kg or 0)
            energia = float(impacto.energia_ahorrada_kwh or 0)
        except ImpactoAmbiental.DoesNotExist:
            impacto_calc = calcular_impacto_prenda(trans.id_prenda.categoria)
            carbono = impacto_calc['carbono_evitado_kg']
            energia = impacto_calc['energia_ahorrada_kwh']
        
        desglose[tipo]['cantidad'] += 1
        desglose[tipo]['carbono'] += carbono
        desglose[tipo]['energia'] += energia
    
    # Totales
    total_carbono = sum(d['carbono'] for d in desglose.values())
    total_energia = sum(d['energia'] for d in desglose.values())
    total_agua = total_carbono * 500
    
    return {
        'titulo': titulo,
        'total_transacciones': transacciones.count(),
        'desglose': desglose,
        'totales': {
            'carbono_kg': round(total_carbono, 2),
            'energia_kwh': round(total_energia, 2),
            'agua_litros': round(total_agua, 0),
        },
        'equivalencias': calcular_equivalencias(total_carbono, total_energia, total_agua)
    }


# ==============================================================================
# FUNCIÓN HELPER PARA TEMPLATES
# ==============================================================================

def formatear_equivalencia(tipo, valor):
    """
    Formatea una equivalencia para mostrar en templates.
    
    Args:
        tipo: Tipo de equivalencia (arboles_año, km_auto, etc.)
        valor: Valor numérico
    
    Returns:
        str formateado
    """
    formatos = {
        'arboles_año': f"{valor} árbol(es) durante 1 año",
        'km_auto': f"{valor} km en automóvil",
        'km_avion': f"{valor} km en avión",
        'horas_bombilla': f"{int(valor)} horas de bombilla LED",
        'cargas_celular': f"{int(valor)} cargas de celular",
        'dias_hogar': f"{valor} día(s) de energía en un hogar",
        'duchas': f"{valor} ducha(s) de 10 minutos",
        'botellas_agua': f"{int(valor)} botellas de agua",
        'dias_agua_persona': f"{int(valor)} día(s) de agua para 1 persona",
    }
    
    return formatos.get(tipo, f"{valor} {tipo}")