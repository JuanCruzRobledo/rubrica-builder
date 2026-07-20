#!/usr/bin/env python3
"""
Validador autónomo de rúbricas Active-IA (modelo v1 y v2).

Replica EXACTAMENTE las reglas del schema Pydantic real
(backend/app/schemas/rubrica.py -> CriteriosStructure y sus hijos)
SIN importar el proyecto, para poder correr en cualquier entorno.

Si este validador pasa, el backend acepta la rúbrica. Si falla, la rebota.
Esa es la única razón por la que este script existe: cerrar el loop antes
de que el JSON llegue al sistema y te explote en la cara.

schema_version (v1 = subcriterios sin peso propio, v2 = subcriterios con
`peso` obligatorio que debe sumar exacto al `peso` del criterio) NO viaja
dentro del JSON de CriteriosStructure -- es un campo aparte del payload de
la rúbrica (hermano de tipo/numero/anio), y el front de Active-IA lo infiere
por presencia de `peso` en los subcriterios. Este validador hace lo mismo:
si algún subcriterio de la rúbrica trae `peso`, la trata como v2 completa.

Uso:
    python validar_rubrica.py <ruta_al_json>
    python validar_rubrica.py -          # lee el JSON desde stdin
    python validar_rubrica.py <ruta_al_json> --schema-version 1|2
        # fuerza la versión en vez de inferirla por presencia de `peso`

Salida:
    Exit 0  -> rúbrica válida (lista para "Cargar criterios")
    Exit 1  -> rúbrica inválida (imprime cada error con su ubicación)
    Exit 2  -> el archivo no es JSON parseable / no existe
"""

from __future__ import annotations

import json
import re
import sys

# La consola de Windows suele venir en cp1252 y revienta con emojis/acentos.
# Forzamos UTF-8 para que la salida sea legible en cualquier terminal.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# --- Patrones de ID exactos del schema real ---------------------------------
RE_CRITERIO_ID = re.compile(r"^[A-Z0-9]+$")        # C1, C2, C10
RE_SUBCRITERIO_ID = re.compile(r"^[A-Z0-9]+\.[0-9]+$")  # C1.1, C2.3
RE_PENALIZACION_ID = re.compile(r"^P[0-9]+$")       # P1, P2
RE_CONDICION_ID = re.compile(r"^CD[0-9]+$")         # CD1, CD2


class Validador:
    """Acumula errores en vez de cortar al primero: queremos ver TODO lo que
    está mal de una sola pasada, no jugar al whack-a-mole."""

    def __init__(self) -> None:
        self.errores: list[str] = []

    def err(self, ubicacion: str, mensaje: str) -> None:
        self.errores.append(f"[{ubicacion}] {mensaje}")

    # -- helpers de tipo ----------------------------------------------------
    def _str_no_vacio(self, valor, ubic: str, campo: str, maxlen: int | None = None) -> bool:
        if not isinstance(valor, str) or not valor.strip():
            self.err(ubic, f"'{campo}' es obligatorio y debe ser texto no vacío.")
            return False
        if maxlen is not None and len(valor) > maxlen:
            self.err(ubic, f"'{campo}' supera el máximo de {maxlen} caracteres (tiene {len(valor)}).")
            return False
        return True

    def _int_en_rango(self, valor, ubic: str, campo: str, lo: int, hi: int) -> bool:
        if isinstance(valor, bool) or not isinstance(valor, int):
            self.err(ubic, f"'{campo}' debe ser un entero.")
            return False
        if not (lo <= valor <= hi):
            self.err(ubic, f"'{campo}' debe estar entre {lo} y {hi} (tiene {valor}).")
            return False
        return True

    # -- validación principal ----------------------------------------------
    def validar(self, data, schema_version: int | None = None) -> int:
        """Valida `data` y devuelve la schema_version efectivamente usada
        (la forzada por `schema_version`, o la inferida por presencia de
        `peso` en subcriterios si no se forzó ninguna)."""
        if not isinstance(data, dict):
            self.err("raíz", "El JSON de la rúbrica debe ser un objeto (diccionario).")
            return schema_version or 1

        self._str_no_vacio(data.get("titulo"), "raíz", "titulo", 200)
        self._str_no_vacio(data.get("descripcion"), "raíz", "descripcion")

        # puntaje_maximo: siempre 100 (default 100 si no viene)
        puntaje = data.get("puntaje_maximo", 100)
        if puntaje != 100:
            self.err("raíz", f"'puntaje_maximo' debe ser exactamente 100 (tiene {puntaje}).")

        # metadata: opcional, pero si viene debe ser objeto
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            self.err("raíz", "'metadata' debe ser un objeto (puede estar vacío {}).")

        version = schema_version if schema_version is not None else _inferir_schema_version(data)
        self._validar_criterios(data.get("criterios"), version)
        self._validar_penalizaciones(data.get("penalizaciones", []))
        self._validar_condiciones(data.get("condiciones_desaprobacion", []))
        return version

    def _validar_criterios(self, criterios, schema_version: int) -> None:
        if not isinstance(criterios, list) or len(criterios) == 0:
            self.err("raíz", "'criterios' debe ser una lista con al menos 1 criterio.")
            return

        ids: list[str] = []
        suma_pesos = 0
        for i, c in enumerate(criterios):
            ubic = f"criterios[{i}]"
            if not isinstance(c, dict):
                self.err(ubic, "cada criterio debe ser un objeto.")
                continue

            cid = c.get("id")
            if self._str_no_vacio(cid, ubic, "id", 20):
                if not RE_CRITERIO_ID.match(cid):
                    self.err(ubic, f"'id' = '{cid}' no respeta el formato ^[A-Z0-9]+$ (ej: C1, C2).")
                ids.append(cid)

            self._str_no_vacio(c.get("nombre"), ubic, "nombre", 100)
            self._str_no_vacio(c.get("descripcion"), ubic, "descripcion", 500)

            peso = c.get("peso")
            peso_valido = self._int_en_rango(peso, ubic, "peso", 1, 100)
            if peso_valido:
                suma_pesos += peso

            instr = c.get("instrucciones_puntuacion")
            if instr is not None and (not isinstance(instr, str) or len(instr) > 2000):
                self.err(ubic, "'instrucciones_puntuacion' es opcional pero debe ser texto de ≤2000 chars.")

            self._validar_subcriterios(
                c.get("subcriterios"), cid or f"#{i}", ubic,
                peso_criterio=peso if peso_valido else None,
                schema_version=schema_version,
            )

        # IDs de criterios únicos
        dup = _duplicados(ids)
        if dup:
            self.err("criterios", f"IDs de criterios duplicados: {', '.join(dup)}. Deben ser únicos.")

        # Σ pesos == 100  (la regla más importante de toda la rúbrica)
        if suma_pesos != 100:
            self.err(
                "criterios",
                f"La suma de los pesos es {suma_pesos}, debe ser exactamente 100. "
                f"Reajustá los pesos antes de cargar.",
            )

    def _validar_subcriterios(
        self, subs, criterio_id: str, ubic_padre: str,
        peso_criterio: int | None, schema_version: int,
    ) -> None:
        if not isinstance(subs, list) or len(subs) == 0:
            self.err(ubic_padre, f"el criterio '{criterio_id}' debe tener al menos 1 subcriterio.")
            return

        sub_ids: list[str] = []
        suma_pesos_sub = 0
        for j, s in enumerate(subs):
            ubic = f"{ubic_padre}.subcriterios[{j}]"
            if not isinstance(s, dict):
                self.err(ubic, "cada subcriterio debe ser un objeto.")
                continue

            sid = s.get("id")
            if self._str_no_vacio(sid, ubic, "id", 20):
                if not RE_SUBCRITERIO_ID.match(sid):
                    self.err(ubic, f"'id' = '{sid}' no respeta el formato ^[A-Z0-9]+\\.[0-9]+$ (ej: C1.1).")
                sub_ids.append(sid)

            self._str_no_vacio(s.get("descripcion"), ubic, "descripcion", 500)

            evidencias = s.get("evidencias")
            if not isinstance(evidencias, list) or len(evidencias) == 0:
                self.err(ubic, "'evidencias' debe ser una lista con al menos 1 evidencia verificable.")
            else:
                for k, e in enumerate(evidencias):
                    if not isinstance(e, str) or not e.strip():
                        self.err(ubic, f"evidencias[{k}] no puede estar vacía.")

            # En v2 el peso del subcriterio es obligatorio y se valida/suma.
            # En v1 no se exige (retrocompatibilidad exacta con rúbricas viejas).
            if schema_version == 2:
                peso_sub = s.get("peso")
                if self._int_en_rango(peso_sub, ubic, "peso", 1, 100):
                    suma_pesos_sub += peso_sub

        dup = _duplicados(sub_ids)
        if dup:
            self.err(ubic_padre, f"IDs de subcriterios duplicados en '{criterio_id}': {', '.join(dup)}.")

        # Σ pesos de subcriterios == peso del criterio (solo v2, y solo si el
        # peso del criterio en sí es válido -- si no lo es, ya se reportó arriba).
        if schema_version == 2 and peso_criterio is not None and suma_pesos_sub != peso_criterio:
            self.err(
                ubic_padre,
                f"La suma de los pesos de los subcriterios de '{criterio_id}' es "
                f"{suma_pesos_sub}, debe ser exactamente {peso_criterio} (el peso del criterio).",
            )

    def _validar_penalizaciones(self, penas) -> None:
        if not isinstance(penas, list):
            self.err("penalizaciones", "debe ser una lista (puede estar vacía []).")
            return
        ids: list[str] = []
        for i, p in enumerate(penas):
            ubic = f"penalizaciones[{i}]"
            if not isinstance(p, dict):
                self.err(ubic, "cada penalización debe ser un objeto.")
                continue
            pid = p.get("id")
            if self._str_no_vacio(pid, ubic, "id", 20):
                if not RE_PENALIZACION_ID.match(pid):
                    self.err(ubic, f"'id' = '{pid}' no respeta el formato ^P[0-9]+$ (ej: P1, P2).")
                ids.append(pid)
            self._str_no_vacio(p.get("descripcion"), ubic, "descripcion", 500)
            self._int_en_rango(p.get("descuento_porcentaje"), ubic, "descuento_porcentaje", 0, 100)
        dup = _duplicados(ids)
        if dup:
            self.err("penalizaciones", f"IDs de penalizaciones duplicados: {', '.join(dup)}.")

    def _validar_condiciones(self, conds) -> None:
        if not isinstance(conds, list):
            self.err("condiciones_desaprobacion", "debe ser una lista (puede estar vacía []).")
            return
        ids: list[str] = []
        for i, c in enumerate(conds):
            ubic = f"condiciones_desaprobacion[{i}]"
            if not isinstance(c, dict):
                self.err(ubic, "cada condición debe ser un objeto.")
                continue
            cid = c.get("id")
            if self._str_no_vacio(cid, ubic, "id", 20):
                if not RE_CONDICION_ID.match(cid):
                    self.err(ubic, f"'id' = '{cid}' no respeta el formato ^CD[0-9]+$ (ej: CD1).")
                ids.append(cid)
            self._str_no_vacio(c.get("condicion"), ubic, "condicion", 500)
            # OJO: el campo es 'nota_maxima', NO 'nota_final' (error común de la doc vieja).
            if "nota_final" in c and "nota_maxima" not in c:
                self.err(ubic, "usaste 'nota_final'; el campo correcto es 'nota_maxima'.")
            self._int_en_rango(c.get("nota_maxima"), ubic, "nota_maxima", 0, 100)
        dup = _duplicados(ids)
        if dup:
            self.err("condiciones_desaprobacion", f"IDs de condiciones duplicados: {', '.join(dup)}.")


def _inferir_schema_version(data: dict) -> int:
    """Misma regla que usa el front de Active-IA al guardar: si ALGÚN
    subcriterio de ALGÚN criterio trae la clave `peso`, toda la rúbrica se
    trata como v2. `schema_version` no viaja en este JSON -- se infiere."""
    criterios = data.get("criterios")
    if not isinstance(criterios, list):
        return 1
    for c in criterios:
        if not isinstance(c, dict):
            continue
        for s in c.get("subcriterios") or []:
            if isinstance(s, dict) and "peso" in s:
                return 2
    return 1


def _duplicados(items: list[str]) -> list[str]:
    vistos: set[str] = set()
    dups: list[str] = []
    for it in items:
        if it in vistos and it not in dups:
            dups.append(it)
        vistos.add(it)
    return dups


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--schema-version")]
    schema_version: int | None = None
    for i, a in enumerate(sys.argv[1:], start=1):
        if a == "--schema-version" and i < len(sys.argv) - 1:
            schema_version = int(sys.argv[i + 1])
        elif a.startswith("--schema-version="):
            schema_version = int(a.split("=", 1)[1])
    if schema_version is not None and schema_version not in (1, 2):
        print("--schema-version debe ser 1 o 2.", file=sys.stderr)
        return 2

    if len(args) != 1:
        print("Uso: python validar_rubrica.py <ruta_al_json | -> [--schema-version 1|2]", file=sys.stderr)
        return 2

    origen = args[0]
    try:
        raw = sys.stdin.read() if origen == "-" else open(origen, encoding="utf-8").read()
    except OSError as e:
        print(f"No se pudo leer el archivo: {e}", file=sys.stderr)
        return 2

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON inválido: {e}", file=sys.stderr)
        return 2

    v = Validador()
    version = v.validar(data, schema_version=schema_version)

    if v.errores:
        print(f"❌ RÚBRICA INVÁLIDA — {len(v.errores)} error(es):\n")
        for e in v.errores:
            print(f"  • {e}")
        print("\nCorregí estos puntos antes de cargar la rúbrica.")
        return 1

    n_crit = len(data.get("criterios", []))
    n_sub = sum(len(c.get("subcriterios", [])) for c in data.get("criterios", []))
    origen_version = "forzada con --schema-version" if schema_version is not None else "inferida por presencia de peso en subcriterios"
    print("✅ RÚBRICA VÁLIDA — el backend la acepta.")
    resumen = f"   schema_version={version} ({origen_version}) · {n_crit} criterios · {n_sub} subcriterios · Σ pesos criterios = 100 ✓"
    if version == 2:
        resumen += " · Σ pesos subcriterios = peso criterio ✓"
    print(resumen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
