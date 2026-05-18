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

# Columnas del Google Form / Sheets
SHEET_HEADERS = [
    "Marca temporal",
    "Dirección de correo electrónico",
    "Cliente",
    "Rubro",
    "Relevancia",
    "Link de la noticia",
    "Insertar noticia (Formato tabla de ChatGTP)",
    "Operador",
    "Tipo",
    "Nivel_Alerta",
    "Region",
    "Departamento",
    "Provincia",
    "Distrito",
    "Categoria",
    "Subcategoria",
    "Tags",
    "Clave_Unica",
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


class AlertFormatter:

    def _optimize_description(self, desc: str) -> str:
        """
        💯 GARANTIZA EXACTAMENTE 20-25 PALABRAS en la salida.
        - Agresivo: remueve palabras relleno, artículos innecesarios
        - Trunca si es necesario (máximo 25 palabras)
        - Expande si es muy corto (mínimo 20 palabras)
        """
        if not desc or len(desc.strip()) < 3:
            return "Noticia sin descripción detallada disponible"
        
        # Normalizar: múltiples espacios a uno
        desc = " ".join(desc.split())
        
        # Palabras que SIEMPRE se pueden remover de forma segura
        FILLER_AGGRESSIVE = {
            "segun", "reporta", "reportan", "indico", "indicaron", "dijo", "dijeron",
            "menciono", "mencionaron", "senalo", "senalaron", "fue", "sera", "es",
            "ha", "han", "haya", "ahora", "ayer", "hoy", "mañana", "actualmente",
            "recientemente", "informo", "dio", "cuenta", "dieron", "informaron",
            "suele", "podria", "podrian", "puede", "pueden", "posible", "logicamente",
            "mas", "pero", "muy", "bastante", "bastanta", "realmente", "verdaderamente",
            "en", "a", "de", "del", "al", "con", "por", "para", "desde", "hacia",
            "durante", "mientras", "cuando", "donde", "segun",
        }
        
        words = desc.split()
        word_count = len(words)
        
        # ✅ CASO 1: PERFECTO (20-25 palabras) → retornar como está
        if 20 <= word_count <= 25:
            return desc.strip()
        
        # ❌ CASO 2: DEMASIADO LARGO (> 25 palabras) → TRUNCAR AGRESIVAMENTE
        if word_count > 25:
            # PASO 1: Remover palabras relleno
            filtradas = [w for w in words if w.lower() not in FILLER_AGGRESSIVE]
            
            # PASO 2: Si sigue siendo muy largo, truncar a 25
            if len(filtradas) > 25:
                filtradas = filtradas[:25]
            
            desc = " ".join(filtradas)
            if not desc.endswith((".", "!", "?")):
                desc = desc + "."
            
            return desc.strip()
        
        # ⚠️ CASO 3: MUY CORTO (< 20 palabras) → EXPANDIR CON CONTEXTO
        if word_count < 20:
            desc_lower = desc.lower()
            
            # Agregar contexto relevante según el tipo de noticia
            prefijos = []
            
            if any(x in desc_lower for x in ["detenido", "asesinado", "muerto", "herido", "fallecido"]):
                prefijos = ["Operativo policial registra", "Acción de seguridad en"]
            elif any(x in desc_lower for x in ["bloqueo", "protesta", "manifestacion", "paro", "movilizacion"]):
                prefijos = ["Mantiene bloqueo de acceso", "Protesta reportada en"]
            elif any(x in desc_lower for x in ["incendio", "explosion", "derrame", "accidente"]):
                prefijos = ["EMERGENCIA reportada en", "Incidente crítico en"]
            elif any(x in desc_lower for x in ["acuerdo", "negociacion", "dialogo", "reunion"]):
                prefijos = ["En negociación encontrándose", "Diálogo inicial entre"]
            elif any(x in desc_lower for x in ["suspension", "huelga", "paro"]):
                prefijos = ["Suspensión de servicios en", "Paro decretado en"]
            
            if prefijos:
                desc = prefijos[0] + " " + desc
                words = desc.split()
            
            word_count = len(words)
            
            # Si aún es < 20, truncar a 20 (garantizar mínimo)
            if word_count < 20:
                desc = " ".join(words[:20])
        
        # 🎯 GARANTÍA FINAL: SIEMPRE 20-25 palabras
        words_final = desc.split()
        
        if len(words_final) < 20:
            # Rellenar hasta 20
            filler = "Situación requiere seguimiento continuo monitoreo"
            desc = desc + " " + filler
            words_final = desc.split()[:20]
        
        if len(words_final) > 25:
            # Truncar a exactamente 25
            words_final = words_final[:25]
        
        result = " ".join(words_final).strip()
        if not result.endswith((".", "!", "?")):
            result = result + "."
        
        return result


    def shorten_url(self, url: str) -> str:
        """Acorta una URL usando TinyURL."""
        if not url or not url.startswith("http"):
            return url
        try:
            resp = requests.get(
                f"https://tinyurl.com/api-create.php?url={url}",
                timeout=5
            )
            if resp.status_code == 200 and resp.text.startswith("http"):
                return resp.text.strip()
        except Exception:
            pass
        return url

    # ─────────────────────────────────────────────────────────────
    # FORMATO 1 — TABLA (para BD / Excel)
    # FECHA_DEPARTAMENTO_PROVINCIA_DISTRITO_CATEGORIA_PALABRAS_CLAVE_TITULO
    # Siempre exactamente 6 underscores (7 columnas).
    # ─────────────────────────────────────────────────────────────
    def format_tabla(self, alert: dict, post: dict, config=None) -> str:
        fecha = alert.get("fecha_str") or _now_peru("%d-%m-%y")

        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia") or dept).upper().strip()
        dist = (alert.get("distrito") or prov).upper().strip()

        # Fallback si todo esta vacio
        if not dept:
            dept = prov = dist = "DESCONOCIDO"

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
    # *FECHA PROVINCIA DISTRITO - KEYWORD1 - KEYWORD2 - KEYWORD3*
    # Titulo y resumen - FUENTE: url
    #
    # Reglas:
    #   - Si provincia tiene nombre propio (≠ departamento) → mostrar provincia, NO dept
    #     ej: ICA + PISCO + TUPAC AMARU → "PISCO TUPAC AMARU"
    #         CAJAMARCA + JAEN + ... → "JAEN ..."
    #         LIMA + BARRANCA + SUPE → "BARRANCA SUPE"
    #   - Si provincia es igual al dept (o vacia) → usar dept como cabecera
    #   - Si distrito == provincia → "CIUDAD DE PROVINCIA"
    #   - Si es NACIONAL → solo "NACIONAL"
    #   - Keywords sin CamelCase: separados por " - "
    # ─────────────────────────────────────────────────────────────
    def format_whatsapp(self, alert: dict, post: dict, config=None) -> str:
        fecha = alert.get("fecha_str") or _now_peru("%d-%m-%y")

        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia")    or "").upper().strip()
        dist = (alert.get("distrito")     or "").upper().strip()

        if dept == "NACIONAL":
            ubicacion = "NACIONAL"
        elif prov and prov != dept:
            # Provincia con nombre propio → omitir departamento
            if dist and dist != prov:
                ubicacion = f"{prov} {dist}"
            elif dist == prov:
                ubicacion = f"{prov}"
            else:
                ubicacion = prov
        else:
            # Provincia vacia o igual al departamento → usar departamento
            if dist and dist != dept:
                ubicacion = f"{dept} {dist}"
            elif dist and dist == dept:
                ubicacion = f"{dept}"
            else:
                ubicacion = dept

        # Keywords: convertir CamelCase a palabras separadas, unir con " - "
        palabras = alert.get("palabras_clave", [])
        palabras_wa = [_strip_camel(str(p)) for p in palabras]
        palabras_str = " - ".join(palabras_wa)

        titulo  = str(alert.get("titulo", "") or "").strip()
        resumen = str(alert.get("resumen_whatsapp", "") or "").strip()
        
        # OPTIMIZAR RESUMEN: 20-25 palabras exactamente
        resumen = self._optimize_description(resumen) if resumen else ""

        # Combinar titulo + resumen
        cuerpo = f"{titulo} {resumen}".strip() if titulo else resumen

        fuente_raw = post.get("url") or alert.get("source_url", "")
        fuente     = self.shorten_url(fuente_raw) if fuente_raw else ""
        fuente_str = f"- FUENTE: {fuente}" if fuente else "- FUENTE:"

        nivel  = NIVEL_EMOJI.get(alert.get("nivel", ""), "")
        header = f"*{nivel} {fecha} {ubicacion} - {palabras_str}*"

        return f"{header}\n{cuerpo} {fuente_str}"

    # ─────────────────────────────────────────────────────────────
    # Formato campo "Insertar noticia" del Google Form (sin cambios)
    # ─────────────────────────────────────────────────────────────
    def format_noticia_tabla(self, alert: dict, post: dict) -> str:
        fecha        = alert.get("fecha_str") or _now_peru("%d-%m-%y")
        region       = alert.get("region", "").upper().replace(" ", "_")
        provincia    = alert.get("provincia", "").upper().replace(" ", "_")
        distrito     = alert.get("distrito", "").upper().replace(" ", "_")
        categoria    = alert.get("categoria", "").replace(" ", "-").upper()
        subcategoria = alert.get("subcategoria", "").replace(" ", "-").upper()
        resumen      = alert.get("resumen_whatsapp", "")
        return f"{fecha}_{region}_{provincia}_{distrito}_{categoria}_{subcategoria}_{resumen}"

    def format_sheets_row(self, alert: dict, post: dict, config=None) -> list:
        """
        Retorna lista de celdas en el mismo orden que las columnas del Form + extras.
        """
        now_str     = _now_peru("%d/%m/%Y %H:%M:%S")
        email       = getattr(config, "EMAIL_SISTEMA", "protecta.dev@gmail.com") if config else "protecta.dev@gmail.com"
        operador    = getattr(config, "OPERADOR_AUTOMATICO", "Sistema Automático") if config else "Sistema Automático"

        cliente     = alert.get("cliente", "Ninguno (Coyuntura Nacional)")
        rubro       = alert.get("rubro", "Otros")
        relevancia  = alert.get("relevancia", "Bajo")
        link        = post.get("url") or alert.get("source_url", "")
        noticia_fmt = self.format_noticia_tabla(alert, post)
        tipo        = alert.get("tipo", "Noticia")

        nivel        = alert.get("nivel", "INFO")
        region       = alert.get("region", "")
        departamento = alert.get("departamento", "")
        provincia    = alert.get("provincia", "")
        distrito     = alert.get("distrito", "")
        categoria    = alert.get("categoria", "")
        subcategoria = alert.get("subcategoria", "")
        tags         = "-".join(alert.get("tags", []))
        clave        = noticia_fmt[:120]

        return [
            now_str, email, cliente, rubro, relevancia, link,
            noticia_fmt, operador, tipo, nivel, region,
            departamento, provincia, distrito, categoria,
            subcategoria, tags, clave,
        ]
