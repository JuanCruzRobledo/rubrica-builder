# Modelo de Rúbrica (v1 y v2) — Fuente de verdad

> Esta referencia replica el schema Pydantic real de
> `backend/app/schemas/rubrica.py` (`CriteriosStructure` y sus hijos).
> Si algún día este archivo y ese schema discrepan, **gana el schema**.
> No confíes en `docs/specs/Rubrica.md` (usa `nota_final`, mal) ni en la
> skill vieja `skills/rubricas/` (modelo con `puntaje_maximo` por criterio
> y sin subcriterios — un esquema *distinto y ya muerto*, no confundirlo con
> el "v1" de este documento). Ambos están desactualizados.
>
> **v1 vs v2 (ojo con el nombre):** el modelo de Active-IA tiene dos
> versiones, ambas vivas. **v1** es el esquema que esta skill documentaba
> hasta ahora: subcriterios **sin** `peso` propio (puro checklist). **v2**
> es el modelo nuevo: subcriterios **con** `peso` propio que debe sumar
> exacto al `peso` del criterio. Esta skill genera **v2 por defecto** y
> sigue soportando v1 para rúbricas ya cargadas. Ninguna de las dos versiones
> tiene relación con el modelo viejo de `skills/rubricas/` mencionado arriba.

## Qué se pega y qué se completa aparte

El botón **"Cargar criterios"** (modo JSON del editor de rúbricas) importa
SOLO el objeto `CriteriosStructure`. Los campos de nivel rúbrica
(`materia_id`, `tipo`, `numero`, `anio`) se completan en el formulario, no en el JSON.

- **Se pega como JSON** → `titulo`, `descripcion`, `puntaje_maximo`, `metadata`, `criterios`, `penalizaciones`, `condiciones_desaprobacion`.
- **Se tipea en el form** → `tipo`, `numero`, `anio` (y `materia_id`, que es contexto del usuario).

## Estructura completa (`CriteriosStructure`)

| Campo | Tipo | Obligatorio | Regla |
|-------|------|-------------|-------|
| `titulo` | string | ✅ | 1–200 chars |
| `descripcion` | string | ✅ | ≥1 char, sin tope superior |
| `puntaje_maximo` | int | — (default 100) | **debe ser exactamente 100** |
| `metadata` | object | — (default `{}`) | **flexible**: cualquier clave/valor |
| `criterios` | array | ✅ | ≥1; **Σ `peso` == 100** |
| `penalizaciones` | array | — (default `[]`) | descuentos opcionales |
| `condiciones_desaprobacion` | array | — (default `[]`) | techos de nota automáticos |

### `criterios[]` — Criterio

| Campo | Tipo | Obligatorio | Regla |
|-------|------|-------------|-------|
| `id` | string | ✅ | patrón `^[A-Z0-9]+$` (ej: `C1`, `C2`), único, ≤20 chars |
| `nombre` | string | ✅ | 1–100 chars |
| `descripcion` | string | ✅ | 1–500 chars |
| `peso` | int | ✅ | 1–100; **la suma de todos = 100** |
| `instrucciones_puntuacion` | string | ❌ opcional | ≤2000 chars — ÚNICO campo opcional del criterio |
| `subcriterios` | array | ✅ | ≥1 |

### `subcriterios[]` — Subcriterio

| Campo | Tipo | Obligatorio | Regla |
|-------|------|-------------|-------|
| `id` | string | ✅ | patrón `^[A-Z0-9]+\.[0-9]+$` (ej: `C1.1`, `C2.3`), único dentro del criterio, ≤20 chars |
| `descripcion` | string | ✅ | 1–500 chars |
| `peso` | int | ✅ en v2 / ❌ en v1 | 1–100; la suma de los subcriterios de un criterio == `peso` de ese criterio (solo v2) |
| `evidencias` | array[string] | ✅ | ≥1 evidencia, ninguna vacía |

> Las **evidencias** son el checklist verificable que usa la IA para corregir.
> Cada una debe ser una afirmación binaria comprobable mirando SOLO la entrega
> del alumno (ej: "El archivo `package.json` existe", "Se define la ruta `GET /productos`").
> Evitá evidencias subjetivas o que requieran info externa al código entregado.

> ⚠️ **v1 — el subcriterio NO tiene nota propia:** solo el criterio puntúa
> (`peso`). El subcriterio es puro checklist de evidencias; la IA reparte el
> puntaje del criterio entre sus subcriterios implícitamente. Este es el
> comportamiento de las rúbricas ya cargadas que esta skill sigue soportando.

> ✅ **v2 — el subcriterio también puntúa:** cada subcriterio gana un `peso`
> propio (puntos absolutos), y **la suma de los `peso` de los subcriterios de
> un criterio debe ser exactamente igual al `peso` de ese criterio** — el
> mismo patrón que ya existía un nivel arriba (Σ `peso` de criterios == 100),
> replicado un nivel abajo. La corrección v2 devuelve, además de la nota por
> criterio, un desglose `subcriterios_evaluados` (ver más abajo). Esta skill
> genera v2 por defecto — ver "El principio que decide la granularidad" en
> `SKILL.md` para cuándo promover un requisito a criterio propio vs. dejarlo
> como subcriterio con `peso`.

**Ejemplo de un criterio v2 completo** (subcriterios con `peso` sumando exacto
al del criterio):

```json
{
  "id": "C2",
  "nombre": "Endpoints CRUD",
  "descripcion": "Implementación completa de Create, Read, Update y Delete sobre productos.",
  "peso": 25,
  "instrucciones_puntuacion": "Descontar si falta validación de entrada o manejo de errores.",
  "subcriterios": [
    {
      "id": "C2.1",
      "descripcion": "POST /productos crea un producto y devuelve 201.",
      "peso": 10,
      "evidencias": [
        "Existe la ruta POST /productos",
        "El handler persiste el producto",
        "Responde con status 201 ante éxito"
      ]
    },
    {
      "id": "C2.2",
      "descripcion": "GET /productos y GET /productos/:id devuelven datos correctamente.",
      "peso": 10,
      "evidencias": [
        "Existe la ruta GET /productos que lista productos",
        "Existe la ruta GET /productos/:id que devuelve uno"
      ]
    },
    {
      "id": "C2.3",
      "descripcion": "PUT y DELETE sobre /productos/:id funcionan.",
      "peso": 5,
      "evidencias": [
        "Existe la ruta PUT /productos/:id que actualiza",
        "Existe la ruta DELETE /productos/:id que elimina"
      ]
    }
  ]
}
```

`10 + 10 + 5 = 25 = peso del criterio C2`.

**Reparto por defecto cuando no hay ponderación clara en la consigna
(método del resto mayor / Hamilton):**

```
base  = floor(peso_criterio / n)
resto = peso_criterio - base * n
```

Los primeros `resto` subcriterios (en orden) reciben `base + 1`; el resto
recibe `base`. Ejemplo: criterio con `peso: 25` y `n=3` subcriterios →
`base = 8`, `resto = 1` → reparto `9, 8, 8` (suma 25). **Borde:** si
`peso_criterio < n`, el validador reporta el desbalance en vez de repartir
en 0 silenciosamente — hay que ajustar a mano (juntar subcriterios o subir
el peso del criterio).

**Corrección v2 — desglose por subcriterio.** Cada criterio evaluado trae
`subcriterios_evaluados`, y la suma de sus `puntaje_obtenido` debe ser igual
al `puntaje_obtenido` del criterio (los subcriterios desglosan esa suma, no
cambian el cálculo de la nota total — la nota final sigue siendo la suma de
`puntaje_obtenido` de los **criterios**):

```json
{
  "id": "C2",
  "puntaje_obtenido": 23,
  "puntaje_maximo": 25,
  "estado": "OK",
  "feedback": "...",
  "subcriterios_evaluados": [
    { "id": "C2.1", "puntaje_obtenido": 10, "puntaje_maximo": 10, "estado": "OK",      "feedback": "..." },
    { "id": "C2.2", "puntaje_obtenido": 8,  "puntaje_maximo": 10, "estado": "WARNING", "feedback": "..." },
    { "id": "C2.3", "puntaje_obtenido": 5,  "puntaje_maximo": 5,  "estado": "OK",      "feedback": "..." }
  ]
}
```

### `penalizaciones[]` — Penalización (opcional)

| Campo | Tipo | Obligatorio | Regla |
|-------|------|-------------|-------|
| `id` | string | ✅ | patrón `^P[0-9]+$` (ej: `P1`), único, ≤20 chars |
| `descripcion` | string | ✅ | 1–500 chars |
| `descuento_porcentaje` | int | ✅ | 0–100 |

### `condiciones_desaprobacion[]` — Condición (opcional)

| Campo | Tipo | Obligatorio | Regla |
|-------|------|-------------|-------|
| `id` | string | ✅ | patrón `^CD[0-9]+$` (ej: `CD1`), único, ≤20 chars |
| `condicion` | string | ✅ | 1–500 chars |
| `nota_maxima` | int | ✅ | 0–100 — techo de nota si se cumple la condición |

> ⚠️ El campo es **`nota_maxima`**, NO `nota_final`. La doc vieja se equivoca.
> Semántica: si la condición se cumple, la nota final NO puede superar este techo
> (ej: plagio → `nota_maxima: 0`; falta requisito troncal → `nota_maxima: 30`).

## Campos de nivel rúbrica (se tipean en el form, fuera del JSON)

| Campo | Tipo | Valores |
|-------|------|---------|
| `tipo` | enum | `TP`, `PARCIAL_1`, `PARCIAL_2`, `RECUPERATORIO_1`, `RECUPERATORIO_2`, `FINAL`, `GLOBAL` |
| `numero` | int | ≥1 (ej: TP **2** → `numero: 2`) |
| `anio` | int | 2020–2100 |
| `materia_id` | int | contexto del usuario — la skill NO lo decide |
| `schema_version` | int | `1` (default) o `2`. Ver nota abajo — **la skill nunca lo escribe en el JSON**. |

> ⚠️ **`schema_version` NO es un campo de `CriteriosStructure`.** Está
> declarado en `RubricaCreate` (default `1`), `RubricaUpdate` (`int | None`)
> y `RubricaResponse`/`RubricaListItem` — es hermano de `criterios_json`,
> igual que `tipo`/`numero`/`anio`. El objeto que se pega en "Cargar
> criterios" **no tiene ese campo**. El frontend de Active-IA lo infiere de
> forma **presence-based**: si algún subcriterio de la rúbrica trae `peso`,
> lo guarda como `schema_version=2`. **Conclusión operativa: la skill nunca
> mete `schema_version` dentro del JSON de criterios — lo único que hace
> falta para producir v2 es poner `peso` en cada subcriterio.**

## Reglas duras (si una falla, el backend rebota la rúbrica)

1. `puntaje_maximo` == 100.
2. **Σ de `peso` de todos los criterios == 100.** (la más rota en la práctica)
3. IDs únicos en cada nivel (criterios, subcriterios dentro de su criterio, penalizaciones, condiciones).
4. Cada ID respeta su patrón regex.
5. Cada criterio tiene ≥1 subcriterio; cada subcriterio ≥1 evidencia no vacía.
6. Rangos: `peso` 1–100, `descuento_porcentaje` 0–100, `nota_maxima` 0–100.
7. **(Solo v2, es decir: si algún subcriterio trae `peso`)** Cada subcriterio
   tiene `peso` (1–100) y la suma de los `peso` de los subcriterios de un
   criterio == `peso` de ese criterio. En v1 esta regla no aplica — los
   subcriterios no llevan `peso` y no se exige.

Validá siempre con `scripts/validar_rubrica.py` antes de entregar.
