"""Gestor de tareas por consola - punto de entrada."""
from tareas import agregar_tarea, listar_tareas, marcar_hecha


def menu():
    while True:
        print("\n1) Agregar  2) Listar  3) Marcar hecha  0) Salir")
        op = input("Opción: ")
        if op == "1":
            desc = input("Descripción: ")
            agregar_tarea(desc)
        elif op == "2":
            listar_tareas()
        elif op == "3":
            tid = int(input("Id: "))
            marcar_hecha(tid)
        elif op == "0":
            break
        else:
            print("Opción inválida")


if __name__ == "__main__":
    menu()
