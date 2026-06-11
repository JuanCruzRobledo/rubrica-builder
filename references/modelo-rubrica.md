# Modelo de Rúbrica V2 — Fuente de verdad

> Esta referencia replica el schema Pydantic real de
> `backend/app/schemas/rubrica.py` (`CriteriosStructure` y sus hijos).
> Si algún día este archivo y ese schema discrepan, **gana el schema**.
> No confíes en `docs/specs/Rubrica.md` (usa `nota_final`, mal) ni en la
> skill vieja `skills/rubricas/` (modelo V1 con `puntaje_maximo` por criterio
> y sin subcriterios). Ambos están desactualizados.

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
| `evidencias` | array[string] | ✅ | ≥1 evidencia, ninguna vacía |

> Las **evidencias** son el checklist verificable que usa la IA para corregir.
> Cada una debe ser una afirmación binaria comprobable mirando SOLO la entrega
> del alumno (ej: "El archivo `package.json` existe", "Se define la ruta `GET /productos`").
> Evitá evidencias subjetivas o que requieran info externa al código entregado.

> ⚠️ **Consecuencia de diseño (clave):** el subcriterio **NO tiene nota propia** —
> solo el criterio puntúa (`peso`). El subcriterio es un checklist de evidencias.
> Por eso, si un requisito necesita poder **descontarse por sí solo**, tiene que ser
> un **CRITERIO**, no un subcriterio. Ver "El principio que decide la granularidad"
> en `SKILL.md`.

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

## Reglas duras (si una falla, el backend rebota la rúbrica)

1. `puntaje_maximo` == 100.
2. **Σ de `peso` de todos los criterios == 100.** (la más rota en la práctica)
3. IDs únicos en cada nivel (criterios, subcriterios dentro de su criterio, penalizaciones, condiciones).
4. Cada ID respeta su patrón regex.
5. Cada criterio tiene ≥1 subcriterio; cada subcriterio ≥1 evidencia no vacía.
6. Rangos: `peso` 1–100, `descuento_porcentaje` 0–100, `nota_maxima` 0–100.

Validá siempre con `scripts/validar_rubrica.py` antes de entregar.
