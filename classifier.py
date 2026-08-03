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
    "HUACHO": "LIMA",  # capital de la provincia HUAURA — incidente real:
                        # IA dijo "ANCASH HUARI" para una noticia de Huacho.

    # ── HUANUCO ──
    "TINGO MARIA": "HUANUCO", "LEONCIO PRADO": "HUANUCO",
    # ── PASCO ──
    "CERRO DE PASCO": "PASCO", "OXAPAMPA": "PASCO",
}


# Los 25 departamentos + Callao. Se usa como guarda en las provincias
# "sensibles" (ver PROVINCIA_MULTI_CLIENTE abajo) para no dejar que una
# provincia/distrito mal extraído (alucinación de la IA) pise un departamento
# ya válido. Incidente real: la IA puso departamento="PIURA" pero
# distrito="PISCO" (error de extracción) → terminaba enrutado al grupo Pisco.
PERU_DEPARTAMENTOS = {
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA",
    "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN",
    "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO", "MADRE DE DIOS",
    "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES",
    "UCAYALI",
}

# Nombres de provincia/distrito que llevan la guarda de PERU_DEPARTAMENTOS en
# fix_dept_by_city (no se corrige el departamento si el actual ya es OTRO
# departamento peruano válido). Dos motivos para estar aquí:
#   1) Determinan un cliente/grupo propio (ver PROVINCIA_TO_CLIENT más abajo:
#      Pisco, Chincha, Nasca, Palpa, Barranca, Supe, Huaura, Huaral, Huarmey)
#      — un error de extracción aquí manda la alerta al cliente equivocado.
#   2) El nombre es AMBIGUO entre departamentos (ej. "SAN MARCOS" es distrito
#      de ANCASH/Huari Y provincia de CAJAMARCA — incidente real: alerta de
#      San Marcos-Cajamarca terminó enrutada a Antamina en vez de
#      Bechtel/Newmont).
# El resto de ciudades (Chimbote, Trujillo, etc.) NO llevan esta guarda: ahí
# SIEMPRE se confía en la ciudad sobre el departamento, que es el caso que
# esta función corrige originalmente ("Chimbote" puesto en "La Libertad").
PROVINCIA_MULTI_CLIENTE_DEPT = {
    "PISCO": "ICA", "CHINCHA": "ICA", "NASCA": "ICA", "NAZCA": "ICA",
    "PALPA": "ICA", "ICA": "ICA",
    "BARRANCA": "LIMA", "SUPE": "LIMA", "HUAURA": "LIMA", "HUARAL": "LIMA",
    "HUARMEY": "ANCASH",
    "SAN MARCOS": "ANCASH",  # ambiguo: tambien es provincia de CAJAMARCA
}


def fix_dept_by_city(alert: dict, config=None) -> dict:
    """
    Si distrito/provincia es una ciudad conocida pero el departamento de la IA
    no coincide, se fuerza el departamento correcto. Corrige errores como
    "CHIMBOTE en LA LIBERTAD" → "CHIMBOTE en ANCASH".

    Excepción: si la ciudad es una provincia "multi-cliente" (PISCO, HUARMEY,
    etc. — ver PROVINCIA_MULTI_CLIENTE_DEPT) Y el departamento actual ya es
    OTRO departamento peruano reconocido, no se corrige — es más probable que
    el error esté en provincia/distrito que en departamento, y forzar el
    cambio causaría un enrutamiento equivocado (ver incidente PIURA→PISCO).
    """
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

        # La provincia vieja (del departamento incorrecto) ya no tiene sentido
        # bajo el departamento corregido — sin esto, ej. "HUACHO" corregia
        # departamento a LIMA pero dejaba provincia="HUARI" (de Ancash), y el
        # cliente nunca se recalculaba bien. Se busca en DEPT_PROV_DIST la
        # provincia real que contiene a "ciudad" como distrito.
        dept_prov_dist = getattr(config, "DEPT_PROV_DIST", {}) if config else {}
        provincias_dept = dept_prov_dist.get(dept_correcto, {})
        for prov_real, distritos in provincias_dept.items():
            if ciudad in distritos:
                alert["provincia"] = prov_real
                alert["distrito"] = ciudad
                break
        else:
            # No se encontro una provincia especifica — limpiar la vieja para
            # no dejar una combinacion invalida (provincia de otro departamento).
            alert["provincia"] = ""

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
    "LA LIBERTAD":   "Clientes Norte",   # Trujillo, Virú, Pataz → NUNCA Bechtel
    # ICA tiene multiples clientes, ver PROVINCIA_TO_CLIENT
    # LORETO/UCAYALI (antes "Petrotal") — cliente eliminado a pedido: el grupo
    # de WhatsApp "Petrotal" no existe/no está conectado (193 envíos fallidos
    # en logs). Ya no se clasifican noticias de esos departamentos hacia
    # ningún cliente específico.
}

# Área de Influencia Operativa (AIO) oficial de Antamina en ANCASH — mapa de
# la empresa (Mina San Marcos, Huallanca, Valle Fortaleza, Huarmey). Antamina
# SOLO recibe alertas de estos distritos especificos, NO de todo Ancash (antes
# se enrutaba cualquier noticia de Ancash a Antamina, generando mucho ruido de
# zonas sin relacion — ej. Huaraz ciudad, Casma, Chimbote). HUARMEY no esta
# en esta lista porque ya tiene su propio cliente ("Agrícola Huarmey", ver
# PROVINCIA_TO_CLIENT) — se maneja aparte. Barranca/Paramonga aparece en el
# mapa oficial de Antamina pero se EXCLUYE a proposito: esa zona ya pertenece
# a "Agrícola Santa Azul" (LIMA, ver PROVINCIA_TO_CLIENT) para este sistema.
ANCASH_AIO_DISTRITOS = {
    "SAN MARCOS", "CHAVIN DE HUANTAR", "HUACHIS", "SAN PEDRO DE CHANA",  # Huari
    "HUALLANCA", "AQUIA", "CHIQUIAN", "CAJACAY", "ANTONIO RAYMONDI",
    "COLQUIOC", "HUAYLLACAYAN",                                          # Bolognesi
    "CATAC", "PAMPAS CHICO", "MARCA", "LLACLLIN", "PARARIN",             # Recuay
}

# Área de Influencia Operativa de Antamina en HUANUCO — mismo criterio que
# ANCASH_AIO_DISTRITOS: solo este distrito, no todo Huanuco.
HUANUCO_AIO_DISTRITOS = {"LLATA"}


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

# Departamento real de cada provincia de PROVINCIA_TO_CLIENT. Reutiliza
# PROVINCIA_MULTI_CLIENTE_DEPT (definido arriba, junto a fix_dept_by_city) para
# no duplicar la lista — sirve de guarda: si la IA puso un departamento
# distinto y válido (ej. "PIURA"), una provincia mal extraída ("PISCO") NO
# debe reenrutar la alerta al grupo equivocado.
PROVINCIA_TO_DEPT = PROVINCIA_MULTI_CLIENTE_DEPT

# Términos que indican contenido turístico/recreativo sin impacto operacional.
# Se buscan en subcategoria y palabras_clave tras la clasificación IA.
TURISMO_TERMS = {
    "TURISMO", "CATARATA", "CATARATAS", "ECOTURISMO",
    "HOSPEDAJE", "ALOJAMIENTO", "RECREACION", "RECREATIVO",
    "AVENTURA", "TOUR", "TOURS", "ATRACTIVO", "CIRCUITO",
}

# Términos que indican convocatorias/avisos de empleo sin impacto operacional.
# Se buscan en subcategoria y palabras_clave SOLO cuando nivel == INFO, para no
# bloquear accidentes laborales (CRIT/ALRT) ni huelgas/protestas por derechos laborales.
EMPLEO_TERMS = {
    "EMPLEO", "TRABAJO", "LABORAL", "RECLUTAMIENTO",
    "POSTULACION", "POSTULA", "VACANTE", "CONTRATACION",
}

# Términos que indican avisos municipales / eventos comunitarios sin conflicto
# social ni impacto operacional (festivales, campañas de salud/mascotas, charlas
# informativas, ferias, talleres). Se buscan en subcategoria y palabras_clave SOLO
# cuando nivel == INFO, para no bloquear denuncias, protestas o emergencias reales.
AVISO_MUNICIPAL_TERMS = {
    "FESTIVAL", "ANIVERSARIO", "CHARLA", "ESTERILIZACION", "VACUNACION",
    "FERIA", "TALLER", "CONCURSO", "CAPACITACION", "JORNADA", "INFORMATIVA",
    "EMPADRONAMIENTO", "PROFOPRI", "TITULACION-DE-PREDIOS",
    "FESTEJO", "TOROS", "TAURINO", "CORRIDA",
    "RECONOCIMIENTO", "RECONOCIMIENTOS", "HOMENAJE", "TRAYECTORIA",
}

# Términos que indican promoción personal de candidatura LOCAL/REGIONAL
# (autopromoción de campaña, discursos, presentaciones). Red de seguridad
# porque el prompt (REGLA 10) no siempre lo filtra de forma consistente —
# se vio en logs alertas de candidatos a alcaldía enviadas como INFO pese a
# la regla. NO se aplica si departamento="NACIONAL": ahí manda REGLA 0
# (cobertura de elecciones generales/presidenciales SIEMPRE es INFO minimo).
CANDIDATURA_TERMS = {
    "CANDIDATURA", "CANDIDATURAS", "CANDIDATO", "CANDIDATOS",
    "CANDIDATA", "CANDIDATAS", "PRECANDIDATO", "PRECANDIDATA",
    "PRECANDIDATURA", "POSTULANTE", "POSTULANTES", "ELECCIONES",
}

# Frases que indican autopromoción de campaña en el TEXTO (titulo+resumen),
# no solo en subcategoria/palabras_clave — ej. "Jacky Olivera presenta su
# plan de gobierno 2027-2030" tenia subcategoria/keywords genericas
# (INCLUSION, DESARROLLO) que CANDIDATURA_TERMS no detectaba.
CANDIDATURA_TEXTO_TERMS = (
    "PLAN DE GOBIERNO", "PLAN DE TRABAJO", "PROPUESTA DE GOBIERNO",
    "CANDIDATA A LA ALCALDIA", "CANDIDATO A LA ALCALDIA",
    "CANDIDATA A LA PRESIDENCIA REGIONAL", "CANDIDATO A LA PRESIDENCIA REGIONAL",
)

# Términos que indican SEGUIMIENTO/aftermath de un homicidio (velorio, entierro,
# proceso judicial) en vez del hecho mismo ocurriendo — ver REGLA 10 del prompt:
# solo el hecho es CRIT. El seguimiento posterior (velorios, prisión preventiva,
# sentencias) no es urgente NI relevante para el sistema → IGNORAR directo, no
# solo bajar de nivel. Red de seguridad porque el prompt no siempre lo respeta.
HOMICIDIO_AFTERMATH_TERMS = (
    "VELORIO", "DESPIDEN", "ENTIERRO", "SEPELIO", "FUNERAL", "ULTIMO ADIOS",
    "PRISION PREVENTIVA", "SENTENCIA", "CONDENA", "JUICIO", "AUDIENCIA",
    "EXIGEN JUSTICIA", "EXIGIENDO JUSTICIA",
)

# Términos de abuso/violencia sexual — SIEMPRE fuera de alcance (ver REGLA 10),
# incluso si aparecen junto a un delito que normalmente SI se considera (ej.
# "robo y abuso a menores"): la presencia de abuso/violacion saca la noticia
# de alcance por completo, no solo se ajusta el nivel.
ABUSO_SEXUAL_TERMS = (
    "ABUSO", "ABUSO SEXUAL", "VIOLACION", "VIOLACIÓN", "AGRESION SEXUAL",
    "AGRESIÓN SEXUAL", "TOCAMIENTOS INDEBIDOS",
)

# Términos que indican promociones/sorteos/campañas comerciales — publicidad,
# no noticia. Ej.: "Hidrandina lanza campaña para premiar a clientes puntuales
# con electrodomésticos y canastas de víveres".
PROMOCIONAL_TERMS = {
    "SORTEO", "SORTEOS", "RIFA", "RIFAS", "PREMIACION", "PREMIACIONES",
    "CANJE", "CANJEA", "PARTICIPA-Y-GANA", "PROMOCION", "PROMOCIONES",
}

# Términos que indican trafico/usurpación de terrenos — riesgo social para zonas
# agricolas/operativas cercanas, aunque la noticia se enfoque en un funcionario o
# excandidato. Se buscan en titulo + resumen (sin tildes). Si la IA clasificó como
# INFO, se eleva a ALRT (nunca se bajan niveles ya asignados como CRIT/ALRT).
TRAFICO_TERRENOS_TERMS = (
    "TRAFICANTE", "TRAFICO DE TERRENO", "USURPACION DE TERRENO",
    "INVASION DE TERRENO", "VENTA IRREGULAR DE LOTE",
)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fix_ica_provincia_by_text(alert: dict, texto: str, config) -> dict:
    """
    La IA a veces asigna provincia="PISCO" solo porque la fuente es una pagina
    de Pisco (ej. prensadigitalpiscoperu), aunque el texto original mencione un
    distrito de OTRA provincia de Ica. Incidente real: noticia de un suicidio
    en Parcona (distrito de la provincia ICA, NO Pisco) enrutada al grupo Pisco
    porque la IA puso provincia=PISCO y distrito=PISCO por defecto.

    Busca en el texto original un distrito conocido de las otras provincias de
    Ica (Ica, Chincha, Nazca, Palpa) que no pertenezca tambien a Pisco, y si lo
    encuentra, corrige provincia/distrito/cliente segun ese distrito real.
    """
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
            # Evitar nombres cortos/ambiguos (ej. "TATE") que puedan dar falsos positivos
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


# Departamentos SIN cliente/zona de operacion — la IA a veces les asigna un
# cliente valido igual (ej. Lambayeque → "Clientes Norte", por cercania a La
# Libertad) aunque no esten en DEPT_TO_CLIENT ni PROVINCIA_TO_CLIENT. Estos
# departamentos NUNCA deben ir a un cliente especifico.
DEPARTAMENTOS_SIN_CLIENTE = {"AREQUIPA", "LAMBAYEQUE", "HUANCAVELICA", "JUNIN", "PUNO", "CUSCO"}


def fix_arequipa_block(alert: dict) -> dict:
    """
    REGLA DURA: los DEPARTAMENTOS_SIN_CLIENTE (Arequipa, Lambayeque,
    Huancavelica, Junin, Puno, Cusco) NUNCA van a un cliente especifico —
    ni Antamina, ni Clientes Sur/Norte, ni ningun cliente agro. Unica
    excepcion: coyuntura politica nacional (presidente, congreso, candidatos)
    → 'Ninguno (Coyuntura Nacional)'. Cualquier otra cosa → IGNORAR.
    Motivos: incidente 30-05-26 con noticia de Keiko Fujimori (Arequipa)
    enviada a grupo agro sur; incidente con noticia de Lambayeque enviada a
    Clientes Norte pese a no ser zona de operacion de Agro Norte.
    """
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
    """
    Corrige el cliente cuando la provincia/distrito identifica una zona
    con cliente especifico (mas granular que el mapa por departamento).
    Ej.: provincia CHINCHA → "Clientes Sur" aunque la IA haya dicho "Pisco".

    Guarda de seguridad: si el departamento ya es uno reconocido (ver
    PERU_DEPARTAMENTOS) y NO es el departamento real de esa provincia
    (PROVINCIA_TO_DEPT), se ignora la coincidencia — es más probable que la
    IA haya extraído mal la provincia/distrito que el departamento. Sin esto,
    una alerta de PIURA con distrito mal extraído como "PISCO" terminaba
    enrutada al grupo de Pisco (Ica) en vez de descartarse/ir a Nacional.
    """
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
        # ANCASH: Antamina solo cubre su Area de Influencia Operativa (ver
        # ANCASH_AIO_DISTRITOS), no todo el departamento. HUARMEY (provincia
        # O distrito — por si la IA solo llena uno de los dos campos) se
        # excluye por completo de este chequeo: tiene su propio cliente y no
        # debe caer en el IGNORAR de Antamina bajo ninguna circunstancia. Se
        # corrige aparte (fix_client_by_provincia / validacion final de
        # HUARMEY en classify).
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

        # HUANUCO: mismo criterio, Antamina solo cubre LLATA (ver HUANUCO_AIO_DISTRITOS).
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

            # Validar nivel — la IA a veces devuelve basura aca (ej. confundio el
            # campo y puso el mismo texto que "cliente"). Sin esto, un nivel
            # invalido pasa silencioso hasta el formateo del WhatsApp, donde
            # NIVEL_EMOJI no lo encuentra y deja el emoji/nivel vacio en el header.
            if alert.get("nivel") not in ("CRIT", "ALRT", "INFO", "IGNORAR"):
                log.warning(f"Nivel invalido '{alert.get('nivel')}' → INFO")
                alert["nivel"] = "INFO"

            # Validar cliente
            if alert.get("cliente") not in self.config.CLIENTES_VALIDOS:
                log.warning(f"Cliente invalido '{alert.get('cliente')}' → Ninguno")
                alert["cliente"] = "Ninguno (Coyuntura Nacional)"

            # Validar rubro
            if alert.get("rubro") not in self.config.RUBROS_VALIDOS:
                alert["rubro"] = self.config.get_rubro(alert.get("cliente", ""))

            # Correccion dura ciudad→departamento (puede cambiar departamento a
            # LIMA, ej. "Huacho" que la IA a veces ubica mal en Ancash) — debe
            # correr ANTES del filtro Lima, para que ese filtro valide el
            # departamento/provincia YA corregidos, no los originales.
            alert = fix_dept_by_city(alert, self.config)

            # Filtro duro Lima
            if not is_lima_valida(alert):
                alert["nivel"]  = "IGNORAR"
                alert["cliente"] = "Ninguno (Coyuntura Nacional)"

            # Correccion dura por departamento + limpiar NO ESPECIFICA + filtro ubicacion
            alert = fix_client_by_dept(alert)
            # Correccion fina por provincia/distrito (mas granular que dept)
            alert = fix_client_by_provincia(alert)
            # Correccion por sesgo de pagina fuente: IA dijo PISCO pero el texto
            # menciona un distrito de otra provincia de Ica (ver caso Parcona)
            alert = fix_ica_provincia_by_text(alert, text, self.config)

            # ⭐ Bloqueo Arequipa — DEBE ser ultimo para que nada lo sobrescriba
            alert = fix_arequipa_block(alert)

            # Validacion final: si provincia es HUARMEY, asegurar ANCASH y cliente correcto.
            # Mismo guard que fix_client_by_provincia: si el departamento ya es OTRO
            # departamento peruano reconocido, no lo pisamos (evita el mismo bug de
            # enrutamiento que PIURA→PISCO, aquí con una provincia mal extraída "HUARMEY").
            dept_check = (alert.get("departamento") or "").upper().strip()
            prov_check = (alert.get("provincia") or "").upper().strip()
            if prov_check == "HUARMEY" and (
                not dept_check or dept_check not in PERU_DEPARTAMENTOS or dept_check == "ANCASH"
            ):
                alert["departamento"] = "ANCASH"
                alert["cliente"] = "Agrícola Huarmey"  # ⭐ Forma canónica de CLIENTES_VALIDOS

            # Filtro duro: contenido turístico/recreativo → siempre IGNORAR
            # Opera como red de seguridad cuando el prompt no bloquea estos casos.
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

            # Filtro duro: promociones/sorteos/campañas comerciales → siempre IGNORAR
            # (publicidad, no noticia — ej. "Hidrandina sortea electrodomésticos").
            if any(t in subcateg for t in PROMOCIONAL_TERMS) or any(t in kws_upper for t in PROMOCIONAL_TERMS):
                log.info(
                    f"Filtro promocional: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            # Filtro duro: convocatorias/avisos de empleo (nivel INFO) → IGNORAR
            # No aplica a CRIT/ALRT para no bloquear accidentes laborales o huelgas.
            if alert.get("nivel") == "INFO" and (
                any(t in subcateg for t in EMPLEO_TERMS) or any(t in kws_upper for t in EMPLEO_TERMS)
            ):
                log.info(
                    f"Filtro empleo: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            # Filtro duro: avisos municipales / eventos comunitarios (nivel INFO) → IGNORAR
            # Festivales, campañas de esterilización/vacunación, charlas informativas,
            # ferias, talleres, etc. sin conflicto social ni impacto operacional.
            if alert.get("nivel") == "INFO" and (
                any(t in subcateg for t in AVISO_MUNICIPAL_TERMS) or any(t in kws_upper for t in AVISO_MUNICIPAL_TERMS)
            ):
                log.info(
                    f"Filtro aviso municipal: subcategoria='{alert.get('subcategoria')}' "
                    f"kws={alert.get('palabras_clave')} → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            # Filtro duro: promoción personal de candidatura LOCAL/REGIONAL (nivel INFO)
            # → IGNORAR. Red de seguridad porque el prompt (REGLA 10) no siempre lo
            # filtra de forma consistente (visto en logs: candidatos a alcaldía
            # enviados como INFO pese a la regla). Chequea subcategoria/keywords Y
            # el texto (titulo+resumen) — algunas notas de campaña usan subcategoria
            # generica ("INCLUSION", "DESARROLLO") sin mencionar "candidato" ahi,
            # pero el texto SI dice "plan de gobierno", etc. NO aplica si
            # departamento=NACIONAL (cobertura de elecciones generales/presidenciales,
            # protegida por REGLA 0).
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

            # Filtro duro: seguimiento/aftermath de un homicidio (velorio, entierro,
            # proceso judicial) en vez del hecho mismo ocurriendo → IGNORAR directo
            # (ni CRIT ni INFO — no es urgente ni relevante). Ver REGLA 10 del prompt.
            if (
                alert.get("nivel") in ("CRIT", "INFO")
                and "HOMICID" in (subcateg + " " + " ".join(kws_upper))
                and any(t in texto_completo for t in HOMICIDIO_AFTERMATH_TERMS)
            ):
                log.info(
                    f"Filtro homicidio-aftermath: '{alert.get('titulo')}' → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            # Filtro duro: abuso/violencia sexual — SIEMPRE fuera de alcance, incluso
            # si viene junto a un delito que normalmente si cuenta (ej. "robo y abuso
            # a menores"). No aplica a INFO puro sin delito de por medio para no
            # bloquear contenido ya filtrado en otro lado; se activa en cualquier nivel.
            if any(t in subcateg for t in ABUSO_SEXUAL_TERMS) or any(t in kws_upper for t in ABUSO_SEXUAL_TERMS) or any(t in texto_completo for t in ABUSO_SEXUAL_TERMS):
                log.info(
                    f"Filtro abuso/violencia sexual: '{alert.get('titulo')}' → IGNORAR"
                )
                alert["nivel"] = "IGNORAR"

            # Filtro duro: trafico/usurpacion de terrenos (nivel INFO) → elevar a ALRT
            # Riesgo social para zonas agricolas/operativas, aunque la noticia se
            # enfoque en un funcionario o excandidato (no se bajan niveles CRIT/ALRT).
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

