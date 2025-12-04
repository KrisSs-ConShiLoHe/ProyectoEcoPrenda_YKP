"""
Utilidades para gestión de imágenes con Cloudinary
Proporciona funciones helper para subida, transformación y eliminación de imágenes
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from django.conf import settings


def subir_imagen_cloudinary(imagen, carpeta='ecoprenda', public_id=None, transformaciones=None):
    """
    Sube una imagen a Cloudinary con opciones de transformación.
    
    Args:
        imagen: Archivo de imagen (UploadedFile de Django)
        carpeta: Carpeta en Cloudinary donde guardar (default: 'ecoprenda')
        public_id: ID público personalizado (opcional)
        transformaciones: Dict con transformaciones a aplicar
    
    Returns:
        dict: Respuesta de Cloudinary con URL, public_id, etc.
        None: Si hay error
    
    Ejemplo:
        resultado = subir_imagen_cloudinary(
            imagen=request.FILES['imagen_prenda'],
            carpeta='prendas',
            transformaciones={'width': 800, 'height': 600, 'crop': 'fill'}
        )
    """
    try:
        # Opciones base
        opciones = {
            'folder': carpeta,
            'resource_type': 'image',
            'quality': 'auto:good',  # Compresión automática
            'fetch_format': 'auto',   # Formato automático (WebP si es soportado)
        }
        
        # Agregar public_id si se proporciona
        if public_id:
            opciones['public_id'] = public_id
            opciones['overwrite'] = True
        
        # Agregar transformaciones si se proporcionan
        if transformaciones:
            opciones['transformation'] = transformaciones
        
        # Subir imagen
        resultado = cloudinary.uploader.upload(imagen, **opciones)
        
        return resultado
    
    except Exception as e:
        print(f"Error al subir imagen a Cloudinary: {str(e)}")
        return None


def eliminar_imagen_cloudinary(public_id):
    """
    Elimina una imagen de Cloudinary.
    
    Args:
        public_id: ID público de la imagen en Cloudinary
    
    Returns:
        bool: True si se eliminó correctamente, False en caso contrario
    """
    try:
        resultado = cloudinary.uploader.destroy(public_id)
        return resultado.get('result') == 'ok'
    except Exception as e:
        print(f"Error al eliminar imagen de Cloudinary: {str(e)}")
        return False


def obtener_url_transformada(public_id, transformaciones):
    """
    Genera URL de Cloudinary con transformaciones aplicadas.
    
    Args:
        public_id: ID público de la imagen
        transformaciones: Dict con transformaciones
    
    Returns:
        str: URL transformada
    
    Ejemplo:
        url = obtener_url_transformada(
            'ecoprenda/prenda_123',
            {'width': 400, 'height': 400, 'crop': 'thumb'}
        )
    """
    try:
        url, options = cloudinary.utils.cloudinary_url(
            public_id,
            **transformaciones
        )
        return url
    except Exception as e:
        print(f"Error al generar URL transformada: {str(e)}")
        return None


def subir_imagen_prenda(imagen, id_prenda):
    """
    Sube imagen de prenda con configuraciones optimizadas.
    
    Args:
        imagen: Archivo de imagen
        id_prenda: ID de la prenda
    
    Returns:
        dict: Resultado de Cloudinary
    """
    transformaciones = {
        'width': 800,
        'height': 800,
        'crop': 'limit',  # No recortar, solo limitar tamaño máximo
        'quality': 'auto:good',
    }
    
    return subir_imagen_cloudinary(
        imagen=imagen,
        carpeta='ecoprenda/prendas',
        public_id=f'prenda_{id_prenda}',
        transformaciones=transformaciones
    )


def subir_imagen_usuario(imagen, id_usuario):
    """
    Sube foto de perfil de usuario con configuraciones optimizadas.
    
    Args:
        imagen: Archivo de imagen
        id_usuario: ID del usuario
    
    Returns:
        dict: Resultado de Cloudinary
    """
    transformaciones = {
        'width': 400,
        'height': 400,
        'crop': 'fill',  # Recortar para mantener aspecto cuadrado
        'gravity': 'face',  # Enfocar en la cara si detecta una
        'quality': 'auto:good',
    }
    
    return subir_imagen_cloudinary(
        imagen=imagen,
        carpeta='ecoprenda/usuarios',
        public_id=f'usuario_{id_usuario}',
        transformaciones=transformaciones
    )


def subir_logo_fundacion(imagen, id_fundacion):
    """
    Sube logo de fundación con configuraciones optimizadas.
    
    Args:
        imagen: Archivo de imagen
        id_fundacion: ID de la fundación
    
    Returns:
        dict: Resultado de Cloudinary
    """
    transformaciones = {
        'width': 500,
        'height': 500,
        'crop': 'fit',  # Ajustar manteniendo aspecto
        'quality': 'auto:best',  # Mejor calidad para logos
        'background': 'transparent',  # Fondo transparente si es PNG
    }
    
    return subir_imagen_cloudinary(
        imagen=imagen,
        carpeta='ecoprenda/fundaciones',
        public_id=f'fundacion_{id_fundacion}',
        transformaciones=transformaciones
    )


def subir_imagen_campana(imagen, id_campana):
    """
    Sube imagen de campaña con configuraciones optimizadas.
    
    Args:
        imagen: Archivo de imagen
        id_campana: ID de la campaña
    
    Returns:
        dict: Resultado de Cloudinary
    """
    transformaciones = {
        'width': 1200,
        'height': 630,  # Formato ideal para redes sociales (Open Graph)
        'crop': 'fill',
        'quality': 'auto:good',
    }
    
    return subir_imagen_cloudinary(
        imagen=imagen,
        carpeta='ecoprenda/campanas',
        public_id=f'campana_{id_campana}',
        transformaciones=transformaciones
    )


def obtener_miniaturas(public_id):
    """
    Genera URLs de miniaturas en diferentes tamaños.
    
    Args:
        public_id: ID público de la imagen
    
    Returns:
        dict: URLs de diferentes tamaños
    """
    tamaños = {
        'thumbnail': {'width': 150, 'height': 150, 'crop': 'thumb'},
        'small': {'width': 300, 'height': 300, 'crop': 'limit'},
        'medium': {'width': 600, 'height': 600, 'crop': 'limit'},
        'large': {'width': 1200, 'height': 1200, 'crop': 'limit'},
    }
    
    urls = {}
    for nombre, transformacion in tamaños.items():
        urls[nombre] = obtener_url_transformada(public_id, transformacion)
    
    return urls


def validar_imagen(imagen, max_size_mb=5):
    """
    Valida que el archivo sea una imagen válida.
    
    Args:
        imagen: Archivo subido
        max_size_mb: Tamaño máximo en MB
    
    Returns:
        tuple: (es_valido: bool, mensaje_error: str)
    """
    # Validar que existe
    if not imagen:
        return False, "No se proporcionó ninguna imagen"
    
    # Validar tipo de archivo
    tipos_permitidos = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if imagen.content_type not in tipos_permitidos:
        return False, f"Tipo de archivo no permitido. Usa: JPG, PNG, GIF o WebP"
    
    # Validar tamaño
    max_size_bytes = max_size_mb * 1024 * 1024
    if imagen.size > max_size_bytes:
        return False, f"La imagen es muy grande. Máximo: {max_size_mb}MB"
    
    return True, ""


def extraer_public_id_de_url(url):
    """
    Extrae el public_id de una URL de Cloudinary.
    
    Args:
        url: URL completa de Cloudinary
    
    Returns:
        str: public_id extraído o None
    
    Ejemplo:
        url = "https://res.cloudinary.com/demo/image/upload/v1234/ecoprenda/prendas/prenda_123.jpg"
        public_id = extraer_public_id_de_url(url)  # "ecoprenda/prendas/prenda_123"
    """
    try:
        # Buscar el patrón /upload/v[número]/[public_id]
        partes = url.split('/upload/')
        if len(partes) < 2:
            return None
        
        # Tomar la parte después de /upload/
        ruta = partes[1]
        
        # Remover versión (v1234567890)
        if ruta.startswith('v'):
            ruta = '/'.join(ruta.split('/')[1:])
        
        # Remover extensión
        public_id = '.'.join(ruta.split('.')[:-1])
        
        return public_id
    except Exception as e:
        print(f"Error al extraer public_id: {str(e)}")
        return None


# ==============================================================================
# TRANSFORMACIONES COMUNES
# ==============================================================================

TRANSFORMACIONES_PRENDA = {
    'lista': {'width': 300, 'height': 300, 'crop': 'fill'},
    'detalle': {'width': 800, 'height': 800, 'crop': 'limit'},
    'galeria': {'width': 600, 'height': 600, 'crop': 'fill'},
}

TRANSFORMACIONES_PERFIL = {
    'avatar': {'width': 100, 'height': 100, 'crop': 'thumb', 'gravity': 'face'},
    'perfil': {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'},
}

TRANSFORMACIONES_FUNDACION = {
    'logo_pequeno': {'width': 150, 'height': 150, 'crop': 'fit'},
    'logo_grande': {'width': 500, 'height': 500, 'crop': 'fit'},
}