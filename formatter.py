"""
formatter.py — Genera los dos formatos de salida.
  1. FORMATO TABLA  → para base de datos / Excel (separado por _)
  2. FORMATO WHATSAPP → resumen con * para negrita
"""

import re
import requests
from datetime import datetime, timezone, timedelta

_PERU_TZ = timezone(timedelta(hours=-5))

def _now_peru(fmt: str) -> str:
    return datetime.now(_PERU_TZ).strftime(fmt)

NIVEL_EMOJI = {
    "CRIT": "CRIT 🔴",
    "ALRT": "ALRT 🟡",
    "INFO": "INFO 🟢",
}

_NIVEL_WORDS = ("CRIT", "ALRT", "INFO")


def _strip_echoed_header(text: str) -> str:
    """
    A veces la IA repite el header completo (NIVEL FECHA UBICACION - PALABRAS)
    al inicio de resumen_whatsapp en vez de solo el resumen (confundida por los
    EJEMPLOS del prompt, que muestran el mensaje final completo). Sin esto el
    mensaje sale con el header duplicado. Se detecta por el patrón NIVEL +
    fecha DD-MM-AA cerca del inicio, y se recorta hasta donde empieza la
    prosa real (primera palabra que no es MAYUSCULA/fecha/puntuación).
    """
    if not text:
        return text
    cabeza = text.lstrip("[*").strip()
    if not any(cabeza.startswith(w) for w in _NIVEL_WORDS):
        return text
    m = re.search(r'\d{2}-\d{2}-\d{2}', text)
    if not m or m.start() > 30:
        return text
    palabras = text[m.end():].split(" ")
    for i, w in enumerate(palabras):
        core = w.strip("[]*-.,")
        if core and any(c.islower() for c in core):
            resultado = " ".join(palabras[i:]).strip(" -")
            return resultado if resultado else text
    return text

# Columnas del Google Form / Sheets
SHEET_HEADERS = [
    "Marca temporal",
    "Dirección de correo electrónico",
    "Cliente",
    "Rubro",
    "Relevancia",
    "Asunto",
    "Coordenadas",
    "Insertar imagen de la noticia",
    "Link de la noticia",
    "Insertar noticia (Formato tabla de ChatGTP)",
    "fecha",
    "ID_Departamento",
    "Provincia",
    "Distrito",
    "Categoria",
    "Etiquetas",
    "Id_Noticias",
    "Bajo",
    "Medio",
    "Alto",
    "Día",
    "Operador",
    "Tipo",
]

# Caracteres prohibidos en titulo y palabras clave
_FORBIDDEN = str.maketrans("", "", ":;!?")


def _strip_camel(text: str) -> str:
    """
    Convierte CamelCase a palabras separadas en mayusculas.
    'POZODeAgua' → 'POZO DE AGUA'
    'JorgeHurtado' → 'JORGE HURTADO'
    """
    # Inserta espacio antes de mayuscula que sigue a minuscula
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    # Inserta espacio antes de mayuscula que sigue a mayuscula+minuscula
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)
    return s.upper()


def _normalize_ubication(dept: str, prov: str, dist: str, config=None) -> tuple:
    """
    Normaliza departamento, provincia y distrito según las reglas:
    1. Si no hay provincia → provincia = departamento
    2. Si no hay distrito → distrito = provincia
    3. Valida contra el mapeo en config.DEPT_PROV_DIST
    4. Retorna tupla (dept, prov, dist) normalizada y validada
    """
    dept = (dept or "").upper().strip()
    prov = (prov or "").upper().strip()
    dist = (dist or "").upper().strip()
    
    # Caso nacional
    if dept == "NACIONAL":
        return "NACIONAL", "NACIONAL", ""
    
    # Si todo está vacío
    if not dept and not prov and not dist:
        return "DESCONOCIDO", "DESCONOCIDO", "DESCONOCIDO"
    
    # Si existe config, validar contra DEPT_PROV_DIST
    if config and hasattr(config, 'DEPT_PROV_DIST'):
        dept_map = config.DEPT_PROV_DIST
        
        # Validar departamento
        if dept and dept in dept_map:
            prov_dist_map = dept_map[dept]
            
            # Si hay provincia, validar que existe
            if prov and prov in prov_dist_map:
                # Provincia válida, usar como es
                if not dist:
                    dist = prov  # Fallback: distrito = provincia
                elif dist not in prov_dist_map.get(prov, []):
                    # Distrito no válido para esta provincia, usar provincia
                    dist = prov
            elif prov:
                # Provincia no válida para este departamento
                # Buscar en otra provincia o usar como fallback
                prov = list(prov_dist_map.keys())[0] if prov_dist_map else dept
                dist = prov
            else:
                # No hay provincia, usar primera provincia del departamento
                prov = list(prov_dist_map.keys())[0] if prov_dist_map else dept
                dist = prov
        else:
            # Departamento no reconocido, usar como es
            if not prov:
                prov = dept
            if not dist:
                dist = prov
    else:
        # Sin config, aplicar reglas básicas
        if not prov or prov == dept:
            prov = dept
        if not dist or dist == prov:
            dist = prov
    
    # Último fallback: no dejar campos vacíos
    if not dept:
        dept = "DESCONOCIDO"
    if not prov:
        prov = dept
    if not dist:
        dist = prov
    
    return dept, prov, dist


class AlertFormatter:

    # Servicios de acortado, en orden de preferencia. clck.ru (Yandex) probo
    # ser el mas confiable (5/5 en pruebas, incluso con URLs largas de
    # Facebook) — redirige en 2 saltos automaticos (clck.ru -> sba.yandex.ru
    # -> destino) sin ninguna pagina visible al usuario. da.gd/is.gd quedan
    # como respaldo por si clck.ru falla (da.gd nos bloqueo por volumen antes,
    # is.gd fallo intermitentemente) — un solo servicio caido no debe dejar
    # todos los links sin acortar.
    _SHORTENERS = (
        ("clck.ru", "https://clck.ru/--", "url"),
        ("da.gd", "https://da.gd/shorten", "url"),
        ("is.gd", "https://is.gd/create.php", "url"),
    )

    def shorten_url(self, url: str) -> str:
        """Acorta una URL probando varios servicios con fallback entre ellos."""
        if not url or not url.startswith("http"):
            return url
        for name, endpoint, param in self._SHORTENERS:
            try:
                params = {param: url}
                if name == "is.gd":
                    params["format"] = "simple"
                resp = requests.get(endpoint, params=params, timeout=5)
                short = resp.text.strip()
                if resp.status_code == 200 and short.startswith("http"):
                    return short
            except Exception:
                continue
        return url

    # ─────────────────────────────────────────────────────────────
    # FORMATO 1 — TABLA (para BD / Excel)
    # FECHA_DEPARTAMENTO_PROVINCIA_DISTRITO_CATEGORIA_PALABRAS_CLAVE_TITULO
    # Siempre exactamente 6 underscores (7 columnas).
    # ─────────────────────────────────────────────────────────────
    def format_tabla(self, alert: dict, post: dict, config=None) -> str:
        # SIEMPRE usar fecha del servidor (hoy), no fecha de publicación
        fecha = _now_peru("%d-%m-%y")

        dept = alert.get("departamento") or ""
        prov = alert.get("provincia") or ""
        dist = alert.get("distrito") or ""
        
        # Normalizar ubicación
        dept, prov, dist = _normalize_ubication(dept, prov, dist, config)

        categoria = alert.get("categoria", "")

        palabras = alert.get("palabras_clave", [])
        # Limpiar caracteres prohibidos de cada keyword y unir con -
        palabras_clean = [str(p).translate(_FORBIDDEN) for p in palabras]
        palabras_str   = "-".join(palabras_clean)

        titulo = str(alert.get("titulo", "") or alert.get("resumen_whatsapp", "")).strip()
        titulo = titulo.translate(_FORBIDDEN)

        # Exactamente 6 _ separando 7 columnas
        return f"{fecha}_{dept}_{prov}_{dist}_{categoria}_{palabras_str}_{titulo}"

    # ─────────────────────────────────────────────────────────────
    # FORMATO 2 — WHATSAPP
    # *NIVEL FECHA DEPARTAMENTO [DISTRITO] - KEYWORD1 - KEYWORD2 - KEYWORD3*
    # Titulo y resumen - FUENTE: url
    #
    # La provincia ya NO se muestra (queda implícita/redundante), EXCEPTO
    # Pisco: tiene su propio cliente/grupo de WhatsApp separado del resto de
    # Ica (ver PROVINCIA_TO_CLIENT en classifier.py), así que mostrar "ICA"
    # ahí sería engañoso — se usa PISCO como si fuera el nivel principal.
    #   - Si se identificó un distrito real → DEPARTAMENTO DISTRITO
    #     Ej: ANCASH AYASH · CAJAMARCA JAEN
    #   - Si no se mencionó ni provincia ni distrito → solo DEPARTAMENTO
    #     Ej: ICA (antes salía "ICA ICA ICA")
    #   - Provincia PISCO → PISCO [DISTRITO]  (nunca "ICA PISCO")
    #   - Caso nacional → NACIONAL
    # ─────────────────────────────────────────────────────────────
    def format_whatsapp(self, alert: dict, post: dict, config=None) -> str:
        # SIEMPRE usar fecha del servidor (hoy), no fecha de publicación
        fecha = _now_peru("%d-%m-%y")

        dept_raw = alert.get("departamento") or ""
        prov_raw = alert.get("provincia") or ""
        dist_raw = alert.get("distrito") or ""

        # Normalizar ubicación (rellena/valida prov y dist si hiciera falta)
        dept, _, dist = _normalize_ubication(dept_raw, prov_raw, dist_raw, config)

        prov_mencionada = prov_raw.strip().upper()
        dist_mencionado = dist_raw.strip().upper()

        if dept == "NACIONAL":
            ubicacion = "NACIONAL"
        elif prov_mencionada == "PISCO":
            # Caso especial: Pisco tiene grupo propio, se usa como nivel principal.
            if dist_mencionado and dist_mencionado != prov_mencionada:
                ubicacion = f"PISCO {dist}".strip()
            else:
                ubicacion = "PISCO"
        else:
            # DEPARTAMENTO + DISTRITO solo si el distrito fue realmente
            # mencionado en la alerta (no un relleno de _normalize_ubication).
            if dist_mencionado and dist_mencionado != dept:
                ubicacion = f"{dept} {dist}".strip()
            else:
                ubicacion = dept

        # Keywords: convertir CamelCase a palabras separadas, unir con " - "
        palabras = alert.get("palabras_clave", [])
        palabras_wa = [_strip_camel(str(p)) for p in palabras]
        palabras_str = " - ".join(palabras_wa)

        titulo  = str(alert.get("titulo", "") or "").strip()
        resumen = str(alert.get("resumen_whatsapp", "") or "").strip()

        # USAR SOLO resumen (no concatenar titulo + resumen para evitar repetición)
        # Si no hay resumen, usar titulo como fallback
        cuerpo = resumen if resumen else titulo

        # A veces la IA repite el header completo dentro del resumen (ver
        # _strip_echoed_header) — se recorta antes de usarlo.
        cuerpo = _strip_echoed_header(cuerpo)

        # A veces la IA copia una cita "- FUENTE: X" del texto original dentro
        # del resumen — se quita para no duplicarla con la que agrega el sistema
        # abajo (ej. "...proteger sus fuentes de agua. - FUENTE: Grufides").
        cuerpo = re.sub(r'\s*-?\s*fuente\s*:\s*.*$', '', cuerpo, flags=re.IGNORECASE).strip()

        fuente_raw = post.get("url") or alert.get("source_url", "")
        fuente     = self.shorten_url(fuente_raw) if fuente_raw else ""
        fuente_str = f"- FUENTE: {fuente}" if fuente else "- FUENTE:"

        nivel  = NIVEL_EMOJI.get(alert.get("nivel", ""), "")
        header = f"*{nivel} {fecha} {ubicacion} - {palabras_str}*"

        return f"{header}\n{cuerpo} {fuente_str}"

    # ─────────────────────────────────────────────────────────────
    # Formato campo "Insertar noticia" del Google Form
    # ─────────────────────────────────────────────────────────────
    def format_noticia_tabla(self, alert: dict, post: dict, config=None) -> str:
        # SIEMPRE usar fecha del servidor (hoy), no fecha de publicación
        fecha        = _now_peru("%d-%m-%y")
        region       = alert.get("region", "").upper().replace(" ", "_")
        provincia    = alert.get("provincia", "").upper().replace(" ", "_")
        distrito     = alert.get("distrito", "").upper().replace(" ", "_")
        
        # Normalizar ubicación
        dept, prov, dist = _normalize_ubication(
            alert.get("departamento", ""),
            alert.get("provincia", ""),
            alert.get("distrito", ""),
            config
        )
        
        # Usar valores normalizados
        if not provincia or provincia == "":
            provincia = prov.replace(" ", "_")
        if not distrito or distrito == "":
            distrito = dist.replace(" ", "_")
        
        categoria    = alert.get("categoria", "").replace(" ", "-").upper()
        subcategoria = alert.get("subcategoria", "").replace(" ", "-").upper()
        resumen      = alert.get("resumen_whatsapp", "")
        return f"{fecha}_{region}_{provincia}_{distrito}_{categoria}_{subcategoria}_{resumen}"

    def format_sheets_row(self, alert: dict, post: dict, config=None) -> list:
        """
        Retorna lista de celdas en el mismo orden que las 23 columnas de Tabla_Informacion.
        Coincide exactamente con la estructura del Google Form.
        """
        now_dt   = datetime.now(_PERU_TZ)
        now_str  = now_dt.strftime("%d/%m/%Y %H:%M:%S")
        email    = getattr(config, "EMAIL_SISTEMA", "protecta.dev@gmail.com") if config else "protecta.dev@gmail.com"
        operador = getattr(config, "OPERADOR_AUTOMATICO", "Sistema Automático") if config else "Sistema Automático"

        cliente    = alert.get("cliente", "Ninguno (Coyuntura Nacional)")
        rubro      = alert.get("rubro", "Otros")
        relevancia = alert.get("relevancia", "Bajo")
        link       = post.get("url") or alert.get("source_url", "")
        imagen     = post.get("image_url", "")
        noticia_fmt = self.format_noticia_tabla(alert, post, config)
        tipo       = alert.get("tipo", "Noticia")

        departamento, provincia, distrito = _normalize_ubication(
            alert.get("departamento", ""),
            alert.get("provincia", ""),
            alert.get("distrito", ""),
            config
        )
        categoria    = alert.get("categoria", "")
        subcategoria = alert.get("subcategoria", "")
        tags         = "-".join(alert.get("tags", []))

        # Columnas del SPLIT
        fecha_split     = now_dt.strftime("%d-%m-%y")
        cat_split       = categoria.replace(" ", "-").upper() if categoria else ""
        etiquetas_split = subcategoria.replace(" ", "-").upper() if subcategoria else tags
        id_noticias     = alert.get("titulo", "") or alert.get("resumen_whatsapp", "")

        # Flags Bajo / Medio / Alto
        bajo  = 1 if relevancia == "Bajo"  else 0
        medio = 1 if relevancia == "Medio" else 0
        alto  = 1 if relevancia == "Alto"  else 0

        # Día en español
        _DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        dia = _DIAS_ES[now_dt.weekday()]

        return [
            now_str,        # Marca temporal
            email,          # Dirección de correo electrónico
            cliente,        # Cliente
            rubro,          # Rubro
            relevancia,     # Relevancia
            "",             # Asunto (vacío en entradas automáticas)
            "",             # Coordenadas
            imagen,         # Insertar imagen de la noticia
            link,           # Link de la noticia
            noticia_fmt,    # Insertar noticia (Formato tabla de ChatGTP)
            fecha_split,    # fecha
            departamento,   # ID_Departamento
            provincia,      # Provincia
            distrito,       # Distrito
            cat_split,      # Categoria
            etiquetas_split,# Etiquetas
            id_noticias,    # Id_Noticias
            bajo,           # Bajo
            medio,          # Medio
            alto,           # Alto
            dia,            # Día
            operador,       # Operador
            tipo,           # Tipo
        ]
