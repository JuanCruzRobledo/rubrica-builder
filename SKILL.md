---
name: rubrica-builder
description: >-
  Crea y audita rúbricas de evaluación autosuficientes para Active-IA a partir
  de la consigna de cualquier entrega (TP, parcial, recuperatorio, final o
  global). En modo CREAR genera el JSON de criterios listo para el botón
  "Cargar criterios"; en modo AUDITAR recibe consigna + rúbrica existente y la
  corrige detectando contradicciones, omisiones e invenciones, reajustando
  pesos a 100. En modo TEST simula la corrección real (consolidación + prompt
  del workflow N8N→Gemini) localmente con el CLI de Claude, para ver qué nota y
  feedback produce la rúbrica sobre una entrega antes de subirla. Usá esta skill
  SIEMPRE que el usuario quiera armar, generar, diseñar, revisar, auditar,
  validar o PROBAR/TESTEAR una rúbrica o sus criterios de evaluación —aunque no
  diga la palabra "rúbrica" explícitamente (ej: "armá los criterios para este
  TP", "revisá si esta evaluación cubre todo lo que pide el parcial", "esta
  rúbrica está bien?", "probá cómo corrige esta rúbrica con esta entrega").
  NO usar para corregir entregas reales de alumnos en producción (eso es la
  skill `corregir`); el modo TEST es solo un ensayo local.
---

# Rúbrica Builder — crear y auditar rúbricas autosuficientes

Construís el instrumento con el que después se corrige. La meta no es una rúbrica
"linda": es una rúbrica **autosuficiente**. ¿Por qué importa tanto? Porque cuando
el sistema corrige, la IA ve SOLO dos cosas: **la rúbrica y la entrega del alumno**.
Nunca vuelve a mirar la consigna. Si un requisito del TP no quedó escrito en la
rúbrica, sencillamente NO se evalúa. La rúbrica es el único puente entre lo que el
profesor pidió y lo que la IA corrige.

Por eso toda la skill gira alrededor de una sola pregunta: **¿se puede corregir
esta entrega con esta rúbrica, sin tener la consigna a mano?** Si la respuesta es
no, la rúbrica está incompleta.

## Antes de empezar: leé el modelo

Leé `references/modelo-rubrica.md`. Es la fuente de verdad del esquema V2 (replica
el Pydantic real). Tené presente las tres trampas del repo:
- `docs/specs/Rubrica.md` usa `nota_final` → **mal**, es `nota_maxima`.
- la skill vieja `skills/rubricas/` usa `puntaje_maximo` por criterio y no tiene
  subcriterios → **modelo V1 muerto, ignorala**.
- el peso del criterio es `peso` (no `puntaje_maximo`), y la suma debe dar 100.

## Inputs que necesitás

| Modo | Necesitás |
|------|-----------|
| **CREAR** | La **consigna** completa de la entrega (texto, PDF, imágenes, tablas). |
| **AUDITAR** | La **consigna** + la **rúbrica existente** (JSON) a revisar. |
| **TEST** | La **rúbrica** (JSON) + una **entrega** de alumno (archivo, carpeta, .zip o .txt). |

Si falta la consigna, no inventes: pedila. Sin consigna no hay forma de saber qué
debe evaluar la rúbrica, y una rúbrica adivinada es exactamente el problema que
esta skill viene a resolver.

Si la consigna trae **imágenes, tablas, diagramas o esquemas** relevantes para la
evaluación, traducilos a texto dentro de la rúbrica (en la `descripcion` del
criterio o en las `evidencias`). La IA correctora no va a ver esa imagen — solo lee
la rúbrica. Lo que no esté en texto, no existe.

## Detectar el modo

- Solo consigna → **CREAR**.
- Consigna + un JSON de rúbrica → **AUDITAR**.
- Rúbrica + una entrega de alumno (probar/testear) → **TEST**.
- Ante la duda, preguntá cuál de los tres quiere.

---

## Modo CREAR

Objetivo: traducir la consigna en una rúbrica completa y autosuficiente.

1. **Leé la consigna entera y extraé requisitos.** Listá TODO lo evaluable:
   funcionalidades pedidas, restricciones técnicas (lenguaje, framework, versiones),
   condiciones de entrega (repo público, formato, deadline si afecta nota),
   validaciones exigidas, estructura obligatoria, lo que está prohibido. Cada
   requisito explícito del TP tiene que terminar reflejado en algún criterio o
   evidencia. Anclá todo en el texto: si no está en la consigna, no entra.

2. **Agrupá en criterios** (apuntá a 3–8). Cada criterio es una dimensión coherente
   (ej: "Endpoints CRUD", "Validaciones", "Documentación"). Asigná `peso` según la
   importancia que la consigna le da a cada cosa — más peso a lo troncal. La suma
   debe dar **exactamente 100**.

3. **Bajá cada criterio a subcriterios con evidencias.** Las evidencias son el
   corazón de la corrección: afirmaciones binarias, verificables mirando SOLO la
   entrega. "Existe la ruta `POST /productos`" es buena evidencia; "el código está
   bien escrito" no lo es (subjetiva, no verificable). Cada subcriterio necesita
   ≥1 evidencia.

4. **Penalizaciones y condiciones de desaprobación.** Si la consigna establece
   castigos (repo privado, no compila) o reglas que tumban la nota (plagio, falta un
   requisito troncal), modelalas. `penalizaciones` descuentan un %; las
   `condiciones_desaprobacion` ponen un techo (`nota_maxima`). Si la consigna no dice
   nada de esto, dejalos como `[]` — no inventes castigos que el profesor no pidió.

5. **Validá** con el script (ver "Validación obligatoria").

6. **Entregá** en el formato de salida de abajo.

---

## Modo AUDITAR

Acá sos un profesor experto en evaluación haciendo análisis crítico. Tenés la
consigna y un borrador de rúbrica. Tu trabajo es dejar la rúbrica fiel, estricta y
completa respecto del TP, y autosuficiente para corregir. Revisá en este orden:

1. **Contradicciones.** Puntos donde la rúbrica choca con la consigna. Ejemplo
   clásico: el TP exige eliminar/no usar algo y la rúbrica lo da por opcional o
   premia dejarlo. Corregí para que la rúbrica diga lo mismo que el TP.

2. **Omisiones.** Requisitos explícitos e importantes del TP que la rúbrica no
   evalúa: condiciones de entrega, validaciones específicas, restricciones técnicas,
   estructura obligatoria, ejecución. Agregalos como criterios, subcriterios o
   evidencias. Esta es la falla más grave: lo omitido nunca se corrige.

3. **Invenciones.** Criterios, concesiones o reglas que la rúbrica trae pero el TP
   no respalda en ningún lado. Sacalos. La rúbrica no puede ser más blanda ni más
   exigente que la consigna; debe ser su espejo fiel.

4. **Elementos visuales.** Si el TP tiene imágenes/tablas/esquemas que importan para
   evaluar y la rúbrica no los refleja en texto, incorporalos.

5. **Ajuste de pesos.** Si agregaste o sacaste criterios, recalculá los `peso` para
   que la suma vuelva a ser exactamente 100. Respetá la importancia relativa que da
   la consigna.

6. **Validá** con el script.

7. **Entregá** con el formato de salida (incluyendo el resumen de hallazgos).

---

## Modo TEST — simular la corrección

Una rúbrica válida no garantiza una rúbrica que corrija BIEN. El modo TEST cierra
ese hueco: corre una corrección real sobre una entrega concreta y te muestra nota +
feedback, para que veas si la rúbrica discrimina lo que tiene que discriminar antes
de subirla.

Replica el pipeline del sistema (consolidación del código + prompt de corrección),
pero dispara la corrección con el CLI de Claude en vez de N8N→Gemini. Claude actúa
como reemplazo del modelo de producción; los resultados son indicativos (otro
modelo), no idénticos al puntaje final que dará Gemini, pero sirven para detectar
problemas de la rúbrica.

```bash
python scripts/simular_correccion.py \
  --rubrica <rubrica.json> \
  --entrega <archivo|carpeta|.zip|.txt> \
  --materia "Nombre de la materia" \
  --alumno  "Nombre del alumno" \
  --modo solo_codigo            # o web_completo | proyecto_completo | personalizado
```

- `--no-run` arma el material y te imprime el comando, sin ejecutar claude (útil para
  inspeccionar el `prompt_correccion.txt` que recibirá el modelo).
- `--tipo TP` si la rúbrica es un `CriteriosStructure` sin campo `tipo`.
- `--ext ".ipynb,.sql"` para `--modo personalizado`.
- Guarda `prompt_correccion.txt` (material exacto) y `correccion.json` (resultado).

**Cómo leer el resultado.** El script valida la corrección contra la rúbrica y avisa
si: un criterio no fue evaluado, un puntaje supera su peso, la suma no cierra, o se
aplicó una penalización/condición inexistente. Pero lo importante es tu juicio:
¿la nota refleja la calidad real de la entrega?, ¿el feedback cita evidencias
concretas?, ¿algún criterio quedó ambiguo y el modelo dudó? Si algo no cierra, suele
ser la rúbrica la que hay que mejorar (descripciones vagas, evidencias no
verificables, pesos mal repartidos) — volvé a CREAR/AUDITAR y re-testeá.

### Qué consume el corrector (importante para diseñar la rúbrica)

La corrección usa la rúbrica **COMPLETA**: por cada criterio manda `id`, `nombre`,
`peso`, `descripcion`, `instrucciones_puntuacion` y **subcriterios con sus
evidencias**, más las `penalizaciones`, las `condiciones_desaprobacion` y la
`metadata`. Por eso las evidencias importan: son el checklist que el modelo verifica.

Recomendación de robustez: redactá la `descripcion` de cada criterio de forma
autosuficiente —que resuma lo que sus evidencias verifican—, así la corrección
funciona bien aun si una integración llegara a enviar menos contexto del esperado.

---

## Validación obligatoria

Antes de entregar cualquier rúbrica, guardá el JSON y corré:

```bash
python scripts/validar_rubrica.py <ruta_al_json>
```

(o `python scripts/validar_rubrica.py -` para leerlo por stdin)

El script replica las reglas del backend real: si pasa, el sistema acepta la
rúbrica; si falla, te dice exactamente qué corregir (suma de pesos, IDs, patrones,
evidencias vacías, `nota_final` vs `nota_maxima`, etc.). **No entregues una rúbrica
sin que el validador la dé por buena.** Si falla, arreglá y volvé a correrlo. Es
barato y te ahorra el rebote del backend.

## Formato de salida

ALWAYS entregá en este orden:

**1. (Solo en AUDITAR) Resumen de hallazgos** — breve, antes del JSON:
```
## Hallazgos
- Contradicciones: <qué y dónde, o "ninguna">
- Omisiones: <qué requisitos faltaban, o "ninguna">
- Invenciones: <qué se quitó, o "ninguna">
- Ajuste de pesos: <cómo quedó el reparto>
```

**2. El JSON de `CriteriosStructure`** — en un bloque ```json, listo para pegar en
el botón "Cargar criterios". Contiene exactamente: `titulo`, `descripcion`,
`puntaje_maximo`, `metadata`, `criterios`, `penalizaciones`,
`condiciones_desaprobacion`. Nada más.

**3. Campos para el formulario** — los que NO van en el JSON y se tipean aparte:
```
Para completar en el formulario de la rúbrica:
- tipo: <TP | PARCIAL_1 | ... según la consigna>
- numero: <ej: 2 para el TP2>
- anio: <año académico>
(materia_id lo elegís vos según la materia)
```

**4. Confirmación del validador** — pegá la línea de "✅ RÚBRICA VÁLIDA".

Mirá `assets/ejemplo-rubrica.json` como molde de una rúbrica V2 completa y válida.

## Errores que arruinan una rúbrica (evitalos)

- Pesos que no suman 100 — el error más común; el validador lo caza, pero pensalo
  desde el reparto.
- Evidencias subjetivas o que piden info fuera de la entrega ("está prolijo").
- Inventar penalizaciones/condiciones que la consigna no menciona.
- Dejar requisitos del TP sin ningún criterio que los cubra.
- Usar `nota_final` en vez de `nota_maxima`, o `puntaje_maximo` por criterio en vez
  de `peso` (eso es el modelo V1 muerto).
- Meter `materia_id`/`tipo`/`numero`/`anio` dentro del JSON de criterios: van en el
  formulario, no en el JSON que se importa.
