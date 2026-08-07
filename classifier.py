"""
classifier.py — Clasifica posts con IA.
Soporta: Groq, Gemini, Claude, OpenRouter.
"""

import json
import logging
import re
import time
import unicodedata
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
    """Filtra alertas de Lima salvo provincias rurales operacionales."""
    departamento = (alert.get("departamento") or "").upper().strip()
    if departamento != "LIMA":
        return True
    provincia = (alert.get("provincia") or "").upper().strip()
    region    = (alert.get("region") or "").upper().strip()
    if provincia in LIMA_PROVINCIAS_OK or region in LIMA_PROVINCIAS_OK:
        return True
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
# ─────────────────────────────────────────────────────────────
CITY_TO_DEPT = {
    "CHIMBOTE": "ANCASH", "HUARAZ": "ANCASH", "CASMA": "ANCASH",
    "CARAZ": "ANCASH", "HUARI": "ANCASH", "HUARMEY": "ANCASH",
    "RECUAY": "ANCASH", "CARHUAZ": "ANCASH", "YUNGAY": "ANCASH",
    "AIJA": "ANCASH", "BOLOGNESI": "ANCASH", "PALLASCA": "ANCASH",
    "POMABAMBA": "ANCASH", "SAN MARCOS": "ANCASH", "CHAVIN": "ANCASH",
    "CATAC": "ANCASH", "SANTA": "ANCASH", "NUEVO CHIMBOTE": "ANCASH",
    "TRUJILLO": "LA LIBERTAD", "VIRU": "LA LIBERTAD", "CHAO": "LA LIBERTAD",
    "ASCOPE": "LA LIBERTAD", "OTUZCO": "LA LIBERTAD", "PATAZ": "LA LIBERTAD",
    "LAREDO": "LA LIBERTAD", "CHEPEN": "LA LIBERTAD", "PACASMAYO": "LA LIBERTAD",
    "SANCHEZ CARRION": "LA LIBERTAD", "HUAMACHUCO": "LA LIBERTAD",
    "CAJABAMBA": "CAJAMARCA", "CELENDIN": "CAJAMARCA", "JAEN": "CAJAMARCA",
    "BAMBAMARCA": "CAJAMARCA", "CHOTA": "CAJAMARCA", "HUALGAYOC": "CAJAMARCA",
    "SAN IGNACIO": "CAJAMARCA", "CUTERVO": "CAJAMARCA",
    "CHINCHA": "ICA", "NASCA": "ICA", "NAZCA": "ICA", "PALPA": "ICA",
    "PISCO": "ICA",
    "BARRANCA": "LIMA", "SUPE": "LIMA", "HUAURA": "LIMA", "HUARAL": "LIMA",
    "HUACHO": "LIMA",
    "TINGO MARIA": "HUANUCO", "LEONCIO PRADO": "HUANUCO",
    "CERRO DE PASCO": "PASCO", "OXAPAMPA": "PASCO",
}


PERU_DEPARTAMENTOS = {
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA",
    "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN",
    "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO", "MADRE DE DIOS",
    "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES",
    "UCAYALI",
}

PROVINCIA_MULTI_CLIENTE_DEPT = {
    "PISCO": "ICA", "CHINCHA": "ICA", "NASCA": "ICA", "NAZCA": "ICA",
    "PALPA": "ICA", "ICA": "ICA",
    "BARRANCA": "LIMA", "SUPE": "LIMA", "HUAURA": "LIMA", "HUARAL": "LIMA",
    "HUARMEY": "ANCASH",
    "SAN MARCOS": "ANCASH",
}


def fix_dept_by_city(alert: dict, config=None) -> dict:
    """Corrige el departamento cuando distrito/provincia identifica una ciudad conocida en otro departamento."""
    prov = (alert.get("provincia") or "").upper().strip()
    dist = (alert.get("distrito")  or "").upper().strip()
    dept_actual = (alert.get("departamento") or "").upper().strip()

    for ciudad in (dist, prov):
        if not ciudad:
            continue
        dept_correcto = CITY_TO_DEPT.get(ciudad)
        if not dept_correcto or dept_correcto == dept_actual:
            continue

        dept_sensible_esperado = PROVINCIA_MULTI_CLIENTE_DEPT.get(ciudad)
        if (
            dept_sensible_esperado
            and dept_actual in PERU_DEPARTAMENTOS
            and dept_actual != dept_sensible_esperado
        ):
            log.warning(
                f"Ciudad '{ciudad}' sugiere departamento '{dept_correcto}' pero la IA "
                f"ya puso '{dept_actual}' (departamento válido) — NO se corrige "
                f"(posible error de extracción en provincia/distrito, no en departamento)"
            )
            continue

        log.info(
            f"Departamento corregido: IA dijo '{dept_actual}' "
            f"pero ciudad '{ciudad}' → '{dept_correcto}'"
        )
        alert["departamento"] = dept_correcto

        dept_prov_dist = getattr(config, "DEPT_PROV_DIST", {}) if config else {}
        provincias_dept = dept_prov_dist.get(dept_correcto, {})
        for prov_real, distritos in provincias_dept.items():
            if ciudad in distritos:
                alert["provincia"] = prov_real
                alert["distrito"] = ciudad
                break
        else:
            alert["provincia"] = ""

        return alert
    return alert


# ─────────────────────────────────────────────────────────────
# MAPA DURO: DEPARTAMENTO → CLIENTE CORRECTO
# ─────────────────────────────────────────────────────────────
DEPT_TO_CLIENT = {
    "ANCASH":        "Antamina",
    "HUANUCO":       "Antamina",
    "PASCO":         "Antamina",
    "CAJAMARCA":     "Bechtel / Newmont",
    "LA LIBERTAD":   "Clientes Norte",
}

ANCASH_AIO_DISTRITOS = {
    "SAN MARCOS", "CHAVIN DE HUANTAR", "HUACHIS", "SAN PEDRO DE CHANA",  # Huari
    "HUALLANCA", "AQUIA", "CHIQUIAN", "CAJACAY", "ANTONIO RAYMONDI",
    "COLQUIOC", "HUAYLLACAYAN",                                          # Bolognesi
    "CATAC", "PAMPAS CHICO", "MARCA", "LLACLLIN", "PARARIN",             # Recuay
}

HUANUCO_AIO_DISTRITOS = {"LLATA"}


# ─────────────────────────────────────────────────────────────
# MAPA DURO: PROVINCIA/DISTRITO → CLIENTE
# ─────────────────────────────────────────────────────────────
PROVINCIA_TO_CLIENT = {
    "PISCO":    "Pisco",
    "CHINCHA":  "Clientes Sur",
    "NASCA":    "Clientes Sur",
    "NAZCA":    "Clientes Sur",
    "PALPA":    "Clientes Sur",
    "ICA":      "Clientes Sur",
    "BARRANCA": "Antamina",
    "HUARMEY":  "Agrícola Huarmey",
}

PROVINCIA_TO_DEPT = PROVINCIA_MULTI_CLIENTE_DEPT

TURISMO_TERMS = {
    "TURISMO", "CATARATA", "CATARATAS", "ECOTURISMO",
    "HOSPEDAJE", "ALOJAMIENTO", "RECREACION", "RECREATIVO",
    "AVENTURA", "TOUR", "TOURS", "ATRACTIVO", "CIRCUITO",
}

EMPLEO_TERMS = {
    "EMPLEO", "TRABAJO", "LABORAL", "RECLUTAMIENTO",
    "POSTULACION", "POSTULA", "VACANTE", "CONTRATACION",
}

AVISO_MUNICIPAL_TERMS = {
    "FESTIVAL", "ANIVERSARIO", "CHARLA", "ESTERILIZACION", "VACUNACION",
    "FERIA", "TALLER", "CONCURSO", "CAPACITACION", "JORNADA", "INFORMATIVA",
    "EMPADRONAMIENTO", "PROFOPRI", "TITULACION-DE-PREDIOS",
    "FESTEJO", "TOROS", "TAURINO", "CORRIDA",
    "RECONOCIMIENTO", "RECONOCIMIENTOS", "HOMENAJE", "TRAYECTORIA",
}

CANDIDATURA_TERMS = {
    "CANDIDATURA", "CANDIDATURAS", "CANDIDATO", "CANDIDATOS",
    "CANDIDATA", "CANDIDATAS", "PRECANDIDATO", "PRECANDIDATA",
    "PRECANDIDATURA", "POSTULANTE", "POSTULANTES", "ELECCIONES",
}

CANDIDATURA_TEXTO_TERMS = (
    "PLAN DE GOBIERNO", "PLAN DE TRABAJO", "PROPUESTA DE GOBIERNO",
    "CANDIDATA A LA ALCALDIA", "CANDIDATO A LA ALCALDIA",
    "CANDIDATA A LA PRESIDENCIA REGIONAL", "CANDIDATO A LA PRESIDENCIA REGIONAL",
)

HOMICIDIO_AFTERMATH_TERMS = (
    "VELORIO", "DESPIDEN", "ENTIERRO", "SEPELIO", "FUNERAL", "ULTIMO ADIOS",
    "PRISION PREVENTIVA", "SENTENCIA", "CONDENA", "JUICIO", "AUDIENCIA",
    "EXIGEN JUSTICIA", "EXIGIENDO JUSTICIA",
)

PRONUNCIAMIENTO_TERMS = (
    "SE PRONUNCIA", "SE PRONUNCIO", "PRONUNCIAMIENTO", "SE REFIRIO",
    "BRINDO DECLARACIONES", "DIO DECLARACIONES", "DECLARACIONES SOBRE",
    "RECONSTRUCCION", "RECONSTRUCCIÓN", "RECONSTRUYEN",
    "INFORMO SOBRE EL CASO", "SE DIRIGIO A LA PRENSA", "CONFERENCIA DE PRENSA",
    "ACLARO SOBRE", "DESCARTO QUE",
)

ABUSO_SEXUAL_TERMS = (
    "ABUSO", "ABUSO SEXUAL", "VIOLACION", "VIOLACIÓN", "AGRESION SEXUAL",
    "AGRESIÓN SEXUAL", "TOCAMIENTOS INDEBIDOS",
)

DETENCION_TERMS = (
    "DETENCION", "DETENCIÓN", "DETENIDO", "DETENIDA", "DETENIDOS", "DETENIDAS",
    "DETIENEN", "DETUVIERON", "CAPTURA", "CAPTURADO", "CAPTURADOS", "CAPTURAN",
    "ARRESTO", "ARRESTADO", "ARRESTADOS", "INTERVENIDO", "INTERVENIDOS",
    "CAE BANDA", "CAYERON", "REQUISITORIADO", "APRESADO", "APREHENDIDO",
)

INVESTIGACION_TERMS = (
    "INVESTIGA", "INVESTIGAN", "INVESTIGACION", "INVESTIGACIÓN",
    "INVESTIGACIONES", "DILIGENCIAS", "DILIGENCIAS PRELIMINARES",
    "PERITAJE", "PERICIA", "INDAGA", "ABRE INVESTIGACION", "FISCALIA INVESTIGA",
)

MUERTE_TERMS = (
    "FALLECE", "FALLECEN", "FALLECIDO", "FALLECIDA", "FALLECIDOS",
    "FALLECIMIENTO", "MUERE", "MUEREN", "MUERTO", "MUERTA", "MUERTOS",
    "MUERTE", "DECESO", "PERDIO LA VIDA", "PIERDE LA VIDA", "VICTIMA MORTAL",
    "VICTIMAS MORTALES", "CADAVER", "OCCISO",
)

MUERTE_CRIT_TERMS = (
    "ASESIN", "SICARI", "HOMICID", "FEMINICID", "CRIMEN", "MATAN A", "MATO A",
    "BALACERA", "BALEADO", "BALEADA", "BALEARON", "DISPAROS", "ARMA DE FUEGO",
    "ACRIBILLADO", "APUNALADO", "APUÑALADO", "DESCUARTIZ",
)

FAUNA_TERMS = (
    "FAUNA", "FAUNA SILVESTRE", "ANIMAL SILVESTRE", "SERFOR",
    "AVISTAMIENTO", "MALTRATO ANIMAL", "RESCATE DE ANIMAL",
    "AVE SILVESTRE", "ESPECIE SILVESTRE",
)

SALUD_ASISTENCIAL_TERMS = (
    "TOMOGRAFIA", "TOMOGRAFÍA", "TOMOGRAFO", "TOMÓGRAFO", "ATENCIONES",
    "CONSULTAS MEDICAS", "PACIENTES ATENDIDOS", "CAMPAÑA DE SALUD",
    "BRIGADA MEDICA", "VACUNACION", "VACUNACIÓN", "DESPISTAJE", "TAMIZAJE",
    "EQUIPAMIENTO MEDICO", "CIRUGIAS", "CIRUGÍAS", "TRASPLANTE",
    "UNIDAD MEDICA", "ATENCION DE URGENCIAS", "ATENCION MEDICA",
    "TOPICO", "POSTA MEDICA", "CENTRO DE SALUD", "SERVICIO DE EMERGENCIA",
    "MEJORA LA ATENCION", "MEJORA ATENCION", "AMBULANCIA",
)

PROGRAMA_MEDIOS_TERMS = (
    "SE ESTRENA", "ESTRENO", "NO TE LO PIERDAS", "NO TE PIERDAS",
    "SINTONIZA", "SIGUE LA TRANSMISION", "EN VIVO POR", "TRANSMISION EN VIVO",
    "NUEVO PROGRAMA", "ESTE DOMINGO EN", "ESTE SABADO EN", "PROXIMO PROGRAMA",
    "INVITADO DE HOY", "ENTREVISTA EXCLUSIVA", "CONDUCE", "EPISODIO",
    "TE ESPERAMOS EN", "SIGUENOS EN", "PODCAST",
)

SALUD_INFRA_TERMS = (
    "OBRA", "OBRAS", "CONSTRUCCION", "CONSTRUCCIÓN", "INFRAESTRUCTURA",
    "AMPLIACION", "AMPLIACIÓN", "PARALIZADA", "PARALIZADO", "EXPEDIENTE TECNICO",
    "LICITACION", "LICITACIÓN", "INVERSION", "INVERSIÓN", "PRESUPUESTO",
    "NUEVO HOSPITAL", "MEJORAMIENTO",
)

PROMOCIONAL_TERMS = {
    "SORTEO", "SORTEOS", "RIFA", "RIFAS", "PREMIACION", "PREMIACIONES",
    "CANJE", "CANJEA", "PARTICIPA-Y-GANA", "PROMOCION", "PROMOCIONES",
}

TRAFICO_TERRENOS_TERMS = (
    "TRAFICANTE", "TRAFICO DE TERRENO", "USURPACION DE TERRENO",
    "INVASION DE TERRENO", "VENTA IRREGULAR DE LOTE",
)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fix_ica_provincia_by_text(alert: dict, texto: str, config) -> dict:
    """Corrige provincia=PISCO cuando el texto original menciona un distrito de otra provincia de Ica."""
    departamento = (alert.get("departamento") or "").upper().strip()
    provincia = (alert.get("provincia") or "").upper().strip()
    if departamento != "ICA" or provincia != "PISCO" or not texto:
        return alert

    ica_provincias = getattr(config, "DEPT_PROV_DIST", {}).get("ICA", {})
    pisco_distritos = set(ica_provincias.get("PISCO", []))
    texto_norm = _strip_accents(texto.upper())

    for otra_provincia, distritos in ica_provincias.items():
        if otra_provincia == "PISCO":
            continue
        for distrito in distritos:
            if len(distrito) < 5 or distrito in pisco_distritos:
                continue
            distrito_norm = _strip_accents(distrito)
            if re.search(rf'\b{re.escape(distrito_norm)}\b', texto_norm):
                log.warning(
                    f"Provincia corregida por texto: IA dijo 'PISCO' pero el texto "
                    f"menciona '{distrito}' (provincia {otra_provincia}) → corrigiendo"
                )
                alert["provincia"] = otra_provincia
                alert["distrito"] = distrito
                cliente_correcto = PROVINCIA_TO_CLIENT.get(otra_provincia)
                if cliente_correcto:
                    alert["cliente"] = cliente_correcto
                return alert
    return alert


DEPARTAMENTOS_SIN_CLIENTE = {"AREQUIPA", "LAMBAYEQUE", "HUANCAVELICA", "JUNIN", "PUNO", "CUSCO"}


def fix_arequipa_block(alert: dict) -> dict:
    """DEPARTAMENTOS_SIN_CLIENTE nunca van a un cliente específico, salvo coyuntura política nacional."""
    dept = (alert.get("departamento") or "").upper().strip()
    if dept not in DEPARTAMENTOS_SIN_CLIENTE:
        return alert

    categoria = (alert.get("categoria") or "").lower()
    es_politica_nacional = "coyuntura politica" in categoria
    cliente = alert.get("cliente", "")

    if es_politica_nacional and cliente == "Ninguno (Coyuntura Nacional)":
        return alert

    log.info(
        f"{dept} bloqueado (sin cliente/zona de operacion): cliente='{cliente}' "
        f"categoria='{categoria}' → IGNORAR"
    )
    alert["nivel"] = "IGNORAR"
    alert["cliente"] = "Ninguno (Coyuntura Nacional)"
    return alert


def fix_client_by_provincia(alert: dict) -> dict:
    """Corrige el cliente cuando la provincia/distrito identifica una zona con cliente específico."""
    departamento = (alert.get("departamento") or "").upper().strip()
    provincia = (alert.get("provincia") or "").upper().strip()
    distrito  = (alert.get("distrito")  or "").upper().strip()

    for zona in (provincia, distrito):
        if not zona:
            continue
        cliente_correcto = PROVINCIA_TO_CLIENT.get(zona)
        if cliente_correcto:
            dept_esperado = PROVINCIA_TO_DEPT.get(zona)
            if (
                dept_esperado
                and departamento in PERU_DEPARTAMENTOS
                and departamento != dept_esperado
            ):
                log.warning(
                    f"Provincia '{zona}' → cliente '{cliente_correcto}' IGNORADO: "
                    f"departamento IA='{departamento}' no coincide con el esperado "
                    f"'{dept_esperado}' (posible error de extracción de la IA)"
                )
                continue
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
    """Corrige el cliente por departamento, limpia campos vacíos, e ignora CRIT/ALRT sin ubicación granular."""
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

    if nivel in ("CRIT", "ALRT") and not es_politica:
        if not departamento or "NACIONAL" in departamento or any(
            x in departamento for x in ["NO ESPECIF", "DESCONOC", "NO INDICA"]
        ):
            log.info(f"{nivel} sin departamento ('{departamento}') no-politico → IGNORAR")
            alert["nivel"] = "IGNORAR"
            return alert
        sin_prov = not provincia or provincia == departamento
        sin_dist = not distrito  or distrito  == provincia or distrito == departamento
        if sin_prov and sin_dist:
            log.info(
                f"{nivel} sin granularidad ({departamento}/{provincia}/{distrito}) → IGNORAR"
            )
            alert["nivel"] = "IGNORAR"
            return alert

    if not departamento or any(x in departamento for x in [
        "NO ESPECIF", "DESCONOC", "NACIONAL", "NO INDICA"
    ]):
        if alert.get("cliente") not in ["Ninguno (Coyuntura Nacional)"] or not es_politica:
            log.info(f"Sin departamento claro ('{departamento}') → forzando IGNORAR")
            alert["nivel"] = "IGNORAR"
        return alert

    correcto = DEPT_TO_CLIENT.get(departamento)
    if correcto:
        if (
            departamento == "ANCASH"
            and provincia != "HUARMEY"
            and distrito != "HUARMEY"
            and distrito not in ANCASH_AIO_DISTRITOS
        ):
            log.info(
                f"Ancash fuera del Área de Influencia Operativa de Antamina "
                f"(provincia='{provincia}' distrito='{distrito}') → IGNORAR"
            )
            alert["nivel"] = "IGNORAR"
            return alert

        if departamento == "HUANUCO" and distrito not in HUANUCO_AIO_DISTRITOS:
            log.info(
                f"Huanuco fuera del Área de Influencia Operativa de Antamina "
                f"(provincia='{provincia}' distrito='{distrito}') → IGNORAR"
            )
            alert["nivel"] = "IGNORAR"
            return alert

        cliente_ia = alert.get("cliente", "")
        if cliente_ia != correcto:
            log.info(
                f"Cliente corregido: IA dijo '{cliente_ia}' "
                f"pero {departamento} → '{correcto}'"
            )
            alert["cliente"] = correcto

    if alert.get("provincia") == "":
        alert["region"] = departamento

    return alert


# ─────────────────────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────────────────────
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

            if not isinstance(alert, dict):
                log.error(f"Respuesta IA no es dict: {type(alert).__name__} | raw: {raw[:200]}")
                return None
            required = ("nivel", "cliente", "departamento", "titulo", "resumen_whatsapp")
            faltantes = [c for c in required if not alert.get(c)]
            if faltantes:
                log.error(f"Campos obligatorios faltantes {faltantes} | raw: {raw[:200]}")
                return None

            kws = alert.get("palabras_clave")
            if not isinstance(kws, list) or len(kws) != 3:
                log.warning(
                    f"palabras_clave inválido (esperaba lista de 3, obtuvo {kws!r}). "
                    "Se rellena/recorta para no romper downstream."
                )
                if not isinstance(kws, list):
                    kws = []
                while len(kws) < 3:
                    kws.append("INFORMACION")
                alert["palabras_clave"] = kws[:3]

            ubic = {
                _strip_accents(str(alert.get(c, "") or "").upper().strip())
                for c in ("departamento", "provincia", "distrito")
            }
            ubic.discard("")
            if ubic:
                limpias = [
                    k for k in alert["palabras_clave"]
                    if _strip_accents(str(k).upper().strip()) not in ubic
                ]
                if len(limpias) != len(alert["palabras_clave"]):
                    log.info(
                        f"Palabras clave con ubicacion removidas: "
                        f"{alert['palabras_clave']} → {limpias}"
                    )
                    for relleno in ("SEGURIDAD", "SOCIAL", "INFORMACION"):
                        if len(limpias) >= 3:
                            break
                        if relleno not in limpias:
                            limpias.append(relleno)
                    alert["palabras_clave"] = limpias[:3]

            if alert.get("nivel") not in ("CRIT", "ALRT", "INFO", "IGNORAR"):
                log.warning(f"Nivel invalido '{alert.get('nivel')}' → INFO")
                alert["nivel"] = "INFO"

            if alert.get("cliente") not in self.config.CLIENTES_VALIDOS:
                log.warning(f"Cliente invalido '{alert.get('cliente')}' → Ninguno")
                alert["cliente"] = "Ninguno (Coyuntura Nacional)"

            if alert.get("rubro") not in self.config.RUBROS_VALIDOS:
                alert["rubro"] = self.config.get_rubro(alert.get("cliente", ""))

            alert = fix_dept_by_city(alert, self.config)

            if not is_lima_valida(alert):
                alert["nivel"]  = "IGNORAR"
                alert["cliente"] = "Ninguno (Coyuntura Nacional)"

            alert = fix_client_by_dept(alert)
            alert = fix_client_by_provincia(alert)
            alert = fix_ica_provincia_by_text(alert, text, self.config)

            alert = fix_arequipa_block(alert)

            dept_check = (alert.get("departamento") or "").upper().strip()
            prov_check = (alert.get("provincia") or "").upper().strip()
            if prov_check == "HUARMEY" and (
                not dept_check or dept_check not in PERU_DEPARTAMENTOS or dept_check == "ANCASH"
            ):
                alert["departamento"] = "ANCASH"
                alert["cliente"] = "Agrícola Huarmey"

            subcateg  = (alert.get("subcategoria") or "").upper()
            kws_upper = {str(k).upper() for k in (alert.get("palabras_clave") or [])}
            texto_completo = _strip_accents(
                f"{alert.get('titulo','')} {alert.get('resumen_whatsapp','')}".upper()
            )
            if any(t in subcateg for t in TURISMO_TERMS) or any(t in kws_upper for t in TURISMO_TERMS):
                log.info(
                    f"Filtro turismo: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if any(t in subcateg for t in PROMOCIONAL_TERMS) or any(t in kws_upper for t in PROMOCIONAL_TERMS):
                log.info(
                    f"Filtro promocional: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if alert.get("nivel") == "INFO" and (
                any(t in subcateg for t in EMPLEO_TERMS) or any(t in kws_upper for t in EMPLEO_TERMS)
            ):
                log.info(
                    f"Filtro empleo: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if alert.get("nivel") == "INFO" and (
                any(t in subcateg for t in AVISO_MUNICIPAL_TERMS) or any(t in kws_upper for t in AVISO_MUNICIPAL_TERMS)
            ):
                log.info(
                    f"Filtro aviso municipal: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            departamento_check = (alert.get("departamento") or "").upper().strip()
            if (
                alert.get("nivel") == "INFO"
                and departamento_check != "NACIONAL"
                and (
                    any(t in subcateg for t in CANDIDATURA_TERMS)
                    or any(t in kws_upper for t in CANDIDATURA_TERMS)
                    or any(t in texto_completo for t in CANDIDATURA_TEXTO_TERMS)
                )
            ):
                log.info(
                    f"Filtro candidatura local: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if (
                alert.get("nivel") in ("CRIT", "INFO")
                and "HOMICID" in (subcateg + " " + " ".join(kws_upper))
                and any(t in texto_completo for t in HOMICIDIO_AFTERMATH_TERMS)
            ):
                log.info(
                    f"Filtro homicidio-aftermath: '{alert.get('titulo')}' → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in PRONUNCIAMIENTO_TERMS
            ) and (
                "HOMICID" in (subcateg + " " + " ".join(kws_upper))
                or any(
                    t in texto_completo or t in subcateg or t in kws_upper
                    for t in MUERTE_TERMS
                )
            ):
                log.info(
                    f"Filtro pronunciamiento/reconstruccion: "
                    f"'{alert.get('titulo')}' → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if alert.get("nivel") == "CRIT" and any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in DETENCION_TERMS
            ):
                log.info(
                    f"Filtro detencion: '{alert.get('titulo')}' → CRIT degradado a ALRT"
                )
                alert["nivel"] = "ALRT"

            if alert.get("nivel") == "CRIT" and any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in INVESTIGACION_TERMS
            ):
                log.info(
                    f"Filtro investigacion: '{alert.get('titulo')}' → CRIT degradado a ALRT"
                )
                alert["nivel"] = "ALRT"

            if alert.get("nivel") == "CRIT" and any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in MUERTE_TERMS
            ) and not any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in MUERTE_CRIT_TERMS
            ):
                log.info(
                    f"Filtro muerte-no-homicidio: '{alert.get('titulo')}' "
                    f"→ CRIT degradado a ALRT"
                )
                alert["nivel"] = "ALRT"

            if any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in FAUNA_TERMS
            ):
                log.info(f"Filtro fauna: '{alert.get('titulo')}' → IGNORAR")
                alert["nivel"] = "IGNORAR"

            if any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in SALUD_ASISTENCIAL_TERMS
            ) and not any(t in texto_completo for t in SALUD_INFRA_TERMS):
                log.info(f"Filtro salud asistencial: '{alert.get('titulo')}' → IGNORAR")
                alert["nivel"] = "IGNORAR"

            if any(
                t in texto_completo or t in subcateg or t in kws_upper
                for t in PROGRAMA_MEDIOS_TERMS
            ):
                log.info(f"Filtro programa/medios: '{alert.get('titulo')}' → IGNORAR")
                alert["nivel"] = "IGNORAR"

            if any(t in subcateg for t in ABUSO_SEXUAL_TERMS) or any(t in kws_upper for t in ABUSO_SEXUAL_TERMS) or any(t in texto_completo for t in ABUSO_SEXUAL_TERMS):
                log.info(
                    f"Filtro abuso/violencia sexual: '{alert.get('titulo')}' → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            if alert.get("nivel") == "INFO" and any(t in texto_completo for t in TRAFICO_TERRENOS_TERMS):
                log.info(
                    f"Filtro trafico de terrenos: '{alert.get('titulo')}' INFO → ALRT"
                )
                alert["nivel"] = "ALRT"

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
                        "response_format": {"type": "json_object"},
                        "temperature": 0,
                        "max_tokens":  1200,
                    },
                    timeout=30
                )
            except requests.exceptions.RequestException as e:
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
                wait = 5 * (attempt + 1)
                log.warning(
                    f"OpenAI {resp.status_code} (transitorio, intento {attempt+1}). Esperando {wait}s..."
                )
                time.sleep(wait)
            else:
                log.error(f"OpenAI error no recuperable {resp.status_code}: {resp.text[:300]}")
                return None

        log.error("OpenAI: reintentos agotados.")
        return None

