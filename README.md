# Rúbrica Builder

> Skill de [Claude Code](https://claude.com/claude-code) para **curar consignas, y crear, auditar y testear** rúbricas de evaluación autosuficientes del sistema **Active-IA** (corrección automática de TPs con IA).

Una rúbrica no sirve solo para verse prolija: tiene que ser **autosuficiente**. Cuando el sistema corrige, el modelo ve únicamente la rúbrica y la entrega del alumno — nunca la consigna original. Si un requisito no quedó escrito en la rúbrica, no se evalúa. Esta skill se asegura de que eso no pase.

Y un segundo pilar, igual de importante: **el puntaje vive en el criterio** (`peso`); el subcriterio no puntúa, es checklist. Por eso, si un requisito necesita poder **descontarse por sí solo**, va como criterio propio — no enterrado en un subcriterio sin palanca de nota. La skill aplica ese **test de granularidad** al crear y al auditar, para que la corrección sea **determinista** (que el mismo trabajo no saque notas distintas según el modelo).

## ✨ Qué hace

| Modo | Para qué | Entrada |
|------|----------|---------|
| **CURAR** | Detecta requisitos de la consigna que rompen el flujo de corrección de la IA (links, videos, imágenes en TP de código, deploy, código+PDF juntos) y los adapta a un solo flujo, los deriva a corrección manual o los saca de la rúbrica — reescribiendo la consigna sin perder la intención | la consigna |
| **CREAR** | Traduce una consigna en una rúbrica completa y válida | la consigna |
| **AUDITAR** | Revisa una rúbrica existente: detecta contradicciones, omisiones e invenciones, y reajusta pesos a 100 | consigna + rúbrica |
| **TEST** | Simula la corrección real (consolidación + prompt del workflow) localmente con el CLI de Claude, para ver qué nota y feedback produce antes de subirla | rúbrica + entrega |

Incluye un **validador** que replica las reglas del backend real: si pasa, el sistema acepta la rúbrica; si falla, te dice exactamente qué corregir.

## 📋 Requisitos

- **Python 3.10+** (solo librería estándar, sin dependencias externas).
- Para el modo TEST: el **CLI de Claude Code** (`claude`) disponible en el `PATH`.

## 🚀 Instalación

```bash
npx skills add https://github.com/JuanCruzRobledo/rubrica-builder
```

La skill queda disponible para tu agente. Se carga automáticamente cuando le pidas crear, auditar o probar una rúbrica.

## 🛠️ Uso

### CURAR, CREAR y AUDITAR (dentro de Claude Code)

Solo describí lo que necesitás y pasá el material; la skill se activa automáticamente:

- *"Revisá si esta consigna se puede corregir con la IA"* / *"curá este TP"* + la consigna → **CURAR**
- *"Armá la rúbrica de evaluación para este TP"* + la consigna → **CREAR**
- *"Revisá si esta rúbrica cubre todo lo que pide el parcial"* + consigna + rúbrica → **AUDITAR**

**CURAR** corre antes de CREAR: detecta los puntos de la consigna que rompen el flujo de corrección (un link de repo, una imagen en un TP de código, un video, código + informe PDF juntos), te propone para cada uno **adaptarlo** a un solo flujo (ej: *"adjuntá una imagen de la salida"* → *"imprimí la salida por pantalla"*), **dejarlo para corrección manual** o **sacarlo de la rúbrica** —preguntándote con una recomendación—, y te devuelve la **consigna reescrita** lista para CREAR.

La skill entrega el JSON listo para el botón **"Cargar criterios"** de Active-IA, más los campos (`tipo`, `numero`, `anio`) para completar en el formulario.

### Validar una rúbrica

```bash
python scripts/validar_rubrica.py mi-rubrica.json
```

### TEST — simular la corrección

```bash
python scripts/simular_correccion.py \
  --rubrica examples/rubrica-tp-cli.json \
  --entrega examples/entrega-demo \
  --materia "Programación I" \
  --alumno  "Alumno Demo" \
  --modo solo_codigo
```

Esto consolida la entrega, arma el prompt de corrección con la rúbrica completa, dispara `claude -p` y muestra nota + feedback por criterio, validando la respuesta contra la rúbrica. Agregá `--no-run` para solo generar el material sin ejecutar el modelo.

## 📂 Estructura

```
rubrica-builder/
├── SKILL.md                       # definición de la skill (4 modos)
├── scripts/
│   ├── validar_rubrica.py         # valida la estructura V2 (espejo del backend)
│   └── simular_correccion.py      # modo TEST: corrección local con claude
├── references/
│   ├── modelo-rubrica.md          # modelo de rúbrica V2 (fuente de verdad)
│   └── limites-corrector.md       # qué puede y qué NO evaluar la IA (modo CURAR)
├── assets/
│   └── ejemplo-rubrica.json       # rúbrica V2 completa de ejemplo
└── examples/
    ├── rubrica-tp-cli.json        # rúbrica de ejemplo para el modo TEST
    └── entrega-demo/              # entrega de alumno de ejemplo
```

## 📐 Modelo de rúbrica

El esquema completo (criterios, subcriterios, evidencias, penalizaciones, condiciones de desaprobación y reglas de validación) está documentado en [`references/modelo-rubrica.md`](references/modelo-rubrica.md).

## 📄 Licencia

[Apache-2.0](LICENSE) © 2026 Juan Cruz Robledo
