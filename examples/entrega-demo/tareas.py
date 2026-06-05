"""Lógica de tareas. NOTA (a propósito, para el test): no persiste en tareas.json,
no permite eliminar, y marcar_hecha no maneja id inexistente (rompe con excepción)."""

_tareas = []
_siguiente_id = 1


def agregar_tarea(descripcion):
    global _siguiente_id
    _tareas.append({"id": _siguiente_id, "descripcion": descripcion, "hecha": False})
    _siguiente_id += 1


def listar_tareas():
    for t in _tareas:
        estado = "hecha" if t["hecha"] else "pendiente"
        print(f"{t['id']} - {t['descripcion']} [{estado}]")


def marcar_hecha(tid):
    # Bug intencional: si el id no existe, esto lanza StopIteration (rompe la app)
    tarea = next(t for t in _tareas if t["id"] == tid)
    tarea["hecha"] = True
