#!/usr/bin/env python3
"""
Simulador de corrección Active-IA con el CLI de Claude.

Replica la consolidación del código + el prompt de corrección del sistema,
pero dispara la corrección local con el comando `claude` en la terminal,
usando Claude como reemplazo del modelo de producción.

Sirve para PROBAR una rúbrica antes de subirla: ver qué nota y qué feedback
produce sobre una entrega real, sin pasar por el sistema.

FIDELIDAD A LA INTENCIÓN DEL SISTEMA (no al bug):
El corrector DEBE evaluar con la rúbrica COMPLETA. Por eso este simulador
le envía al modelo todo lo que la rúbrica define:
  - criterios: id, nombre, peso, descripción, instrucciones_puntuación
  - subcriterios + EVIDENCIAS (el checklist verificable)
  - penalizaciones (descuentos)
  - condiciones_desaprobacion (techos de nota)
  - metadata (lenguaje, framework, formato, etc.)
Si el workflow de N8N hoy omite alguna de estas partes, es un BUG del workflow,
no algo que este test deba imitar. El test ejerce la corrección CORRECTA.

Uso:
    python simular_correccion.py --rubrica <rubrica.json> --entrega <archivo|carpeta|.zip|.txt>
        [--materia "Nombre"] [--alumno "Nombre"] [--tipo TP]
        [--modo solo_codigo|web_completo|proyecto_completo|personalizado]
        [--ext ".ipynb,.sql"] [--out <carpeta>] [--model <id>] [--no-run]

Salida:
    <out>/prompt_correccion.txt  → el material EXACTO que recibe el modelo
    <out>/correccion.json        → la corrección parseada (si se ejecutó)
    + informe legible en la terminal
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# --- Constantes copiadas de backend/app/services/consolidacion_service.py ----
EXCLUDED_DIRS = {".git", ".idea", ".vscode", ".settings", "target", "build",
                 "out", "bin", "node_modules", ".gradle", ".mvn", "__pycache__",
                 ".pytest_cache", "__MACOSX"}
BINARY_EXTENSIONS = {".class", ".jar", ".war", ".ear", ".zip", ".tar", ".gz",
                     ".7z", ".exe", ".dll", ".so", ".dylib", ".png", ".jpg",
                     ".jpeg", ".gif", ".ico", ".bmp", ".mp3", ".mp4", ".avi",
                     ".mov", ".doc", ".docx", ".bin"}
LANG_MAP = {".py": "python", ".java": "java", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript", ".c": "c", ".cpp": "cpp",
            ".h": "c", ".hpp": "cpp", ".go": "go", ".rs": "rust", ".kt": "kotlin",
            ".kts": "kotlin", ".rb": "ruby", ".php": "php", ".swift": "swift",
            ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
            ".json": "json", ".md": "markdown", ".txt": "text", ".yml": "yaml",
            ".yaml": "yaml", ".xml": "xml", ".sql": "sql", ".sh": "bash",
            ".bat": "batch", ".cmd": "batch", ".properties": "properties",
            ".gradle": "gradle"}
_CODIGO = {".py", ".java", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h",
           ".hpp", ".go", ".rs", ".kt", ".rb", ".php", ".swift"}
MODOS = {
    "solo_codigo": ("Solo código", set(_CODIGO)),
    "web_completo": ("Web completo", _CODIGO | {".html", ".htm", ".css", ".scss", ".json"}),
    "proyecto_completo": ("Proyecto completo", _CODIGO | {".html", ".htm", ".css", ".scss",
        ".json", ".md", ".txt", ".yml", ".yaml", ".xml", ".sql", ".sh", ".bat",
        ".cmd", ".properties", ".gradle", ".kts"}),
}


def ext_of(name: str) -> str:
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


def read_safely(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
        try:
            return raw.decode(enc).replace("\x00", "")
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "[Error: No se pudo leer el archivo con encodings comunes]"


def resolve_ext(modo: str, custom: list[str] | None) -> set[str]:
    if modo == "personalizado":
        if not custom:
            raise SystemExit("Modo personalizado requiere --ext '.x,.y'")
        return {e if e.startswith(".") else f".{e}" for e in custom}
    if modo not in MODOS:
        raise SystemExit(f"Modo inválido: {modo}")
    return MODOS[modo][1]


def modo_nombre(modo: str) -> str:
    return MODOS[modo][0] if modo in MODOS else modo


def build_tree(paths: list[str]) -> str:
    entries: set[str] = set()
    for p in paths:
        parts = p.split("/")
        for i in range(len(parts)):
            entries.add("/".join(parts[: i + 1]))
    file_set = set(paths)
    sorted_entries = sorted(entries)
    out = []
    for e in sorted_entries[:50]:
        level = e.count("/")
        out.append(f"{'  ' * level}{'📄 ' if e in file_set else '📁 '}{e.split('/')[-1]}")
    if len(sorted_entries) > 50:
        out.append(f"\n... y {len(sorted_entries) - 50} elementos más")
    return "\n".join(out)


def build_document(contenidos: list[tuple[str, str]], modo_nom: str, single: bool) -> str:
    s: list[str] = []
    s.append("# Documento de Evaluación - Entrega del Alumno\n\n")
    s.append("> 📋 **IMPORTANTE PARA LA CORRECCIÓN:**  \n")
    s.append("> Este documento fue generado automáticamente a partir de la entrega del alumno.  \n")
    s.append("> El estudiante **NO envió este archivo TXT**, sino archivos de código fuente que fueron procesados aquí.  \n")
    s.append("> A continuación se presenta el contenido completo de todos los archivos entregados para su evaluación.\n\n")
    s.append(f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    if not single:
        s.append(f"**Modo de procesamiento:** {modo_nom}\n\n")
    s.append("## 📋 Metadata del Proyecto\n\n")
    s.append(f"- **Total de archivos:** {len(contenidos)}\n")
    paths = [p for p, _ in contenidos]
    s.append("\n## 📁 Estructura de Directorios\n\n```\n")
    if single:
        s.append(f"📄 {paths[0]}\n```\n")
    else:
        s.append(build_tree(paths))
        s.append("\n```\n")
    s.append("\n## 📄 Contenido de Archivos\n\n---\n\n")
    total_lines = 0
    codigo_files = 0
    for path, content in contenidos:
        ext = ext_of(path)
        lang = LANG_MAP.get(ext, "text")
        lines = content.count("\n") + 1
        total_lines += lines
        if ext in _CODIGO:
            codigo_files += 1
        s.append(f"### 📄 `{path}`\n\n")
        s.append(f"**Líneas:** {lines} | **Tipo:** {ext}\n\n")
        s.append(f"```{lang}\n{content}")
        if not content.endswith("\n"):
            s.append("\n")
        s.append("```\n\n---\n\n")
    s.append("## 📊 Estadísticas del Proyecto\n\n")
    s.append(f"- **Total de archivos procesados:** {len(contenidos)}\n")
    s.append(f"- **Total de líneas de código:** {total_lines:,}\n")
    s.append(f"- **Archivos de código:** {codigo_files}\n")
    s.append(f"- **Otros archivos:** {len(contenidos) - codigo_files}\n")
    return "".join(s)


def consolidar(entrega: str, modo: str, custom: list[str] | None) -> str:
    """Consolida la entrega igual que ConsolidacionService (dir, archivo, zip, txt)."""
    exts = resolve_ext(modo, custom)
    nom = modo_nombre(modo)

    if os.path.isdir(entrega):
        contenidos: list[tuple[str, str]] = []
        for root, dirs, files in os.walk(entrega):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, entrega).replace("\\", "/")
                ext = ext_of(f)
                if ext in BINARY_EXTENSIONS or ext not in exts:
                    continue
                with open(full, "rb") as fh:
                    contenidos.append((rel, read_safely(fh.read())))
        if not contenidos:
            raise SystemExit(f"No hay archivos con extensiones {sorted(exts)} en {entrega}")
        contenidos.sort(key=lambda x: x[0])
        return build_document(contenidos, nom, single=False)

    if entrega.lower().endswith(".zip"):
        with zipfile.ZipFile(entrega, "r") as zf:
            contenidos = []
            for info in sorted(zf.filelist, key=lambda i: i.filename):
                if info.is_dir():
                    continue
                path = info.filename.replace("\\", "/")
                if any(part in EXCLUDED_DIRS for part in path.split("/")[:-1]):
                    continue
                ext = ext_of(path)
                if ext in BINARY_EXTENSIONS or ext not in exts:
                    continue
                contenidos.append((path, read_safely(zf.read(info.filename))))
        if not contenidos:
            raise SystemExit("No se encontraron archivos válidos en el ZIP")
        return build_document(contenidos, nom, single=False)

    if entrega.lower().endswith(".txt"):
        with open(entrega, "rb") as fh:
            return read_safely(fh.read())

    # archivo individual de código
    with open(entrega, "rb") as fh:
        contenido = read_safely(fh.read())
    fname = os.path.basename(entrega)
    if ext_of(fname) not in exts:
        raise SystemExit(f"La extensión {ext_of(fname)} no está permitida en el modo '{modo}'")
    return build_document([(fname, contenido)], nom, single=True)


def cargar_rubrica(path: str) -> dict:
    """Acepta CriteriosStructure o RubricaCreate y normaliza la rúbrica completa."""
    data = json.load(open(path, encoding="utf-8"))
    return {
        "titulo": data.get("titulo", "Sin título"),
        "tipo": data.get("tipo"),
        "puntaje_maximo": data.get("puntaje_maximo", 100),
        "metadata": data.get("metadata") or data.get("metadata_json") or {},
        "criterios": data.get("criterios") or data.get("criterios_json") or [],
        "penalizaciones": data.get("penalizaciones") or data.get("penalizaciones_json") or [],
        "condiciones_desaprobacion": (data.get("condiciones_desaprobacion")
                                      or data.get("condiciones_desaprobacion_json") or []),
    }


def build_prompt(rubrica: dict, codigo: str, materia: str, alumno: str) -> str:
    """Construye el prompt de corrección con la rúbrica COMPLETA (intención del sistema).

    Base: nodo "Construir Body Gemini" de correccion-workflow.json, corregido para
    incluir subcriterios+evidencias (patrón de correccion-pdf-workflow.json),
    instrucciones_puntuación y metadata.
    """
    # Criterios CON subcriterios + evidencias + instrucciones de puntuación
    criterios_texto = ""
    for c in rubrica["criterios"]:
        criterios_texto += (
            f"- ID: {c.get('id')}\n  Nombre: {c.get('nombre')}\n"
            f"  Peso: {c.get('peso')} pts\n  Descripción: {c.get('descripcion')}\n"
        )
        if c.get("instrucciones_puntuacion"):
            criterios_texto += f"  Instrucciones de puntuación: {c['instrucciones_puntuacion']}\n"
        subs = c.get("subcriterios") or []
        if subs:
            criterios_texto += "  Evidencias esperadas (checklist verificable en la entrega):\n"
            for sub in subs:
                if sub.get("descripcion"):
                    criterios_texto += f"  - {sub['descripcion']}\n"
                for ev in (sub.get("evidencias") or []):
                    criterios_texto += f"    * {ev}\n"
        criterios_texto += "\n"

    # Penalizaciones
    pen_texto = ""
    for p in rubrica["penalizaciones"]:
        pen_texto += (f"- ID: {p.get('id')}\n  Descripción: {p.get('descripcion')}\n"
                      f"  Descuento: {p.get('descuento_porcentaje')}%\n\n")

    # Condiciones de desaprobación
    cond_texto = ""
    for cd in rubrica["condiciones_desaprobacion"]:
        techo = cd.get("nota_maxima", cd.get("nota_final", 0))
        cond_texto += (f"- ID: {cd.get('id')}\n  Condición: {cd.get('condicion')}\n"
                       f"  Nota máxima permitida: {techo}\n\n")

    # Metadata de contexto adicional
    meta_texto = ""
    for k, v in (rubrica["metadata"] or {}).items():
        meta_texto += f"- {k}: {v}\n"

    # Listas inline para los pasos 2 y 3
    cd_inline = "\n".join(
        f"   - {cd.get('id')}: {cd.get('condicion')} → Si se cumple, nota máxima = "
        f"{cd.get('nota_maxima', cd.get('nota_final', 0))}"
        for cd in rubrica["condiciones_desaprobacion"]
    ) or "   Ninguna."
    pen_inline = "\n".join(
        f"   - {p.get('id')}: {p.get('descripcion')} → Descuento del {p.get('descuento_porcentaje')}% sobre la nota"
        for p in rubrica["penalizaciones"]
    ) or "   Ninguna."

    pm = rubrica["puntaje_maximo"]
    return (
        f'Eres un evaluador experto de trabajos prácticos de programación para la materia "{materia}".\n\n'
        f'Tu tarea es evaluar el siguiente código del alumno "{alumno}" según la rúbrica proporcionada.\n\n'
        f"## RÚBRICA DE EVALUACIÓN\n\n"
        f"Título: {rubrica['titulo']}\nTipo: {rubrica['tipo']}\nPuntaje máximo: {pm}\n\n"
        f"## CONTEXTO ADICIONAL\n\n{meta_texto or 'Sin metadata adicional.'}\n\n"
        f"Criterios:\n{criterios_texto}\n"
        f"## PENALIZACIONES\n\n"
        f"Estas penalizaciones se aplican SOBRE el puntaje obtenido en los criterios. "
        f"Evalúa si alguna aplica al código entregado.\n{pen_texto or 'Ninguna definida.'}\n\n"
        f"## CONDICIONES DE DESAPROBACIÓN\n\n"
        f"IMPORTANTE: Estas condiciones establecen un TECHO (nota máxima) para la calificación. "
        f"Si CUALQUIERA de ellas se cumple, la nota final NO PUEDE SUPERAR el máximo indicado. "
        f"La nota final será el MÍNIMO entre la suma de criterios y la nota máxima de la condición. "
        f"Evalúa cada condición cuidadosamente.\n{cond_texto or 'Ninguna definida.'}\n\n"
        f"## CÓDIGO DEL ALUMNO\n\n```\n{codigo}\n```\n\n"
        f"## INSTRUCCIONES DE EVALUACIÓN\n\n"
        f"1. Primero, evalúa cada criterio de la rúbrica normalmente (puntaje y feedback), "
        f"verificando las evidencias esperadas de cada criterio contra el código.\n"
        f"2. Luego, verifica si alguna CONDICIÓN DE DESAPROBACIÓN se cumple:\n{cd_inline}\n"
        f"3. Luego, verifica si alguna PENALIZACIÓN aplica:\n{pen_inline}\n"
        f"4. Calcula la nota final:\n"
        f"   - Calcula nota_antes_penalizaciones = suma de puntajes de los criterios.\n"
        f"   - Si aplica alguna condición de desaprobación → nota = min(nota_antes_penalizaciones, "
        f"nota_maxima_de_la_condicion). Es decir, la nota no puede superar el techo.\n"
        f"   - Si aplica alguna penalización → aplica el descuento porcentual sobre nota_antes_penalizaciones.\n"
        f"   - Si no aplica nada → nota = nota_antes_penalizaciones.\n\n"
        f"Para cada criterio:\n"
        f"1. DEBES incluir el ID exacto del criterio de la rúbrica\n"
        f"2. Asigna un puntaje entre 0 y el peso del criterio\n"
        f"3. Determina el estado:\n"
        f'   - "OK" si logra ≥80% del peso del criterio\n'
        f'   - "WARNING" si logra 40-79% del peso\n'
        f'   - "ERROR" si logra <40% del peso\n'
        f"4. Proporciona feedback específico y constructivo, citando las evidencias cumplidas o faltantes\n\n"
        f"Además:\n"
        f"- Lista 2-4 fortalezas del código (array de strings)\n"
        f"- Lista 2-4 recomendaciones de mejora específicas (array de strings)\n"
        f"- Escribe un comentario general de 2-3 oraciones\n\n"
        f"## FORMATO DE RESPUESTA OBLIGATORIO\n\n"
        f"Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:\n\n"
        f"{{\n"
        f'  "nota": <número entre 0 y {pm}>,\n'
        f'  "condicion_desaprobacion_aplicada": <null si no aplica, o el ID de la condición que aplica (ej: "CD1")>,\n'
        f'  "penalizaciones_aplicadas": [<array de IDs de penalizaciones aplicadas, vacío si ninguna>],\n'
        f'  "nota_antes_penalizaciones": <número: suma de criterios antes de aplicar condiciones o penalizaciones>,\n'
        f'  "criterios": [\n'
        f"    {{\n"
        f'      "id": "<ID exacto del criterio de la rúbrica>",\n'
        f'      "nombre": "<nombre exacto del criterio de la rúbrica>",\n'
        f'      "puntaje_obtenido": <número>,\n'
        f'      "puntaje_maximo": <número igual al peso del criterio>,\n'
        f'      "estado": "<OK|WARNING|ERROR>",\n'
        f'      "feedback": "<feedback específico>"\n'
        f"    }}\n"
        f"  ],\n"
        f'  "fortalezas": ["<fortaleza 1>", "<fortaleza 2>"],\n'
        f'  "recomendaciones": ["<recomendación 1>", "<recomendación 2>"],\n'
        f'  "comentario_general": "<comentario de 2-3 oraciones>"\n'
        f"}}\n\n"
        f"IMPORTANTE:\n"
        f"- CADA criterio debe tener su ID exacto de la rúbrica\n"
        f'- Si aplica una condición de desaprobación, "nota" debe ser min(suma_criterios, '
        f'nota_maxima_de_la_condicion), pero IGUAL debes evaluar todos los criterios con su puntaje real.\n'
        f'- Si aplica una penalización, "nota" debe reflejar el descuento aplicado sobre "nota_antes_penalizaciones".\n'
        f'- Si no aplica ni condición ni penalización, "nota" = "nota_antes_penalizaciones" = suma de puntajes.\n'
        f"- Cada criterio de la rúbrica debe aparecer en la respuesta\n"
        f"- NO incluyas texto antes o después del JSON"
    )


def correr_claude(prompt: str, model: str | None) -> str:
    cmd = ["claude", "-p"]
    if model:
        cmd += ["--model", model]
    try:
        r = subprocess.run(cmd, input=prompt, text=True, capture_output=True, encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit("No se encontró el comando 'claude' en el PATH.")
    if r.returncode != 0:
        raise SystemExit(f"claude falló (exit {r.returncode}):\n{r.stderr}")
    return r.stdout.strip()


def extraer_json(texto: str) -> dict:
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip().rstrip("`").strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j != -1:
            return json.loads(t[i:j + 1])
        raise


def normalizar_nota(corr: dict) -> None:
    """Replica el parser de N8N: nota_antes_penalizaciones = suma; techos y notas coherentes."""
    suma = sum(c.get("puntaje_obtenido", 0) for c in corr.get("criterios", []))
    corr["nota_antes_penalizaciones"] = suma
    cd = corr.get("condicion_desaprobacion_aplicada")
    pen = corr.get("penalizaciones_aplicadas") or []
    if cd and corr.get("nota", 0) > suma:
        corr["nota"] = suma
    if not cd and not pen:
        corr["nota"] = suma


def informe(rubrica: dict, corr: dict) -> list[str]:
    """Valida la corrección contra la rúbrica y devuelve advertencias."""
    warns: list[str] = []
    peso_por_id = {str(c.get("id")): c.get("peso") for c in rubrica["criterios"]}
    resp = {str(c.get("id")): c for c in corr.get("criterios", [])}

    for cid in peso_por_id:
        if cid not in resp:
            warns.append(f"El criterio '{cid}' de la rúbrica NO aparece en la corrección.")
    for cid in resp:
        if cid not in peso_por_id:
            warns.append(f"La corrección trae un criterio '{cid}' que no existe en la rúbrica.")
    for cid, c in resp.items():
        peso = peso_por_id.get(cid)
        obt = c.get("puntaje_obtenido")
        if peso is not None and isinstance(obt, (int, float)) and obt > peso:
            warns.append(f"'{cid}': puntaje_obtenido {obt} supera el peso {peso}.")

    pen_ids = {str(p.get("id")) for p in rubrica["penalizaciones"]}
    for pid in (corr.get("penalizaciones_aplicadas") or []):
        if str(pid) not in pen_ids:
            warns.append(f"penalizaciones_aplicadas refiere a '{pid}', que no existe en la rúbrica.")
    cd = corr.get("condicion_desaprobacion_aplicada")
    if cd:
        cd_ids = {str(x.get("id")) for x in rubrica["condiciones_desaprobacion"]}
        if str(cd) not in cd_ids:
            warns.append(f"condicion_desaprobacion_aplicada '{cd}' no existe en la rúbrica.")
    return warns


def imprimir(rubrica: dict, corr: dict, warns: list[str]) -> None:
    print("\n" + "=" * 64)
    nap = corr.get("nota_antes_penalizaciones")
    print(f"  CORRECCIÓN SIMULADA — NOTA: {corr.get('nota')} / {rubrica['puntaje_maximo']}")
    if nap is not None and nap != corr.get("nota"):
        print(f"  (nota antes de penalizaciones/condiciones: {nap})")
    if corr.get("condicion_desaprobacion_aplicada"):
        print(f"  ⛔ Condición de desaprobación aplicada: {corr['condicion_desaprobacion_aplicada']}")
    if corr.get("penalizaciones_aplicadas"):
        print(f"  ➖ Penalizaciones aplicadas: {', '.join(map(str, corr['penalizaciones_aplicadas']))}")
    print("=" * 64)
    print("\nCriterios:")
    for c in corr.get("criterios", []):
        est = c.get("estado", "?")
        icono = {"OK": "✅", "WARNING": "⚠️ ", "ERROR": "❌"}.get(est, "•")
        print(f"  {icono} [{c.get('id')}] {c.get('nombre')}: "
              f"{c.get('puntaje_obtenido')}/{c.get('puntaje_maximo')} ({est})")
        fb = (c.get("feedback") or "").strip()
        if fb:
            print(f"      → {fb}")
    if corr.get("fortalezas"):
        print("\nFortalezas:")
        for f in corr["fortalezas"]:
            print(f"  + {f}")
    if corr.get("recomendaciones"):
        print("\nRecomendaciones:")
        for r in corr["recomendaciones"]:
            print(f"  - {r}")
    if corr.get("comentario_general"):
        print(f"\nComentario general:\n  {corr['comentario_general']}")
    if warns:
        print("\n⚠️  Avisos (lo que el test reveló sobre la rúbrica):")
        for w in warns:
            print(f"  • {w}")
    else:
        print("\n✅ La corrección es consistente con la rúbrica.")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Simula la corrección de Active-IA con el CLI de Claude.")
    ap.add_argument("--rubrica", required=True, help="JSON de la rúbrica (CriteriosStructure o RubricaCreate)")
    ap.add_argument("--entrega", required=True, help="Archivo, carpeta, .zip o .txt con la entrega del alumno")
    ap.add_argument("--materia", default="Materia de prueba")
    ap.add_argument("--alumno", default="Alumno de prueba")
    ap.add_argument("--tipo", default=None, help="Tipo de rúbrica si no está en el JSON (ej: TP)")
    ap.add_argument("--modo", default="solo_codigo")
    ap.add_argument("--ext", default=None, help="Extensiones para modo personalizado, ej: '.ipynb,.sql'")
    ap.add_argument("--out", default=None, help="Carpeta de salida (default: junto a la rúbrica)")
    ap.add_argument("--model", default=None, help="Modelo para claude -p (opcional)")
    ap.add_argument("--no-run", action="store_true", help="Solo prepara el material, no ejecuta claude")
    args = ap.parse_args()

    rubrica = cargar_rubrica(args.rubrica)
    if not rubrica["tipo"]:
        rubrica["tipo"] = args.tipo or "TP"
    if not rubrica["criterios"]:
        raise SystemExit("La rúbrica no tiene criterios.")

    custom = [e.strip() for e in args.ext.split(",")] if args.ext else None
    codigo = consolidar(args.entrega, args.modo, custom)
    prompt = build_prompt(rubrica, codigo, args.materia, args.alumno)

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.rubrica)), "simulacion")
    os.makedirs(out, exist_ok=True)
    prompt_path = os.path.join(out, "prompt_correccion.txt")
    open(prompt_path, "w", encoding="utf-8").write(prompt)
    print(f"📝 Material de corrección escrito en: {prompt_path}")
    n_sub = sum(len(c.get("subcriterios") or []) for c in rubrica["criterios"])
    print(f"   ({len(rubrica['criterios'])} criterios · {n_sub} subcriterios · "
          f"código consolidado: {len(codigo):,} chars)")

    if args.no_run:
        cmd = "claude -p" + (f" --model {args.model}" if args.model else "")
        print(f"\n--no-run: para correrlo a mano:\n  Get-Content '{prompt_path}' | {cmd}")
        return 0

    print("\n🤖 Ejecutando corrección con claude... (esto puede tardar)")
    salida = correr_claude(prompt, args.model)
    try:
        corr = extraer_json(salida)
    except Exception as e:
        print(f"❌ No se pudo parsear la respuesta como JSON: {e}")
        print("Respuesta cruda:\n" + salida[:2000])
        open(os.path.join(out, "respuesta_cruda.txt"), "w", encoding="utf-8").write(salida)
        return 1

    corr.setdefault("fortalezas", [])
    corr.setdefault("recomendaciones", [])
    corr.setdefault("comentario_general", "")
    corr.setdefault("condicion_desaprobacion_aplicada", None)
    corr.setdefault("penalizaciones_aplicadas", [])
    normalizar_nota(corr)
    warns = informe(rubrica, corr)
    json.dump(corr, open(os.path.join(out, "correccion.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    imprimir(rubrica, corr, warns)
    print(f"💾 Corrección guardada en: {os.path.join(out, 'correccion.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
