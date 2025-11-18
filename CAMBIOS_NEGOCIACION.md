# 📋 Resumen de Cambios - Sistema de Negociación Pre-acuerdo

## 🎯 Objetivo Completado
✅ **Los usuarios ahora pueden contactarse para negociar ANTES de llegar a un acuerdo formal**
✅ **La prenda solo desaparece del listado público cuando se ACEPTA una propuesta**
✅ **Sistema de múltiples propuestas simultáneas para la misma prenda**

---

## 📝 Cambios en Views (`A_EcoPrenda/views.py`)

### 1. `comprar_prenda(request, id_prenda)` - MODIFICADO
**Cambio**: Ya no marca la prenda como `RESERVADA` automáticamente
```python
# ANTES:
transaccion = Transaccion.objects.create(...)
prenda.marcar_como_reservada()  # ❌ Quitar esto

# AHORA:
transaccion = Transaccion.objects.create(...)
# NO marca como RESERVADA
# La prenda permanece DISPONIBLE para negociación
```
**Efecto**: Comprador y vendedor pueden contactarse antes de comprometerse

---

### 2. `proponer_intercambio(request, id_prenda)` - MODIFICADO
**Cambio**: Ya no llama `transaccion.actualizar_disponibilidad_prenda()`
```python
# ANTES:
transaccion.actualizar_disponibilidad_prenda()  # ❌ Quitar esto

# AHORA:
# Prenda destino permanece DISPONIBLE
# Solo se reserva cuando destino ACEPTA
```
**Efecto**: Otros usuarios pueden contactar y proponer mientras se negocia

---

### 3. `donar_prenda(request, id_prenda)` - MODIFICADO (EXCEPCIÓN)
**Cambio**: SÍ marca como `RESERVADA` (caso especial)
```python
# Donaciones son diferentes: unilaterales, no negociables
prenda.marcar_como_reservada()  # ✅ Se mantiene
```
**Efecto**: Una prenda donada no puede ser donada a múltiples fundaciones

---

### 4. `actualizar_estado_transaccion(request, id_transaccion)` - COMPLETAMENTE REESCRITO
**Cambio Crítico**: Nuevo flujo de aceptación/rechazo

```python
# NUEVO FLUJO:
Si estado actual == 'PENDIENTE':
    Si nuevo_estado == 'ACEPTADA':
        ✅ Marcar prenda como RESERVADA (AQUÍ es donde se reserva)
        ✅ Mensaje: "Prenda reservada, envío iniciado"
    
    Si nuevo_estado == 'RECHAZADA':
        ✅ Prenda PERMANECE DISPONIBLE
        ✅ Mensaje: "Propuesta rechazada, otros pueden intentar"
```

**Efecto**: 
- El vendedor CONTROLA cuándo se compromete (acepta)
- El vendedor PUEDE rechazar y la prenda sigue siendo visible
- Otros compradores pueden hacer propuestas alternativas

---

## 🎨 Cambios en Templates

### `detalle_prenda.html` - MEJORADO
**Cambios**:
1. Nueva sección: **"Negociar & Comprar"**
2. Botón destacado: **"Abrir Conversación"** (contactar antes)
3. Información clara: "Puedes contactar al vendedor para negociar..."
4. Badge de estado con colores dinámicos:
   - 🟢 DISPONIBLE (verde)
   - 🟡 RESERVADA (amarillo)
   - 🔵 COMPLETADA (azul)

**Código**:
```html
<!-- Nuevo panel a la derecha -->
<h5><i class="bi bi-lightbulb"></i> Negociar & Comprar</h5>
<a href="{% url 'conversacion' prenda.id_usuario.id_usuario %}" class="btn btn-outline-secondary">
    <i class="bi bi-chat-dots"></i> Abrir Conversación
</a>
<button type="submit" class="btn btn-success">
    <i class="bi bi-cart-check"></i> Proponer Compra
</button>
```

---

### `mis_transacciones.html` - CORREGIDO
**Cambios**:
1. Comparaciones usan claves internas: `'PENDIENTE'`, `'ACEPTADA'`, `'RECHAZADA'`
2. Display usa `get_estado_display()` para etiquetas humanizadas
3. Form values son claves: `value="ACEPTADA"` (no `value="Aceptada"`)

**Antes vs Ahora**:
```html
<!-- ANTES (❌ NO funcionaba) -->
{% if trans.estado == 'Pendiente' %}
<input type="hidden" name="estado" value="Aceptada">

<!-- AHORA (✅ Funciona) -->
{% if trans.estado == 'PENDIENTE' %}
<input type="hidden" name="estado" value="ACEPTADA">
```

---

### `mis_prendas.html` - CORREGIDO
**Cambios**:
1. Eliminado HTML duplicado/mal formado
2. Comparaciones de estado arregladas
3. URLs actualizadas (`marcar-entregada`, `cancelar`)
4. Iconos mejorados en botones

---

### `lista_prendas.html` - MEJORADO
**Cambios**:
1. Estado badge usa `get_estado_display()` con colores dinámicos
2. Las prendas con propuestas PENDIENTE siguen siendo visibles

---

## 🔄 Flujo Completo Visualmente

```
USUARIO VE PRENDA (DISPONIBLE)
              ↓
    ┌─────────┼─────────┐
    ↓         ↓         ↓
  CONTACTAR  PROPONER  PROPONER
   (CHAT)    COMPRA    INTERCAMBIO
    ↓         ↓         ↓
    └─────────┼─────────┘
              ↓
    TRANSACCIÓN = PENDIENTE
    PRENDA = DISPONIBLE (¡Sin cambios!)
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
 ACEPTAR            RECHAZAR
    ↓                   ↓
PRENDA →           PRENDA →
RESERVADA          DISPONIBLE
   ↓                   ↓
ENVÍO               (Otros pueden
INICIA              proponer)
```

---

## 🔐 Estados y Disponibilidad

### Transacción
```
PENDIENTE     → Esperando decisión del vendedor
ACEPTADA      → Vendedor aceptó, envío iniciado
EN_PROCESO    → Enviado, esperando recepción
COMPLETADA    → Recibido y confirmado
RECHAZADA     → Vendedor rechazó, vuelve a DISPONIBLE
CANCELADA     → Cancelado por usuario
```

### Prenda
```
DISPONIBLE            → Visible en lista, aceptar nuevas propuestas
RESERVADA            → Prenda comprometida (no aceptar nuevas propuestas)
EN_PROCESO_ENTREGA   → En camino al comprador
COMPLETADA           → Transacción finalizada
```

---

## 📊 Matriz de Estados

| Transacción Estado | Prenda Estado | ¿Otra propuesta posible? | ¿Visible en lista? |
|--------------------|---------------|-------------------------|-------------------|
| PENDIENTE          | DISPONIBLE    | ✅ SÍ (múltiples)        | ✅ SÍ               |
| ACEPTADA           | RESERVADA     | ❌ NO                     | ❌ NO               |
| EN_PROCESO         | EN_PROCESO    | ❌ NO                     | ❌ NO               |
| COMPLETADA         | COMPLETADA    | ❌ NO                     | ❌ NO               |
| RECHAZADA          | DISPONIBLE    | ✅ SÍ (nuevas)           | ✅ SÍ               |

---

## 🎯 Ejemplo Real: Maria vende su camiseta

```
1. Maria publica camiseta → Estado: DISPONIBLE

2. Juan ve camiseta y:
   - Abre conversación: "Hola, ¿es XL?"
   - Propone compra → Transacción PENDIENTE, camiseta sigue DISPONIBLE

3. Mientras tanto, Pedro TAMBIÉN:
   - Propone compra → OTRA transacción PENDIENTE
   - Camiseta sigue DISPONIBLE

4. Maria ve 2 propuestas en "mis_transacciones":
   - Juan - 200$ - PENDIENTE
   - Pedro - 180$ - PENDIENTE

5. Maria contacta a Juan y negocia:
   - "Bajo a 190$, pero envío inmediato"
   - Juan acepta → Maria da clic en ACEPTAR
   - Transacción de Juan → ACEPTADA
   - Camiseta → RESERVADA
   - Transacción de Pedro → Sigue PENDIENTE

6. Maria rechaza propuesta de Pedro:
   - Camiseta vuelve a DISPONIBLE... PERO SOLO SI la de Juan no se completa
   - Si Juan paga y envía, la de Pedro desaparece
```

---

## 💬 Flujo de Mensajería

### Endpoints
```
GET  /conversacion/<id_usuario>/      → Ver chat con usuario
POST /enviar-mensaje/                  → Enviar mensaje
```

### Integración
- Botón **"Abrir Conversación"** disponible mientras prenda está DISPONIBLE
- Chat accesible antes de proponer (se recomienda)
- Chat accesible durante propuesta PENDIENTE (negociación)
- Chat accesible después de aceptar (coordinar envío)

---

## ⚠️ Cambios Técnicos Importantes

### Modelo Transaccion (NO cambios, solo uso diferente)
```python
# El modelo ya tenía estos estados, ahora se usan correctamente:
ESTADO_CHOICES = [
    ('PENDIENTE', 'Pendiente'),
    ('ACEPTADA', 'Aceptada'),
    ('EN_PROCESO', 'En Proceso'),
    ('COMPLETADA', 'Completada'),
    ('RECHAZADA', 'Rechazada'),
    ('CANCELADA', 'Cancelada'),
]
```

### URLs (algunas actualizadas en mis_transacciones.html)
```
{% if trans.estado == 'PENDIENTE' %}        ← Ahora en mayúsculas
<input type="hidden" name="estado" value="ACEPTADA">  ← Valores correctos
```

---

## 🧪 Cómo Probar

### Test 1: Propuesta Pendiente
```
1. Inicia sesión como USUARIO A
2. Publica una prenda
3. Inicia sesión como USUARIO B
4. Haz clic en "Proponer Compra"
5. Verifica: Prenda sigue en lista (DISPONIBLE)
6. Propón desde USUARIO C también (misma prenda)
7. Verifica: Ambas propuestas en mis_transacciones
```

### Test 2: Aceptar Propuesta
```
1. Como USUARIO A (vendedor), ve mis_transacciones
2. Haz clic en "Aceptar" para propuesta de USUARIO B
3. Verifica: Prenda cambia a RESERVADA
4. Verifica: Desaparece de lista pública
5. Verifica: Propuesta de USUARIO C aún muestra opciones
```

### Test 3: Rechazar Propuesta
```
1. Como USUARIO A, rechaza propuesta de USUARIO C
2. Verifica: Prenda vuelve a DISPONIBLE
3. Verifica: Otros usuarios pueden ver la prenda de nuevo
```

---

## 📚 Documentación

Ver archivo: `FLUJO_NEGOCIACION.md` para detalles completos del flujo de negociación.

---

## ✅ Checklist de Implementación

- [x] No marcar RESERVADA en `comprar_prenda`
- [x] No marcar RESERVADA en `proponer_intercambio`
- [x] SÍ marcar RESERVADA en `actualizar_estado_transaccion` (cuando ACEPTA)
- [x] Donar SÍ marca RESERVADA (excepción)
- [x] Corregir comparaciones en `mis_transacciones.html`
- [x] Corregir comparaciones en `mis_prendas.html`
- [x] Mejorar UX en `detalle_prenda.html`
- [x] Actualizar `lista_prendas.html` para colores dinámicos
- [x] Documentar flujo completo

---

**Estado**: ✅ COMPLETADO  
**Fecha**: 16 Nov 2024  
**Próximas Mejoras**: Notificaciones en tiempo real, expiración automática de propuestas
