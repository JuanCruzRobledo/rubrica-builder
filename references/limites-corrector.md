# Límites del corrector — qué puede y qué NO puede evaluar la IA

> Fuente de verdad de las restricciones estructurales del corrector. Replica el
> comportamiento real de `backend/app/services/consolidacion_service.py`
> (espejado en `scripts/simular_correccion.py`). El modo CURAR razona contra este
> archivo, no contra la memoria del modelo. Si este archivo y el servicio real
> discrepan, **gana el servicio**.

## Qué ve el corrector

Cuando el sistema corrige, el modelo recibe SOLO dos cosas: **la rúbrica** y el
**material consolidado de la entrega**. No tiene la consigna, no navega afuera, no
ejecuta nada. El material consolidado es un único documento de texto armado a partir
de los archivos de la entrega que pasan el filtro de extensión del modo.

## Los cuatro límites duros

1. **No navega a recursos externos.** Un link de repositorio (GitHub/GitLab), una URL
   de deploy, un video (YouTube/Drive), un recurso en la nube → la IA **no los abre**.
   Lo que esté detrás de un link es invisible para el corrector.

2. **Filtra por extensión según el modo.** Antes de llegar al modelo, la entrega se
   consolida tomando solo las extensiones permitidas del modo. Todo lo demás se
   descarta silenciosamente. En particular, las **imágenes** (`.png`, `.jpg`, `.jpeg`,
   `.gif`, `.ico`, `.bmp`) están en la lista de binarios excluidos y **nunca** llegan
   al corrector en los modos de código.

3. **Es un solo flujo: código O PDF, no los dos.** La corrección de código y la de PDF
   son workflows distintos. Una misma corrección consume **un único canal**. No se
   puede pedir que evalúe, en la misma corrección, el código entregado Y un informe PDF
   con capturas.

4. **No ejecuta nada.** El corrector lee archivos estáticos. "El programa corre y
   muestra X", "el deploy responde", "los tests pasan en CI" → no son verificables por
   ejecución. Solo se puede verificar lo que se lee mirando el código entregado.

## Extensiones por modo (espejo de `MODOS` en `simular_correccion.py`)

| Modo | Extensiones que llegan al corrector |
|------|-------------------------------------|
| `solo_codigo` | `.py .java .js .ts .jsx .tsx .c .cpp .h .hpp .go .rs .kt .rb .php .swift` |
| `web_completo` | lo de `solo_codigo` + `.html .htm .css .scss .json` |
| `proyecto_completo` | lo de `web_completo` + `.md .txt .yml .yaml .xml .sql .sh .bat .cmd .properties .gradle .kts` |
| `personalizado` | las extensiones que se pasen por `--ext` |

**Siempre excluidas (binarios), en cualquier modo de código:**
`.class .jar .war .ear .zip .tar .gz .7z .exe .dll .so .dylib .png .jpg .jpeg .gif
.ico .bmp .mp3 .mp4 .avi .mov .doc .docx .bin`

**Directorios ignorados:** `.git .idea .vscode .settings target build out bin
node_modules .gradle .mvn __pycache__ .pytest_cache __MACOSX`

## Implicancia para CURAR

Cualquier requisito de la consigna que dependa de algo de la lista de arriba
**rompe el flujo de corrección**: por más fiel que sea la rúbrica, el corrector no
puede evaluarlo. El modo CURAR existe para detectar estos puntos ANTES de crear la
rúbrica y resolverlos con una de las tres curas (ver "Modo CURAR" en `SKILL.md`):
**adaptar** al flujo único, **mantener en la consigna + corrección manual**, o
dejarlo **fuera de la rúbrica**.
