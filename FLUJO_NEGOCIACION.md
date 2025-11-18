# 🤝 Flujo de Negociación en EcoPrenda

## Descripción General
Se implementó un sistema de negociación **antes de aceptar** una transacción, permitiendo que:
1. Los usuarios contacten al vendedor para negociar
2. La prenda se mantenga disponible mientras hay propuestas PENDIENTE
3. El vendedor acepte o rechace propuestas sin comprometerse inmediatamente

---

## Flujo Compra/Intercambio

```
┌─────────────────────────────────────────────────────────────────┐
│ USUARIO VE PRENDA EN LISTA (estado: DISPONIBLE)                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
       ┌───────────────┴──────────────────┬──────────────────┐
       │                                  │                  │
    CONTACTAR                      PROPONER COMPRA      PROPONER INTERCAMBIO
    (Chat)                         (POST)               (POST)
       │                                  │                  │
       └──────────────────────────────────┴──────────────────┘
                       │
    ┌─────────────────┴────────────────────────────┐
    │ TRANSACCIÓN CREADA (estado: PENDIENTE)       │
    │ ⚠️ PRENDA SIGUE DISPONIBLE                    │
    │ ✅ Otros pueden contactar/proponer también   │
    └────────────────────┬──────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
      VENDEDOR VE        │            TIEMPO
    EN MIS_TRANSACCIONES │            (se puede renegociar)
    (en "Recibidas")     │
         │               │
         │    NEGOCIACIÓN POR CHAT    │
         │               │               │
         ├───────────────┼───────────────┤
         │               │               │
      ACEPTAR        RECHAZAR        ESPERAR
       (POST)         (POST)         (Seguir PENDIENTE)
         │               │               │
         ▼               ▼               ▼
    ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
    │ ACEPTADA    │  │ RECHAZADA    │  │ PENDIENTE    │
    │ Prenda →    │  │ Prenda →     │  │ (sin cambios)│
    │ RESERVADA   │  │ DISPONIBLE   │  │              │
    │ ✅ Envío    │  │ (para otros) │  │              │
    │    inicia   │  │ ✅ Otros     │  │              │
    │             │  │    pueden    │  │              │
    │             │  │    intentar  │  │              │
    └─────────────┘  └──────────────┘  └──────────────┘
         │
      MARCAR ENTREGADA (comprador)
      ├─ Venta: marcar-entregada (prenda.id_transaccion)
      ├─ Intercambio: marcar-entregada (prenda.id_transaccion)
         │
      CONFIRMAR RECEPCIÓN (receptor)
         │
      COMPLETADA ✅
```

---

## Cambios Implementados

### 1. **Views**: `comprar_prenda()`, `proponer_intercambio()`
- **ANTES**: Llamaban a `prenda.marcar_como_reservada()` inmediatamente
- **AHORA**: NO marcan como reservada; la prenda permanece DISPONIBLE
- **Motivo**: Permitir negociación y múltiples propuestas

### 2. **View**: `actualizar_estado_transaccion()`
- **Lógica NEW**: 
  ```python
  Si estado actual == 'PENDIENTE':
    - Si nuevo_estado == 'ACEPTADA':
        → Marcar prenda como RESERVADA
        → Mensaje: "Prenda reservada, envío iniciado"
    - Si nuevo_estado == 'RECHAZADA':
        → Prenda sigue DISPONIBLE
        → Mensaje: "Otros pueden intentar"
  ```

### 3. **Donaciones** (excepción)
- Las donaciones SÍ se marcan como RESERVADAS inmediatamente
- **Motivo**: Son ofertas unilaterales, no negociables
- **Flujo**: Donante → Fundación (sin ida/vuelta)

### 4. **Template**: `detalle_prenda.html`
- Nuevo panel: **"Negociar & Comprar"**
- Botón destacado: **Abrir Conversación** (antes de proponer)
- Aclaración: "Puedes contactar al vendedor para negociar..."
- Estados con colores: DISPONIBLE (verde), RESERVADA (amarillo), COMPLETADA (azul)

### 5. **Template**: `mis_transacciones.html`
- Comparaciones de estado ahora usan claves internas (`PENDIENTE`, `ACEPTADA`, `RECHAZADA`)
- Hidden form values son las claves de estado (no labels humanizados)
- Labels se muestran con `get_estado_display()`

---

## Casos de Uso

### ✅ Caso 1: Negociación exitosa
1. Juan propone compra de una camiseta (PENDIENTE)
2. Camiseta sigue DISPONIBLE
3. Juan contacta a María (vendedora) para negociar el precio
4. María acepta
5. Camiseta pasa a RESERVADA → Juan paga → Envío
6. Camiseta COMPLETADA

### ✅ Caso 2: Múltiples propuestas
1. Camiseta recibe 3 propuestas (3 transacciones PENDIENTE)
2. María contacta a los 3 compradores
3. María acepta solo 1 → esa camiseta RESERVADA
4. María rechaza las otras 2 → camiseta sigue DISPONIBLE para ellos

### ✅ Caso 3: Cambio de opinión
1. Juan propone compra
2. Se da cuenta que su talla es XL, no M
3. Contacta a María sin formalizar
4. María rechaza o el tiempo pasa
5. Camiseta vuelve a estar completamente disponible

---

## URLs afectadas

```
POST /comprar/<id_prenda>/           → Proponer compra (crea PENDIENTE)
POST /proponer-intercambio/<id_prenda>/ → Proponer intercambio (crea PENDIENTE)
POST /donar/<id_prenda>/              → Donar (crea PENDIENTE + marca RESERVADA)

POST /actualizar-estado/<id_transaccion>/ → Aceptar/Rechazar (PENDIENTE → ACEPTADA/RECHAZADA)
POST /marcar-entregada/<id_transaccion>/ → Marcar entregada (ACEPTADA → EN_PROCESO)
POST /confirmar-recepcion/<id_transaccion>/ → Confirmar recepción (EN_PROCESO → COMPLETADA)
POST /cancelar/<id_transaccion>/    → Cancelar transacción

GET /conversacion/<id_usuario>/      → Chat entre usuarios
```

---

## Estados Transacción (modelo)

```python
ESTADO_CHOICES = [
    ('PENDIENTE', 'Pendiente'),         # Nueva propuesta, esperando aceptación
    ('ACEPTADA', 'Aceptada'),           # Vendedor aceptó, prenda RESERVADA
    ('EN_PROCESO', 'En Proceso'),       # Envío iniciado
    ('COMPLETADA', 'Completada'),       # Recibido y confirmado
    ('RECHAZADA', 'Rechazada'),         # Vendedor rechazó
    ('CANCELADA', 'Cancelada'),         # Usuario canceló manualmente
]
```

---

## Estados Prenda (modelo)

```python
ESTADO_CHOICES = [
    ('DISPONIBLE', 'Disponible'),       # A la venta/intercambio
    ('RESERVADA', 'Reservada'),         # En transacción aceptada
    ('EN_PROCESO_ENTREGA', 'En Proceso de Entrega'),
    ('COMPLETADA', 'Completada'),       # Transacción finalizada
    ('CANCELADA', 'Cancelada'),         # Cancelada/vuelta a disponible
]

DISPONIBILIDAD_CHOICES = [
    ('DISPONIBLE', 'Disponible'),       # Público puede verla
    ('NO_DISPONIBLE', 'No disponible'), # Oculta (no en lista pública)
]
```

---

## Mensajes al usuario

| Acción | Antes | Ahora |
|--------|-------|-------|
| Proponer compra | "Solicitud enviada" | "Solicitud enviada. El vendedor puede aceptar o rechazar **después de contactarte**" |
| Proponer intercambio | "Intercambio propuesto" | "Intercambio propuesto. El otro usuario puede aceptar o rechazar **después de contactarte**" |
| Aceptar propuesta | N/A | "✅ Prenda reservada, envío iniciado" |
| Rechazar propuesta | N/A | "Propuesta rechazada. Prenda sigue disponible" |

---

## Próximas Mejoras (Opcional)

1. **Notificaciones en tiempo real**: Avisar al comprador cuando el vendedor acepta/rechaza
2. **Expiración automática**: Transacciones PENDIENTE > 7 días → auto-cancelar
3. **Rating después de negociación**: Calificar la experiencia con el comprador/vendedor
4. **Historial de negociación**: Ver todas las propuestas rechazadas de una prenda
5. **Contraprouesta**: Comprador sugiere otro precio, vendedor puede contraproponer

---

## Pruebas Recomendadas

```
✓ Crear propuesta → Prenda sigue DISPONIBLE
✓ Contactar mientras PENDIENTE → Chat funciona
✓ Aceptar propuesta → Prenda RESERVADA
✓ Rechazar propuesta → Prenda vuelve DISPONIBLE
✓ Cancelar transacción → Prenda vuelve DISPONIBLE
✓ Donar → Prenda RESERVADA inmediatamente
```

---

**Versión**: 1.0  
**Fecha**: 16 Nov 2024  
**Estado**: ✅ Implementado
