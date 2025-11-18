from rest_framework import viewsets, status, generics
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models import (
    Usuario, Prenda, Transaccion, TipoTransaccion,
    Fundacion, Mensaje, ImpactoAmbiental, Logro, UsuarioLogro, CampanaFundacion
)
from .serializers import (
    UsuarioSerializer, PrendaSerializer, TransaccionSerializer,
    TipoTransaccionSerializer, FundacionSerializer, MensajeSerializer,
    ImpactoAmbientalSerializer, EstadisticasSerializer, ImpactoTotalSerializer,
    LogroSerializer, UsuarioLogroSerializer, CampanaFundacionSerializer,
    PrendaSimpleSerializer, 
)

# Funciones basadas en vistas

@api_view(['GET', 'POST'])
def prenda_list(request):
    """
    GET: Lista todas las prendas con filtros opcionales por categoria, talla, estado.
    POST: Crea una nueva prenda.
    """
    if request.method == 'GET':
        prendas = Prenda.objects.all()
        
        # Filtros opcionales
        categoria = request.query_params.get('categoria', None)
        talla = request.query_params.get('talla', None)
        estado = request.query_params.get('estado', None)
        
        if categoria:
            prendas = prendas.filter(categoria=categoria)
        if talla:
            prendas = prendas.filter(talla=talla)
        if estado:
            prendas = prendas.filter(estado=estado)
        
        serializer = PrendaSerializer(prendas, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = PrendaSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
def prenda_detail(request, pk):
    """
    GET: Obtiene una prenda específica.
    PUT: Actualiza una prenda.
    DELETE: Elimina una prenda.
    """
    try:
        prenda = Prenda.objects.get(pk=pk)
    except Prenda.DoesNotExist:
        return Response({'error': 'Prenda no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = PrendaSerializer(prenda)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = PrendaSerializer(prenda, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        prenda.delete()
        return Response({'message': 'Prenda eliminada'}, status=status.HTTP_204_NO_CONTENT)


# Clases basadas en vistas (APIView)

class UsuarioListAPIView(APIView):
    """
    GET: Lista todos los usuarios.
    POST: Crea un nuevo usuario.
    """
    
    def get(self, request):
        usuarios = Usuario.objects.all()
        serializer = UsuarioSerializer(usuarios, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = UsuarioSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UsuarioDetailAPIView(APIView):
    """
    GET: Obtiene un usuario específico.
    PUT: Actualiza un usuario.
    DELETE: Elimina un usuario.
    """
    
    def get_object(self, pk):
        try:
            return Usuario.objects.get(pk=pk)
        except Usuario.DoesNotExist:
            return None
    
    def get(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UsuarioSerializer(usuario)
        return Response(serializer.data)
    
    def put(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UsuarioSerializer(usuario, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        usuario = self.get_object(pk)
        if not usuario:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        usuario.delete()
        return Response({'message': 'Usuario eliminado'}, status=status.HTTP_204_NO_CONTENT)


# Vistas basadas en genéricos (generics)

class TransaccionListCreateAPIView(generics.ListCreateAPIView):
    """Lista y crea transacciones."""
    queryset = Transaccion.objects.all()
    serializer_class = TransaccionSerializer


class TransaccionDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Obtiene, actualiza y elimina transacciones."""
    queryset = Transaccion.objects.all()
    serializer_class = TransaccionSerializer
    lookup_field = 'pk'


class FundacionListCreateAPIView(generics.ListCreateAPIView):
    """Lista y crea fundaciones."""
    queryset = Fundacion.objects.all()
    serializer_class = FundacionSerializer


class FundacionDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Obtiene, actualiza y elimina fundaciones."""
    queryset = Fundacion.objects.all()
    serializer_class = FundacionSerializer
    lookup_field = 'pk'


# Conjuntos de vistas (ViewSets)

class PrendaViewSet(viewsets.ModelViewSet):
    """ViewSet para Prendas - CRUD completo"""
    queryset = Prenda.objects.all()
    serializer_class = PrendaSerializer
    
    def get_queryset(self):
        """Permite filtrar prendas por query params"""
        queryset = Prenda.objects.all()
        categoria = self.request.query_params.get('categoria', None)
        usuario = self.request.query_params.get('usuario', None)
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        if usuario:
            queryset = queryset.filter(id_usuario=usuario)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def categorias(self, request):
        """Endpoint personalizado: Lista todas las categorías únicas"""
        categorias = Prenda.objects.values_list('categoria', flat=True).distinct()
        return Response({'categorias': list(categorias)})
    
    @action(detail=True, methods=['get'])
    def impacto(self, request, pk=None):
        """Endpoint personalizado: Obtiene el impacto ambiental de una prenda"""
        prenda = self.get_object()
        impacto = ImpactoAmbiental.objects.filter(id_prenda=prenda).first()
        if impacto:
            serializer = ImpactoAmbientalSerializer(impacto)
            return Response(serializer.data)
        return Response({'message': 'No hay impacto registrado'}, status=status.HTTP_404_NOT_FOUND)


class UsuarioViewSet(viewsets.ModelViewSet):
    """ViewSet para Usuarios - CRUD completo"""
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    
    @action(detail=True, methods=['get'])
    def prendas(self, request, pk=None):
        """Obtiene todas las prendas de un usuario"""
        usuario = self.get_object()
        prendas = Prenda.objects.filter(id_usuario=usuario)
        serializer = PrendaSerializer(prendas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def transacciones(self, request, pk=None):
        """Obtiene todas las transacciones de un usuario"""
        usuario = self.get_object()
        transacciones = Transaccion.objects.filter(id_usuario_origen=usuario) | Transaccion.objects.filter(id_usuario_destino=usuario)
        serializer = TransaccionSerializer(transacciones.distinct(), many=True)
        return Response(serializer.data)


class FundacionViewSet(viewsets.ModelViewSet):
    """ViewSet para Fundaciones - CRUD completo"""
    queryset = Fundacion.objects.all()
    serializer_class = FundacionSerializer
    
    @action(detail=True, methods=['get'])
    def donaciones(self, request, pk=None):
        """Obtiene todas las donaciones recibidas por una fundación"""
        fundacion = self.get_object()
        donaciones = Transaccion.objects.filter(id_fundacion=fundacion)
        serializer = TransaccionSerializer(donaciones, many=True)
        return Response(serializer.data)


class TipoTransaccionViewSet(viewsets.ModelViewSet):
    """ViewSet para Tipos de Transacción - CRUD completo"""
    queryset = TipoTransaccion.objects.all()
    serializer_class = TipoTransaccionSerializer
    
    @action(detail=True, methods=['get'])
    def transacciones(self, request, pk=None):
        """Obtiene todas las transacciones de un tipo específico"""
        tipo = self.get_object()
        transacciones = Transaccion.objects.filter(id_tipo=tipo)
        serializer = TransaccionSerializer(transacciones, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas por tipo de transacción"""
        tipos_stats = []
        for tipo in TipoTransaccion.objects.all():
            count = Transaccion.objects.filter(id_tipo=tipo).count()
            tipos_stats.append({
                'id': tipo.id_tipo,
                'nombre': tipo.nombre_tipo,
                'total_transacciones': count
            })
        return Response(tipos_stats)


class MensajeViewSet(viewsets.ModelViewSet):
    """ViewSet para Mensajes - CRUD completo"""
    queryset = Mensaje.objects.all()
    serializer_class = MensajeSerializer
    
    def get_queryset(self):
        """Permite filtrar mensajes por emisor o receptor"""
        queryset = Mensaje.objects.all()
        emisor = self.request.query_params.get('emisor', None)
        receptor = self.request.query_params.get('receptor', None)
        
        if emisor:
            queryset = queryset.filter(id_emisor=emisor)
        if receptor:
            queryset = queryset.filter(id_receptor=receptor)
        
        return queryset.order_by('-fecha_envio')
    
    @action(detail=False, methods=['get'])
    def conversacion(self, request):
        """Obtiene la conversación entre dos usuarios"""
        usuario1_id = request.query_params.get('usuario1', None)
        usuario2_id = request.query_params.get('usuario2', None)
        
        if not usuario1_id or not usuario2_id:
            return Response(
                {'error': 'Se requieren los parámetros usuario1 y usuario2'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        mensajes = Mensaje.objects.filter(
            (Q(id_emisor=usuario1_id) & Q(id_receptor=usuario2_id)) |
            (Q(id_emisor=usuario2_id) & Q(id_receptor=usuario1_id))
        ).order_by('fecha_envio')
        
        serializer = MensajeSerializer(mensajes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def enviar(self, request):
        """Enviar un nuevo mensaje"""
        serializer = MensajeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(fecha_envio=timezone.now())
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ImpactoAmbientalViewSet(viewsets.ModelViewSet):
    """ViewSet para Impacto Ambiental - CRUD completo"""
    queryset = ImpactoAmbiental.objects.all()
    serializer_class = ImpactoAmbientalSerializer
    
    @action(detail=False, methods=['get'])
    def por_prenda(self, request):
        """Obtiene el impacto de una prenda específica"""
        prenda_id = request.query_params.get('prenda', None)
        if not prenda_id:
            return Response(
                {'error': 'Se requiere el parámetro prenda'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        impactos = ImpactoAmbiental.objects.filter(id_prenda=prenda_id)
        serializer = ImpactoAmbientalSerializer(impactos, many=True)
        return Response(serializer.data)


class TransaccionViewSet(viewsets.ModelViewSet):
    """ViewSet para Transacciones - CRUD completo"""
    queryset = Transaccion.objects.all()
    serializer_class = TransaccionSerializer
    
    def get_queryset(self):
        """Permite filtrar transacciones por query params"""
        queryset = Transaccion.objects.all()
        tipo = self.request.query_params.get('tipo', None)
        usuario = self.request.query_params.get('usuario', None)
        estado = self.request.query_params.get('estado', None)
        fundacion = self.request.query_params.get('fundacion', None)
        
        if tipo:
            queryset = queryset.filter(id_tipo=tipo)
        if usuario:
            queryset = queryset.filter(
                Q(id_usuario_origen=usuario) | Q(id_usuario_destino=usuario)
            )
        if estado:
            queryset = queryset.filter(estado=estado)
        if fundacion:
            queryset = queryset.filter(id_fundacion=fundacion)
        
        return queryset.order_by('-fecha_transaccion')
    
    @action(detail=False, methods=['get'])
    def por_tipo(self, request):
        """Obtiene transacciones agrupadas por tipo"""
        tipos = TipoTransaccion.objects.all()
        resultado = []
        
        for tipo in tipos:
            transacciones = Transaccion.objects.filter(id_tipo=tipo)
            resultado.append({
                'tipo': tipo.nombre_tipo,
                'total': transacciones.count(),
                'transacciones': TransaccionSerializer(transacciones, many=True).data
            })
        
        return Response(resultado)
    
    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Obtiene todas las transacciones pendientes"""
        transacciones = Transaccion.objects.filter(estado='Pendiente')
        serializer = TransaccionSerializer(transacciones, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de una transacción"""
        transaccion = self.get_object()
        nuevo_estado = request.data.get('estado', None)
        
        if not nuevo_estado:
            return Response(
                {'error': 'Se requiere el campo estado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        estados_validos = ['Pendiente', 'Aceptada', 'Rechazada', 'Completada', 'Cancelada']
        if nuevo_estado not in estados_validos:
            return Response(
                {'error': f'Estado inválido. Estados válidos: {estados_validos}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transaccion.estado = nuevo_estado
        transaccion.save()
        
        serializer = TransaccionSerializer(transaccion)
        return Response(serializer.data)


# Puntos finales personalizados (Endpoints)

class EstadisticasAPIView(APIView):
    """Estadísticas generales del sistema."""
    
    def get(self, request):
        total_usuarios = Usuario.objects.count()
        total_prendas = Prenda.objects.count()
        total_transacciones = Transaccion.objects.count()
        total_donaciones = Transaccion.objects.filter(id_tipo__nombre_tipo='Donación').count()
        
        impacto = ImpactoAmbiental.objects.aggregate(
            carbono=Sum('carbono_evitar_kg'),
            energia=Sum('energia_ahorrada_kwh')
        )
        
        data = {
            'total_usuarios': total_usuarios,
            'total_prendas': total_prendas,
            'total_transacciones': total_transacciones,
            'total_donaciones': total_donaciones,
            'carbono_evitado_total': impacto['carbono'] or 0,
            'energia_ahorrada_total': impacto['energia'] or 0
        }
        
        serializer = EstadisticasSerializer(data=data)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ImpactoTotalAPIView(APIView):
    """Impacto ambiental total del sistema."""
    
    def get(self, request):
        impacto = ImpactoAmbiental.objects.aggregate(
            total_carbono=Sum('carbono_evitar_kg'),
            total_energia=Sum('energia_ahorrada_kwh'),
            total_prendas_impactadas=Count('id_prenda')
        )
        
        serializer = ImpactoTotalSerializer(data=impacto)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---- Logros ----
class LogroViewSet(viewsets.ModelViewSet):
    """CRUD completo para Logro"""
    queryset = Logro.objects.all()
    serializer_class = LogroSerializer

# ---- UsuarioLogro ----
class UsuarioLogroViewSet(viewsets.ModelViewSet):
    """CRUD completo para logros obtenidos por usuario"""
    queryset = UsuarioLogro.objects.all()
    serializer_class = UsuarioLogroSerializer

    # Custom: logros de usuario por parámetro
    @action(detail=False, methods=['get'])
    def por_usuario(self, request):
        usuario_id = request.query_params.get('usuario_id')
        if not usuario_id:
            return Response({'error': 'Parametro usuario_id obligatorio'}, status=status.HTTP_400_BAD_REQUEST)
        logros = UsuarioLogro.objects.filter(usuario_id=usuario_id)
        serializer = self.get_serializer(logros, many=True)
        return Response(serializer.data)
    
# ---- Campañas de Fundación ----
class CampanaFundacionViewSet(viewsets.ModelViewSet):
    """CRUD para campañas solidarias"""
    queryset = CampanaFundacion.objects.all()
    serializer_class = CampanaFundacionSerializer

    # Custom: campañas activas
    @action(detail=False, methods=['get'])
    def activas(self, request):
        campanas = CampanaFundacion.objects.filter(activa=True)
        serializer = self.get_serializer(campanas, many=True)
        return Response(serializer.data)
    
    # Custom: campañas por fundación
    @action(detail=False, methods=['get'])
    def por_fundacion(self, request):
        fundacion_id = request.query_params.get('fundacion_id')
        if not fundacion_id:
            return Response({'error': 'Parametro fundacion_id obligatorio'}, status=status.HTTP_400_BAD_REQUEST)
        campanas = CampanaFundacion.objects.filter(id_fundacion=fundacion_id)
        serializer = self.get_serializer(campanas, many=True)
        return Response(serializer.data)

# ---- Prenda Simple: lista sin relaciones ----
class PrendaSimpleListAPIView(generics.ListAPIView):
    """Lista de prendas sin relaciones (optimizada)"""
    queryset = Prenda.objects.all()
    serializer_class = PrendaSimpleSerializer
