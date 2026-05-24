"""
classifier.py — Clasifica posts con IA.
Soporta: Groq, Gemini, Claude, OpenRouter.
"""

import json
import logging
import time
from pathlib import Path
import requests
from config import Config

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# FILTRO DURO — independiente de la IA
# ─────────────────────────────────────────────────────────────
LIMA_PROVINCIAS_OK = {
    "BARRANCA", "SUPE", "HUAURA", "HUARAL",
}

def is_lima_valida(alert: dict) -> bool:
    """
    Filtra alertas de Lima salvo provincias rurales operacionales.
    Usa igualdad estricta (no substring) para evitar falsos positivos como
    "HUAURA" matcheando "HUAURALA" o "LIMA" matcheando cualquier string que la contenga.
    """
    departamento = (alert.get("departamento") or "").upper().strip()
    # Solo aplicar filtro si dept es exactamente LIMA (no "LIMA NORTE", "METROPOLITANA DE LIMA", etc.)
    if departamento != "LIMA":
        return True
    provincia = (alert.get("provincia") or "").upper().strip()
    region    = (alert.get("region") or "").upper().strip()
    # Igualdad estricta contra el set de provincias permitidas
    if provincia in LIMA_PROVINCIAS_OK or region in LIMA_PROVINCIAS_OK:
        return True
    # Fallback: también aceptar si la región es "LIMA <PROVINCIA>"
    for zona in LIMA_PROVINCIAS_OK:
        if region == f"LIMA {zona}":
            return True
    log.info(
        f"Filtro Lima: descartando Lima sin provincia de operacion "
        f"(provincia='{provincia}', region='{region}')"
    )
    return False


# ─────────────────────────────────────────────────────────────
# MAPA DURO: CIUDAD → DEPARTAMENTO CORRECTO
# Si la IA pone "Chimbote en La Libertad", aqui se corrige.
# Las keys deben estar SIN TILDES y en MAYUSCULAS.
# ─────────────────────────────────────────────────────────────
CITY_TO_DEPT = {
    # ── ANCASH ──
    "CHIMBOTE": "ANCASH", "HUARAZ": "ANCASH", "CASMA": "ANCASH",
    "CARAZ": "ANCASH", "HUARI": "ANCASH", "HUARMEY": "ANCASH",
    "RECUAY": "ANCASH", "CARHUAZ": "ANCASH", "YUNGAY": "ANCASH",
    "AIJA": "ANCASH", "BOLOGNESI": "ANCASH", "PALLASCA": "ANCASH",
    "POMABAMBA": "ANCASH", "SAN MARCOS": "ANCASH", "CHAVIN": "ANCASH",
    "CATAC": "ANCASH", "SANTA": "ANCASH", "NUEVO CHIMBOTE": "ANCASH",
    # ── LA LIBERTAD ──
    "TRUJILLO": "LA LIBERTAD", "VIRU": "LA LIBERTAD", "CHAO": "LA LIBERTAD",
    "ASCOPE": "LA LIBERTAD", "OTUZCO": "LA LIBERTAD", "PATAZ": "LA LIBERTAD",
    "LAREDO": "LA LIBERTAD", "CHEPEN": "LA LIBERTAD", "PACASMAYO": "LA LIBERTAD",
    "SANCHEZ CARRION": "LA LIBERTAD", "HUAMACHUCO": "LA LIBERTAD",
    # ── CAJAMARCA ──
    "CAJABAMBA": "CAJAMARCA", "CELENDIN": "CAJAMARCA", "JAEN": "CAJAMARCA",
    "BAMBAMARCA": "CAJAMARCA", "CHOTA": "CAJAMARCA", "HUALGAYOC": "CAJAMARCA",
    "SAN IGNACIO": "CAJAMARCA", "CUTERVO": "CAJAMARCA",
    # ── ICA ──
    "CHINCHA": "ICA", "NASCA": "ICA", "NAZCA": "ICA", "PALPA": "ICA",
    "PISCO": "ICA",
    # ── LIMA (provincias rurales OK) ──
    "BARRANCA": "LIMA", "SUPE": "LIMA", "HUAURA": "LIMA", "HUARAL": "LIMA",
    # ── HUANUCO ──
    "TINGO MARIA": "HUANUCO", "LEONCIO PRADO": "HUANUCO",
    # ── PASCO ──
    "CERRO DE PASCO": "PASCO", "OXAPAMPA": "PASCO",
}


def fix_dept_by_city(alert: dict) -> dict:
    """
    Si distrito/provincia es una ciudad conocida pero el departamento de la IA
    no coincide, se fuerza el departamento correcto. Corrige errores como
    "CHIMBOTE en LA LIBERTAD" → "CHIMBOTE en ANCASH".
    """
    prov = (alert.get("provincia") or "").upper().strip()
    dist = (alert.get("distrito")  or "").upper().strip()
    dept_actual = (alert.get("departamento") or "").upper().strip()

    for ciudad in (dist, prov):
        if not ciudad:
            continue
        dept_correcto = CITY_TO_DEPT.get(ciudad)
        if dept_correcto and dept_correcto != dept_actual:
            log.info(
                f"Departamento corregido: IA dijo '{dept_actual}' "
                f"pero ciudad '{ciudad}' → '{dept_correcto}'"
            )
            alert["departamento"] = dept_correcto
            return alert
    return alert


# ─────────────────────────────────────────────────────────────
# MAPA DURO: DEPARTAMENTO → CLIENTE CORRECTO
# Si la IA se equivoca, este mapa lo corrige
# ─────────────────────────────────────────────────────────────
DEPT_TO_CLIENT = {
    "ANCASH":        "Antamina",
    "HUANUCO":       "Antamina",
    "PASCO":         "Antamina",
    "CAJAMARCA":     "Bechtel / Newmont",
    "LORETO":        "Petrotal",
    "UCAYALI":       "Petrotal",
    "LA LIBERTAD":   "Clientes Norte",   # Trujillo, Virú, Pataz → NUNCA Bechtel
    # ICA tiene multiples clientes, ver PROVINCIA_TO_CLIENT
}


# ─────────────────────────────────────────────────────────────
# MAPA DURO: PROVINCIA/DISTRITO → CLIENTE (mas granular que DEPT)
# ICA tiene multiples clientes: Pisco va al grupo Pisco; Chincha/Nasca/Palpa/Ica
# van a Clientes Sur. Lima costera (Barranca/Supe/Huaura) → Santa Azul.
# Las keys deben ir SIN TILDES y en MAYUSCULAS.
# ─────────────────────────────────────────────────────────────
PROVINCIA_TO_CLIENT = {
    "PISCO":    "Pisco",
    "CHINCHA":  "Clientes Sur",
    "NASCA":    "Clientes Sur",
    "NAZCA":    "Clientes Sur",
    "PALPA":    "Clientes Sur",
    "ICA":      "Clientes Sur",            # provincia Ica (no la de Pisco)
    "BARRANCA": "Agrícola Santa Azul",
    "SUPE":     "Agrícola Santa Azul",
    "HUAURA":   "Agrícola Santa Azul",
    "HUARAL":   "Agrícola Santa Azul",  # ⭐ Fix #7: HUARAL pasaba filtro Lima pero no tenía cliente
    "HUARMEY":  "Agrícola Huarmey",
}


def fix_client_by_provincia(alert: dict) -> dict:
    """
    Corrige el cliente cuando la provincia/distrito identifica una zona
    con cliente especifico (mas granular que el mapa por departamento).
    Ej.: provincia CHINCHA → "Clientes Sur" aunque la IA haya dicho "Pisco".
    """
    provincia = (alert.get("provincia") or "").upper().strip()
    distrito  = (alert.get("distrito")  or "").upper().strip()

    for zona in (provincia, distrito):
        if not zona:
            continue
        cliente_correcto = PROVINCIA_TO_CLIENT.get(zona)
        if cliente_correcto:
            cliente_actual = alert.get("cliente", "")
            if cliente_actual != cliente_correcto:
                log.info(
                    f"Cliente corregido por provincia: IA dijo '{cliente_actual}' "
                    f"pero '{zona}' → '{cliente_correcto}'"
                )
                alert["cliente"] = cliente_correcto
            return alert
    return alert

def fix_client_by_dept(alert: dict) -> dict:
    """
    Correccion dura: si el departamento tiene un cliente unico conocido
    y la IA puso otro, lo corregimos.
    Tambien limpia campos vacios con texto tipo NO ESPECIFICA.
    Y aplica una regla estricta: CRIT/ALRT sin ubicacion granular → IGNORAR.
    """
    # Limpiar campos con texto NO ESPECIFICA / NO ESPECIFICADO / DESCONOCIDO
    for campo in ["provincia", "distrito", "region"]:
        val = (alert.get(campo) or "").upper().strip()
        if any(x in val for x in ["NO ESPECIF", "DESCONOC", "NO INDICA", "NO MENC"]):
            alert[campo] = ""

    departamento = (alert.get("departamento") or "").upper().strip()
    provincia    = (alert.get("provincia")    or "").upper().strip()
    distrito     = (alert.get("distrito")     or "").upper().strip()
    nivel        = alert.get("nivel", "")
    categoria    = (alert.get("categoria") or "").lower()
    es_politica  = "coyuntura politica" in categoria

    # ── REGLA DE UBICACION OBLIGATORIA ──
    # Cualquier CRIT/ALRT que no sea coyuntura politica nacional, REQUIERE
    # departamento Y al menos provincia o distrito especifico (distinto del dept).
    if nivel in ("CRIT", "ALRT") and not es_politica:
        if not departamento or "NACIONAL" in departamento or any(
            x in departamento for x in ["NO ESPECIF", "DESCONOC", "NO INDICA"]
        ):
            log.info(f"{nivel} sin departamento ('{departamento}') no-politico → IGNORAR")
            alert["nivel"] = "IGNORAR"
            return alert
        # Si solo hay departamento sin granularidad (prov/dist iguales o vacios) → IGNORAR
        sin_prov = not provincia or provincia == departamento
        sin_dist = not distrito  or distrito  == provincia or distrito == departamento
        if sin_prov and sin_dist:
            log.info(
                f"{nivel} sin granularidad ({departamento}/{provincia}/{distrito}) → IGNORAR"
            )
            alert["nivel"] = "IGNORAR"
            return alert

    # Si no hay departamento → IGNORAR salvo coyuntura nacional explicita
    if not departamento or any(x in departamento for x in [
        "NO ESPECIF", "DESCONOC", "NACIONAL", "NO INDICA"
    ]):
        if alert.get("cliente") not in ["Ninguno (Coyuntura Nacional)"] or not es_politica:
            log.info(f"Sin departamento claro ('{departamento}') → forzando IGNORAR")
            alert["nivel"] = "IGNORAR"
        return alert

    # Corregir cliente si el departamento es inequivoco
    correcto = DEPT_TO_CLIENT.get(departamento)
    if correcto:
        cliente_ia = alert.get("cliente", "")
        if cliente_ia != correcto:
            log.info(
                f"Cliente corregido: IA dijo '{cliente_ia}' "
                f"pero {departamento} → '{correcto}'"
            )
            alert["cliente"] = correcto

    # Limpiar region si tiene NO ESPECIFICA
    if alert.get("provincia") == "":
        # region solo con departamento
        alert["region"] = departamento

    return alert


# ─────────────────────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────────────────────
# El SYSTEM_PROMPT se carga desde prompts/classifier_prompt.md
# para versionarlo aparte (git diff legible) y editarlo sin tocar código.
_PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier_prompt.md"
try:
    SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError as _e:
    raise RuntimeError(
        f"No se encontró el prompt en {_PROMPT_PATH}. "
        "Asegúrate de que prompts/classifier_prompt.md existe."
    ) from _e

USER_TEMPLATE = """Clasifica esta publicacion de Facebook.

ATENCION: Determina el cliente por DONDE ocurrio el hecho en el texto,
NO por la pagina que lo publica. La pagina '{source_page}' puede publicar
noticias de cualquier region del Peru.

FECHA: {date}
TEXTO:
{text}
"""


class AlertClassifier:
    def __init__(self, config: Config):
        self.config   = config
        self.provider = getattr(config, "AI_PROVIDER", "groq").lower()

    def classify(self, post: dict) -> dict | None:
        text = post.get("text", "").strip()
        if not text or len(text) < 30:
            return None

        prompt = USER_TEMPLATE.format(
            source_page=post.get("source_page", "Desconocido"),
            date=post.get("date", "desconocida"),
            text=text
        )

        raw = ""
        try:
            if self.provider == "openai":
                raw = self._call_openai(prompt)
            elif self.provider in ("claude", "gemini", "openrouter"):
                log.error(
                    f"AI_PROVIDER '{self.provider}' aún NO implementado. "
                    "Solo 'openai' está disponible. Ajusta AI_PROVIDER en .env."
                )
                return None
            else:
                log.error(f"AI_PROVIDER desconocido: {self.provider}")
                return None

            if not raw:
                return None

            raw   = raw.replace("```json", "").replace("```", "").strip()
            alert = json.loads(raw)

            # ⭐ Fix #11: Validar estructura mínima del JSON
            if not isinstance(alert, dict):
                log.error(f"Respuesta IA no es dict: {type(alert).__name__} | raw: {raw[:200]}")
                return None
            required = ("nivel", "cliente", "departamento", "titulo", "resumen_whatsapp")
            faltantes = [c for c in required if not alert.get(c)]
            if faltantes:
                log.error(f"Campos obligatorios faltantes {faltantes} | raw: {raw[:200]}")
                return None

            # ⭐ Fix #9: Validar palabras_clave (debe ser lista de 3 elementos)
            kws = alert.get("palabras_clave")
            if not isinstance(kws, list) or len(kws) != 3:
                log.warning(
                    f"palabras_clave inválido (esperaba lista de 3, obtuvo {kws!r}). "
                    "Se rellena/recorta para no romper downstream."
                )
                if not isinstance(kws, list):
                    kws = []
                # Rellenar con valores genéricos del rubro si faltan, recortar si sobran
                while len(kws) < 3:
                    kws.append("INFORMACION")
                alert["palabras_clave"] = kws[:3]

            # Validar cliente
            if alert.get("cliente") not in self.config.CLIENTES_VALIDOS:
                log.warning(f"Cliente invalido '{alert.get('cliente')}' → Ninguno")
                alert["cliente"] = "Ninguno (Coyuntura Nacional)"

            # Validar rubro
            if alert.get("rubro") not in self.config.RUBROS_VALIDOS:
                alert["rubro"] = self.config.get_rubro(alert.get("cliente", ""))

            # Filtro duro Lima
            if not is_lima_valida(alert):
                alert["nivel"]  = "IGNORAR"
                alert["cliente"] = "Ninguno (Coyuntura Nacional)"

            # Correccion dura ciudad→departamento ANTES de validar
            alert = fix_dept_by_city(alert)
            # Correccion dura por departamento + limpiar NO ESPECIFICA + filtro ubicacion
            alert = fix_client_by_dept(alert)
            # Correccion fina por provincia/distrito (mas granular que dept) — SIEMPRE ULTIMO
            alert = fix_client_by_provincia(alert)
            
            # Validacion final: si provincia es HUARMEY, asegurar ANCASH y cliente correcto
            prov_check = (alert.get("provincia") or "").upper().strip()
            if prov_check == "HUARMEY":
                alert["departamento"] = "ANCASH"
                alert["cliente"] = "Agrícola Huarmey"  # ⭐ Forma canónica de CLIENTES_VALIDOS

            alert["source_url"]  = post.get("url", "")
            alert["source_page"] = post.get("source_page", "")
            return alert

        except json.JSONDecodeError as e:
            log.error(f"JSON invalido del modelo: {e} | raw: {raw[:300]}")
            return None
        except Exception as e:
            log.error(f"Error en clasificador ({self.provider}): {e}")
            return None

    # ─────────────────────────────────────────────
    # OPENAI
    # ─────────────────────────────────────────────
    def _call_openai(self, prompt: str) -> str | None:
        key   = self.config.OPENAI_API_KEY
        model = getattr(self.config, "OPENAI_MODEL", "gpt-4o-mini")

        if not key:
            log.error("OPENAI_API_KEY no configurado en .env")
            return None

        for attempt in range(4):
            try:
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type":  "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user",   "content": prompt}
                        ],
                        # ⭐ response_format garantiza JSON válido y elimina la necesidad
                        # de limpiar ```json``` o lidiar con texto extra del modelo.
                        "response_format": {"type": "json_object"},
                        # ⭐ temperature=0 para clasificación determinística (reproducible).
                        "temperature": 0,
                        # ⭐ Subido de 700 → 1200: el JSON tiene ~15 campos y resumen de 2 oraciones,
                        # 700 truncaba la respuesta y rompía json.loads.
                        "max_tokens":  1200,
                    },
                    timeout=30
                )
            except requests.exceptions.RequestException as e:
                # Errores de red (timeout, conexión rota) → reintentar con backoff
                wait = 5 * (attempt + 1)
                log.warning(f"OpenAI error de red (intento {attempt+1}): {e}. Esperando {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                wait = (int(float(retry_after)) + 2) if retry_after else 15 * (attempt + 1)
                log.warning(f"OpenAI rate limit (intento {attempt+1}). Esperando {wait}s...")
                time.sleep(wait)
            elif 500 <= resp.status_code < 600:
                # ⭐ Fix #10: Retry para 5xx transitorios (500, 502, 503, 504)
                wait = 5 * (attempt + 1)
                log.warning(
                    f"OpenAI {resp.status_code} (transitorio, intento {attempt+1}). Esperando {wait}s..."
                )
                time.sleep(wait)
            else:
                # 4xx no recuperable (400 bad request, 401 auth, 403 forbidden) → fallar rápido
                log.error(f"OpenAI error no recuperable {resp.status_code}: {resp.text[:300]}")
                return None

        log.error("OpenAI: reintentos agotados.")
        return None

