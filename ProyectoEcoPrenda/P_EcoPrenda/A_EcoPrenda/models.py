from django.db import models
from django.utils import timezone

# ------------------- Usuario ----------------------

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True, null=True)
    correo = models.CharField(unique=True, max_length=120)
    contrasena = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    comuna = models.CharField(max_length=100, blank=True, null=True)
    fecha_registro = models.DateTimeField(default=timezone.now, blank=True, null=True)
    
    ROL_CHOICES = [
        ('CLIENTE', 'Cliente'),
        ('REPRESENTANTE_FUNDACION', 'Representante de Fundación'),
        ('MODERADOR', 'Moderador'),
        ('ADMINISTRADOR', 'Administrador'),
    ]

    rol = models.CharField(
        max_length=30, 
        choices=ROL_CHOICES, 
        default='CLIENTE',
        help_text='Rol del usuario en el sistema'
    )
    fundacion_asignada = models.ForeignKey(
        'Fundacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='representantes',
        help_text='Fundación a la que representa (solo para representantes)'
    )
    imagen_usuario = models.ImageField(
        upload_to='usuarios/', blank=True, null=True, max_length=200,
        help_text='Imagen de perfil del usuario'
    )
    es_staff = models.BooleanField(default=False, help_text='Puede acceder al panel de administración')

    # NUEVOS CAMPOS PARA MAPA
    direccion = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text='Dirección completa del usuario'
    )

    lat = models.FloatField(
        blank=True, 
        null=True,
        help_text='Latitud para ubicación en mapa'
    )

    lng = models.FloatField(
        blank=True, 
        null=True,
        help_text='Longitud para ubicación en mapa'
    )

    mostrar_en_mapa = models.BooleanField(
        default=False,
        help_text='¿Permitir que mi ubicación sea visible en el mapa público?'
    )

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} ({dict(self.ROL_CHOICES).get(self.rol, self.rol)})"

    # Métodos para roles y permisos personalizados:
    def es_cliente(self): return self.rol == 'CLIENTE'
    def es_representante_fundacion(self): return self.rol == 'REPRESENTANTE_FUNDACION'
    def es_moderador(self): return self.rol == 'MODERADOR'
    def es_administrador(self): return self.rol == 'ADMINISTRADOR'
    def puede_gestionar_donaciones(self): 
        return self.es_representante_fundacion() and self.fundacion_asignada is not None
    def obtener_fundacion(self):
        return self.fundacion_asignada if self.es_representante_fundacion() else None
    
    def set_password(self, raw_password):
        """Hashea y asigna la contraseña de forma segura."""
        from django.contrib.auth.hashers import make_password
        self.contrasena = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica la contraseña contra el hash almacenado.
        Soporta hashes Django (con $) y legacy SHA256 hex.
        """
        import hashlib
        from django.contrib.auth.hashers import check_password as django_check
        if not self.contrasena:
            return False
        if '$' in self.contrasena:
            return django_check(raw_password, self.contrasena)
        return hashlib.sha256(raw_password.encode()).hexdigest() == self.contrasena
    
    def save(self, *args, **kwargs):
        if self.contrasena and '$' not in self.contrasena:
            from django.contrib.auth.hashers import make_password
            self.contrasena = make_password(self.contrasena)
        super().save(*args, **kwargs)

# ------------------- Fundacion ----------------------

class Fundacion(models.Model):
    id_fundacion = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    correo_contacto = models.CharField(max_length=120, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    imagen_fundacion = models.ImageField(upload_to='fundaciones/', blank=True, null=True, max_length=200, help_text='Imagen o logo de la fundación')
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    representante = models.OneToOneField(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='fundacion_representada')

    # NUEVOS CAMPOS PARA MAPA
    lat = models.FloatField(
        blank=True, 
        null=True,
        help_text='Latitud de la fundación (OBLIGATORIO para aparecer en mapa)'
    )

    lng = models.FloatField(
        blank=True, 
        null=True,
        help_text='Longitud de la fundación (OBLIGATORIO para aparecer en mapa)'
    )

    class Meta:
        db_table = 'fundacion'

    def __str__(self): return self.nombre

    def obtener_representantes(self): return self.representantes.all()
    def total_donaciones_recibidas(self):
        from .models import Transaccion
        return Transaccion.objects.filter(id_fundacion=self, id_tipo__nombre_tipo='Donación').count()

# ------------------- Tipo Transaccion ----------------------

class TipoTransaccion(models.Model):
    id_tipo = models.AutoField(primary_key=True)
    nombre_tipo = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'tipo_transaccion'

    def __str__(self): return self.nombre_tipo

# ------------------- Prenda ----------------------

class Prenda(models.Model):
    id_prenda = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(Usuario, models.DO_NOTHING)
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)
    talla = models.CharField(max_length=10, blank=True, null=True)
    fecha_publicacion = models.DateTimeField(default=timezone.now, blank=True, null=True)

    # Estados de publicación/negociación (PENDIENTE, DISPONIBLE, RESERVADA, EN_PROCESO_ENTREGA, COMPLETADA, etc.)
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('RESERVADA', 'Reservada'),
        ('EN_PROCESO_ENTREGA', 'En Proceso de Entrega'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('AGOTADA', 'Agotada'), # Opcional si manejas stock/cantidad
        # ...otros estados necesarios...
    ]
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='DISPONIBLE')
    
    DISPONIBILIDAD_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('EN_PROCESO', 'En Proceso'),
        ('INTERCAMBIADA', 'Intercambiada'),
        ('VENDIDA', 'Vendida'),
        ('DONADA', 'Donada'),
        ('NO_DISPONIBLE', 'No Disponible'),
    ]
    disponibilidad = models.CharField(max_length=20, choices=DISPONIBILIDAD_CHOICES, default='DISPONIBLE')
    
    cantidad = models.PositiveIntegerField(default=1, help_text="Cantidad disponible en stock") # Opcional
    
    imagen_prenda = models.ImageField(upload_to='prendas/', blank=True, null=True, max_length=200)

    class Meta:
        db_table = 'prenda'

    def marcar_como_reservada(self):
        self.estado = 'RESERVADA'
        self.save()
    def marcar_como_en_proceso(self):
        self.estado = 'EN_PROCESO_ENTREGA'
        self.disponibilidad = 'EN_PROCESO'
        self.save()
    def marcar_como_completada(self):
        self.estado = 'COMPLETADA'
        self.save()
    def marcar_como_cancelada(self):
        self.estado = 'CANCELADA'
        self.disponibilidad = 'DISPONIBLE'
        self.save()

    def __str__(self): return self.nombre
    def esta_disponible(self): return self.disponibilidad == 'DISPONIBLE' and self.estado == 'DISPONIBLE'
    def marcar_como_no_disponible(self, motivo='EN_PROCESO'):
        self.disponibilidad = motivo
        self.save()
    def marcar_como_disponible(self):
        self.disponibilidad = 'DISPONIBLE'
        self.save()

# ------------------- Transaccion ----------------------

class Transaccion(models.Model):
    id_transaccion = models.AutoField(primary_key=True)
    id_prenda = models.ForeignKey(Prenda, models.DO_NOTHING)
    id_tipo = models.ForeignKey(TipoTransaccion, models.DO_NOTHING)
    id_usuario_origen = models.ForeignKey(Usuario, models.DO_NOTHING, related_name='transaccion_id_usuario_origen_set')
    id_usuario_destino = models.ForeignKey(Usuario, models.DO_NOTHING, related_name='transaccion_id_usuario_destino_set', blank=True, null=True)
    id_fundacion = models.ForeignKey(Fundacion, models.DO_NOTHING, blank=True, null=True)
    id_campana = models.ForeignKey('CampanaFundacion', models.DO_NOTHING, blank=True, null=True)
    fecha_transaccion = models.DateTimeField(default=timezone.now, blank=True, null=True)
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ACEPTADA', 'Aceptada'),
        ('RESERVADA', 'Reservada'),
        ('EN_PROCESO', 'En Proceso de Entrega'),
        ('COMPLETADA', 'Completada'),
        ('RECHAZADA', 'Rechazada'),
        ('EN_DISPUTA', 'En Disputa'),
        ('CANCELADA', 'Cancelada'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    destino_final = models.CharField(max_length=300, blank=True, null=True, help_text='Destino final de la donación')
    fecha_entrega = models.DateTimeField(blank=True, null=True)

    # Nuevos campos para disputas
    en_disputa = models.BooleanField(default=False)
    razon_disputa = models.TextField(null=True, blank=True)
    reportado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='disputas_reportadas')
    fecha_disputa = models.DateTimeField(null=True, blank=True)

    # NUEVOS CAMPOS PARA LOGÍSTICA Y ENVÍOS
    direccion_retiro = models.CharField(
        max_length=300, 
        blank=True, 
        null=True,
        help_text='Dirección de retiro/origen para envío'
    )
    direccion_entrega = models.CharField(
        max_length=300, 
        blank=True, 
        null=True,
        help_text='Dirección de entrega/destino para envío'
    )
    peso_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text='Peso estimado de la prenda en kilogramos'
    )
    dimensiones = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Dimensiones del paquete (largo x ancho x alto en cm)'
    )
    codigo_seguimiento_envio = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Código de seguimiento del envío (Shipit u otro)'
    )
    costo_envio = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text='Costo del envío calculado'
    )
    courier = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text='Nombre del courier (ej: Chilexpress, Correos, etc.)'
    )

    class Meta:
        db_table = 'transaccion'

    def __str__(self):
        return f"{self.id_tipo.nombre_tipo} - {self.id_prenda.nombre}"
    def es_donacion(self): return self.id_tipo.nombre_tipo == 'Donación'
    def actualizar_disponibilidad_prenda(self):
        if self.estado == 'COMPLETADA':
            if self.id_tipo.nombre_tipo == 'Donación':
                self.id_prenda.marcar_como_no_disponible('DONADA')
            elif self.id_tipo.nombre_tipo == 'Venta':
                self.id_prenda.marcar_como_no_disponible('VENDIDA')
            elif self.id_tipo.nombre_tipo == 'Intercambio':
                self.id_prenda.marcar_como_no_disponible('INTERCAMBIADA')
        elif self.estado in ['PENDIENTE', 'EN_PROCESO']:
            self.id_prenda.marcar_como_no_disponible('EN_PROCESO')
        elif self.estado in ['RECHAZADA', 'CANCELADA']:
            self.id_prenda.marcar_como_disponible()

    def reservar(self):
        self.estado = 'RESERVADA'
        self.save()
        self.id_prenda.marcar_como_reservada()

    def marcar_en_proceso(self):
        self.estado = 'EN_PROCESO'
        self.save()
        self.id_prenda.marcar_como_en_proceso()

    def marcar_como_completada(self):
        self.estado = 'COMPLETADA'
        self.save()
        self.id_prenda.marcar_como_completada()

    def cancelar(self):
        self.estado = 'CANCELADA'
        self.save()
        self.id_prenda.marcar_como_cancelada()

    def puede_aceptar(self, usuario):
        """Verifica si el usuario puede aceptar esta transacción.
        - Donaciones: solo representante de la fundación asignada.
        - Intercambios/Ventas: solo el usuario destino.
        - Estado debe ser PENDIENTE o RESERVADA.
        """
        if self.estado not in ['PENDIENTE', 'RESERVADA']:
            return False
        if self.es_donacion():
            return (usuario.es_representante_fundacion() and 
                    usuario.fundacion_asignada == self.id_fundacion)
        if self.id_usuario_destino:
            return usuario.id_usuario == self.id_usuario_destino.id_usuario
        return False

    def puede_rechazar(self, usuario):
        """Verifica si el usuario puede rechazar esta transacción.
        - Donaciones: solo representante de la fundación.
        - Intercambios/Ventas: usuario destino siempre, origen solo en PENDIENTE.
        """
        if self.estado not in ['PENDIENTE', 'RESERVADA']:
            return False
        if self.es_donacion():
            return (usuario.es_representante_fundacion() and 
                    usuario.fundacion_asignada == self.id_fundacion)
        es_destino = (self.id_usuario_destino and 
                      usuario.id_usuario == self.id_usuario_destino.id_usuario)
        es_origen = usuario.id_usuario == self.id_usuario_origen.id_usuario
        return es_destino or (es_origen and self.estado == 'PENDIENTE')

    def puede_confirmar_entrega(self, usuario):
        """Verifica si el usuario puede confirmar entrega de la prenda.
        - Donaciones: representante de fundación en estado EN_PROCESO.
        - Intercambios/Ventas: usuario destino en estado EN_PROCESO.
        """
        if self.estado != 'EN_PROCESO':
            return False
        if self.es_donacion():
            return (usuario.es_representante_fundacion() and 
                    usuario.fundacion_asignada == self.id_fundacion)
        if self.id_usuario_destino:
            return usuario.id_usuario == self.id_usuario_destino.id_usuario
        return False

    def puede_reservar(self, usuario):
        """Verifica si el usuario puede reservar esta transacción.
        - Solo usuario destino (no es origen) en estado PENDIENTE.
        """
        if self.estado != 'PENDIENTE':
            return False
        es_destino = (self.id_usuario_destino and 
                      usuario.id_usuario == self.id_usuario_destino.id_usuario)
        es_origen = usuario.id_usuario == self.id_usuario_origen.id_usuario
        return es_destino and not es_origen

    def puede_modificar(self, usuario):
        """Verifica si el usuario puede modificar detalles de la transacción.
        - Usuario origen, admin/moderador, o representante en estado PENDIENTE.
        """
        if self.estado != 'PENDIENTE':
            return False
        es_origen = usuario.id_usuario == self.id_usuario_origen.id_usuario
        es_admin = usuario.es_administrador() or usuario.es_moderador()
        es_rep = (usuario.es_representante_fundacion() and 
                  usuario.fundacion_asignada == self.id_fundacion)
        return es_origen or es_admin or es_rep

# ------------------- Mensaje ----------------------

class Mensaje(models.Model):
    id_mensaje = models.AutoField(primary_key=True)
    id_emisor = models.ForeignKey(Usuario, models.DO_NOTHING, related_name='mensaje_id_emisor_set')
    id_receptor = models.ForeignKey(Usuario, models.DO_NOTHING, related_name='mensaje_id_receptor_set')
    contenido = models.CharField(max_length=500)
    fecha_envio = models.DateTimeField(default=timezone.now, blank=True, null=True)

    class Meta:
        db_table = 'mensaje'

    def __str__(self): return f"Mensaje de {self.id_emisor.nombre} a {self.id_receptor.nombre}"

# ------------------- Impacto Ambiental ----------------------

class ImpactoAmbiental(models.Model):
    id_impacto = models.AutoField(primary_key=True)
    id_prenda = models.ForeignKey(Prenda, models.DO_NOTHING)
    carbono_evitar_kg = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    energia_ahorrada_kwh = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    fecha_calculo = models.DateTimeField(default=timezone.now, blank=True, null=True)

    class Meta:
        db_table = 'impacto_ambiental'

    def __str__(self): return f"Impacto de {self.id_prenda.nombre}"

# ------------------- Logros ----------------------

class Logro(models.Model):
    id_logro = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('DONACION', 'Donación'),
        ('INTERCAMBIO', 'Intercambio'),
        ('VENTA', 'Venta'),
        ('IMPACTO', 'Impacto Ambiental'),
        ('COMUNIDAD', 'Comunidad'),
    ]
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=300)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    icono = models.CharField(max_length=50, help_text='Clase de ícono Bootstrap')
    requisito_valor = models.IntegerField(help_text='Valor necesario para desbloquear')
    codigo = models.CharField(max_length=50, unique=True, default="")
    class Meta: db_table = 'logro'
    def __str__(self): return self.nombre

class UsuarioLogro(models.Model):
    id_usuario_logro = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    logro = models.ForeignKey(Logro, on_delete=models.CASCADE)
    fecha_desbloqueo = models.DateTimeField(default=timezone.now)
    class Meta:
        db_table = 'usuario_logro'
        unique_together = ('usuario', 'logro')
    def __str__(self):
        return f"{self.usuario.nombre} - {self.logro.nombre}"

# ------------------- Campaña Fundación ----------------------

class CampanaFundacion(models.Model):
    id_campana = models.AutoField(primary_key=True)
    id_fundacion = models.ForeignKey(Fundacion, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    imagen_campana = models.ImageField(upload_to='campanas/', blank=True, null=True, max_length=200)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    objetivo_prendas = models.IntegerField(help_text='Meta de prendas a recolectar')
    activa = models.BooleanField(default=True)
    categorias_solicitadas = models.CharField(max_length=300, help_text='Categorías separadas por comas')

    class Meta:
        db_table = 'campana_fundacion'

    def __str__(self): return f"{self.nombre} - {self.id_fundacion.nombre}"

    def prendas_donadas(self):
        from .models import Transaccion
        return Transaccion.objects.filter(
            id_campana=self,
            estado='COMPLETADA',
            id_tipo__nombre_tipo='Donación'
        ).count()
    def porcentaje_completado(self):
        donadas = self.prendas_donadas()
        if self.objetivo_prendas > 0:
            return min(100, (donadas / self.objetivo_prendas) * 100)
        return 0
