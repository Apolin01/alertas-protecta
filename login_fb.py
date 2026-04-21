"""
login_fb.py — Ejecutar UNA SOLA VEZ para guardar la sesión de Facebook.
Abre Chrome visible → logueas manualmente → cierra → sesión guardada.

Uso:
    python login_fb.py
"""

import os
from playwright.sync_api import sync_playwright

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fb_session")


def main():
    print("=" * 50)
    print("LOGIN DE FACEBOOK — Solo se hace una vez")
    print("=" * 50)
    print(f"\nSesión se guardará en: {SESSION_DIR}\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            SESSION_DIR,
            headless=False,
            slow_mo=300,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = ctx.new_page()
        page.goto("https://www.facebook.com")

        print("Se abrió Chrome. Logueate en Facebook.")
        print("Cuando veas tu feed, vuelve aquí y presiona ENTER.")
        input("\n>>> Presiona ENTER cuando hayas iniciado sesión: ")

        # Verificar que la sesión es válida
        if "facebook.com" in page.url and "login" not in page.url:
            print("\n✅ Sesión guardada correctamente.")
            print("Ya puedes ejecutar: python main.py")
        else:
            print("\n⚠️  No se detectó sesión activa. Intenta de nuevo.")

        ctx.close()


if __name__ == "__main__":
    main()
