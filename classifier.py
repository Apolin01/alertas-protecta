"""
classifier.py — Clasifica posts con IA.
Soporta: Groq, Gemini, Claude, OpenRouter.
"""

import json
import logging
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
    departamento = (alert.get("departamento") or "").upper().strip()
    if "LIMA" not in departamento:
        return True
    provincia = (alert.get("provincia") or "").upper().strip()
    region    = (alert.get("region") or "").upper().strip()
    for zona in LIMA_PROVINCIAS_OK:
        if zona in provincia or zona in region:
            return True
    log.info(
        f"Filtro Lima: descartando Lima sin provincia de operacion "
        f"(provincia='{provincia}', region='{region}')"
    )
    return False


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
    # ICA tiene multiples clientes, la IA decide
}

def fix_client_by_dept(alert: dict) -> dict:
    """
    Correccion dura: si el departamento tiene un cliente unico conocido
    y la IA puso otro, lo corregimos.
    Tambien limpia campos vacios con texto tipo NO ESPECIFICA.
    """
    departamento = (alert.get("departamento") or "").upper().strip()

    # Limpiar campos con texto NO ESPECIFICA / NO ESPECIFICADO / DESCONOCIDO
    for campo in ["provincia", "distrito", "region"]:
        val = (alert.get(campo) or "").upper().strip()
        if any(x in val for x in ["NO ESPECIF", "DESCONOC", "NO INDICA", "NO MENC"]):
            alert[campo] = ""

    # Si no hay departamento claro → IGNORAR
    if not departamento or any(x in departamento for x in [
        "NO ESPECIF", "DESCONOC", "NACIONAL", "NO INDICA"
    ]):
        # Solo ignorar si el cliente tampoco es Coyuntura
        if alert.get("cliente") not in ["Ninguno (Coyuntura Nacional)"]:
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
SYSTEM_PROMPT = """
Eres un clasificador y formateador de alertas para el equipo de inteligencia operacional de Protecta Peru.
Analizas publicaciones de Facebook, clasificas su relevancia operacional y generas los metadatos
necesarios para dos formatos de publicacion: tabla de base de datos y mensaje de WhatsApp.

Responde SOLO con JSON valido (sin markdown, sin texto extra):

{
  "nivel": "CRIT" | "ALRT" | "INFO" | "IGNORAR",
  "cliente": "<cliente valido>",
  "rubro": "No es un rubro" | "Agroindustria" | "Hidrocarburos" | "Mineria" | "Pesca" | "Otros",
  "relevancia": "Alto" | "Medio" | "Bajo",
  "tipo": "Noticia" | "Incidente",
  "region": "<DEPARTAMENTO, o DEPARTAMENTO PROVINCIA si hay provincia>",
  "departamento": "<MAYUSCULAS SIN TILDES. Si alcance nacional: NACIONAL. Vacio solo si totalmente desconocido>",
  "provincia":   "<MAYUSCULAS SIN TILDES. Si no se menciona: mismo que departamento. Si nacional: NACIONAL>",
  "distrito":    "<MAYUSCULAS SIN TILDES. Si no se menciona: mismo que provincia. Si nacional: vacio ''>",
  "fecha_str": "<DD-MM-AA>",
  "categoria": "<una de las 6 categorias validas, ver lista>",
  "palabras_clave": ["<max 3 keywords, ver reglas de formato>"],
  "titulo": "<titular segun reglas>",
  "resumen_whatsapp": "<max 2 oraciones de resumen, estilo telegrama, sin emojis>",
  "subcategoria": "<MAYUSCULAS-CON-GUIONES>",
  "tags": ["PALABRAS", "CLAVE"]
}

═══════════════════════════════════════════════
CATEGORIAS VALIDAS — usar EXACTAMENTE estos nombres (sin variaciones):

  "Agro-Agua-Medioambiente"       → agro, agua, medioambiente, inundaciones, sismos, empresas agroindustriales
  "Coyuntura Social"              → conflictos sociales, reclamos, denuncias, accidentes de transito, conflictos laborales, festividades
  "Coyuntura Politica"            → funcionarios publicos, instituciones, corrupcion, politica regional o nacional
  "Economia-Desarrollo"           → obras de infraestructura, indicadores economicos, inversiones, nuevos proyectos
  "Protestas, Paros y Bloqueos"   → protestas, paros, bloqueos, huelgas
  "Seguridad y delincuencia"      → detenciones, bandas, robos, homicidios, extorsion, violencia, balaceras

═══════════════════════════════════════════════
REGLAS PARA palabras_clave (MAXIMO 3):

  Etiquetas preferentes — usar si aplica al contexto:
    DETENCION, HOMICIDIO, SEGURIDAD, AGRO, AGRICULTORES, AGUA, MEDIOAMBIENTE,
    SOCIAL, POLITICA, SALUD, DENGUE, FENOMENO DEL NINO, ECONOMIA, EXPORTACIONES

  Reglas de formato y contenido:
    - Palabras de un solo termino: MAYUSCULAS normales  →  HOMICIDIO, AGUA, SEGURIDAD
    - Palabras compuestas o frases: CamelCase            →  POZODeAgua, ObrasPorImpuesto, NuevosRiegos
    - Nombres de personas: CamelCase                     →  JorgeHurtado, CarlosZegarra, LuzCanales
    - En vez de ASESINATO usar siempre                   →  HOMICIDIO
    - En homicidios NO incluir nombre de victimas
    - Conflicto laboral: LABORAL + nombre del sindicato (SUTEP, CGTP, FETSA) o SUNAFIL si se menciona
    - AGRO = agroindustria en general; AGRICULTORES = pequeños productores con dificultades economicas
    - Incluir nombre del CLIENTE si la noticia ocurre en su zona o lo mencionan:
        Mineria: ANTAMINA, YANACOCHA, NEWMONT, BECHTEL, CONGA
        Agro Sur (ICA/Arequipa): ATHOS, CHAPI, AGROKASA, RIACHUELO, SAFRESCO, SAFCO,
            FAMILY-FARMS, SUN-FRUITS, VANGUARD, RVR, UVICA, CAMPOS-DEL-SUR, DON-LUIS, DON-RICARDO
        Agro Norte (La Libertad/costa): CASA-GRANDE, DANPER, MISSION, HORTIFRUT, GREEN-PERU,
            HASS, CAMPOSOL, GIDDINGS, TALSA, WESTFALIA, LAREDO, ADAS, CAMPO-ANDINO
        Otros: PETROTAL, AGRICOLA-SANTA-AZUL
    - Incluir abreviaciones si se nombran explicitamente en el texto:
        CODEHICA, CNDDHH, SEDYS, FETSA, CAMPOSOL, SITECASA-CAMPOSOL,
        CNUL, CPUL-ICA, STCCI, SUTEP, CGTP, TUAGRAP

═══════════════════════════════════════════════
REGLAS PARA titulo:

  - Una sola oracion descriptiva, estilo titular de periodico
  - Solo primera letra de la oracion en mayuscula + nombres propios
  - PROHIBIDO CamelCase: "Buscan mineros perdidos" CORRECTO; "BuscanMinerosPerdidos" INCORRECTO
  - PROHIBIDO todo en mayusculas: "BUSCAN MINEROS PERDIDOS" INCORRECTO
  - PROHIBIDO estos caracteres: : ; ! ?
  - NO incluir fecha formato DD-MM-AA salvo que aparezca textualmente en el titular original
  - Ejemplos correctos: "Buscan mineros perdidos en la sierra", "Asaltan a familia en Viru",
                        "Regidora pierde dedo tras agresion", "Choque de camion y combi en via"

═══════════════════════════════════════════════
REGLA 1 — UBICACION SIN TILDES:
  departamento, provincia y distrito NUNCA llevan tildes ni caracteres especiales.
  ANCASH no ANCASH con tilde. PERU no PERU con tilde. HUANUCO no HUANUCO con tilde.
  NUNCA escribir "NO ESPECIFICA", "DESCONOCIDO", "NO INDICA" ni similar.

  Si se desconoce provincia  → usar mismo nombre que departamento.
  Si se desconoce distrito   → usar mismo nombre que provincia.
  Si la noticia cubre MAS DE UN DEPARTAMENTO o es de alcance nacional:
    departamento = "NACIONAL", provincia = "NACIONAL", distrito = ""

═══════════════════════════════════════════════
REGLA 2 — UBICACION MANDA, NO LA FUENTE:
  La pagina que publica NO determina el cliente ni la region.
  Leer el TEXTO completo para encontrar donde ocurrio el hecho.
  Una pagina de Ancash puede publicar noticias de Cajamarca o Lima.
  USA TU CONOCIMIENTO GEOGRAFICO: si el texto menciona una ciudad, provincia
  o distrito, infiere su departamento. Ejemplos:
    Huaraz, Casma, Chimbote, Recuay, Carhuaz, Caraz, Yungay, Huari → ANCASH
    Cajabamba, Celendin, Jaen, Bambamarca, Chota, Hualgayoc → CAJAMARCA
    Tingo Maria, Huanuco ciudad, Leoncio Prado → HUANUCO
    Cerro de Pasco, Oxapampa, Pasco ciudad → PASCO
    Chincha, Nasca, Nazca, Palpa, Pisco ciudad → ICA
    Trujillo, Viru, Chao, Ascope, Otuzco → LA LIBERTAD
    Barranca, Supe, Huaura, Huaral → LIMA (provincia rural)

═══════════════════════════════════════════════
REGLA 3 — DEPARTAMENTOS Y CLIENTES (MAPA FIJO):
  ANCASH, HUANUCO, PASCO → cliente SIEMPRE "Antamina"
  CAJAMARCA              → cliente SIEMPRE "Bechtel / Newmont"  (incluye: Minera Yanacocha, Newmont, proyecto Conga, Gold Fields La Cima)
  LA LIBERTAD            → cliente SIEMPRE "Clientes Norte" — NUNCA "Bechtel / Newmont"
  HUANCAVELICA, JUNIN, AREQUIPA, PUNO, CUSCO → IGNORAR (salvo politica nacional)

═══════════════════════════════════════════════
REGLA 4 — LIMA:
  Solo procesar si menciona EXPLICITAMENTE: BARRANCA, SUPE, HUAURA, HUARAL → "Agricola Santa Azul"
  Lima ciudad / Callao / Lima sin provincia → IGNORAR (salvo politica nacional)

═══════════════════════════════════════════════
REGLA 5 — "Ninguno (Coyuntura Nacional)":
  SOLO para noticias del gobierno central (presidente, congreso, ministerios)
  sin mencionar ninguna region de operacion especifica.
  Si la noticia menciona Ancash    → Antamina, NO Coyuntura Nacional.
  Si la noticia menciona Cajamarca → Bechtel, NO Coyuntura Nacional.

═══════════════════════════════════════════════
REGLA 6 — SIN UBICACION CLARA → IGNORAR:
  Si el texto no menciona ninguna region, departamento ni provincia reconocible
  de las zonas de operacion → IGNORAR. No inventar ubicaciones.

═══════════════════════════════════════════════
NIVELES:
  CRIT    = homicidios, balaceras, denuncias a empresas cliente, bloqueos de operaciones,
            explosivos, derrames, secuestros, feminicidios
  ALRT    = accidentes en vias, huaicos, derrumbes, cortes de via, huelgas,
            incendios, robos a empresas, protestas, detencion de dirigentes
  INFO    = inauguraciones, inversiones, avances de obra, reuniones con comunidades,
            produccion positiva, acuerdos, proyectos, politica regional
  IGNORAR = deportes, farandula, publicidad, eventos sin impacto operacional,
            regiones fuera de zonas de operacion, sin ubicacion clara

═══════════════════════════════════════════════
CLIENTES VALIDOS:
  "Ninguno (Coyuntura Nacional)"  — politica nacional del gobierno central
  "Antamina"           — ANCASH, HUANUCO, PASCO (todas sus provincias)
  "Bechtel / Newmont"  — CAJAMARCA (todas sus provincias); empresas: Minera Yanacocha, Newmont, proyecto Conga, Bechtel
  "Petrotal"           — LORETO, UCAYALI
  "Pisco"              — ICA provincia de Pisco, zona costera pesquera
  "Agricola Santa Azul"— LIMA: BARRANCA, SUPE, HUAURA solamente
  "Agricola Huarmey"   — ANCASH provincia HUARMEY
  "Agricola 3P"        — LA LIBERTAD
  "Agricola Chapi"     — ICA (no Pisco)
  "Campos Andino"      — LA LIBERTAD costa norte
  "Campos del Sur"     — ICA / Arequipa
  "Don Ricardo"        — ICA / Arequipa zona sur
  "Hortifrut"          — LA LIBERTAD costa norte
  "Mission"            — LA LIBERTAD costa norte
  "RVR"                — ICA / Arequipa zona sur
  "SunFruits"          — LA LIBERTAD costa norte
  "Vanguard"           — ICA / La Libertad
  "Uvica"              — ICA zona sur
  "Clientes Sur"       — ICA, Arequipa general
  "Clientes Norte"     — LA LIBERTAD, LAMBAYEQUE, PIURA general

═══════════════════════════════════════════════
REGLA 7 — EMPRESA CLIENTE MENCIONADA DIRECTAMENTE:
  Si el texto nombra EXPLICITAMENTE una empresa cliente → nivel minimo ALRT e incluir en palabras_clave.
  Si hay protesta, bloqueo, accidente o denuncia CONTRA ellas → CRIT.

  MINERIA:
    Antamina     → "ANTAMINA", "COMPANIA MINERA ANTAMINA"
    Yanacocha    → "YANACOCHA", "MINERA YANACOCHA", "NEWMONT", "CONGA", "BECHTEL"

  AGRO SUR (ICA / Arequipa):
    ATHOS, CHAPI, AGROKASA, RIACHUELO, SAFRESCO, SAFCO, FAMILY FARMS,
    SUN FRUITS, VANGUARD, RVR, UVICA, CAMPOS DEL SUR, DON LUIS, DON RICARDO, AGROMIGIVA

  AGRO NORTE (La Libertad / costa norte):
    CASA GRANDE, DANPER, MISSION, HORTIFRUT, GREEN PERU, HASS PERU,
    CAMPOSOL, GIDDINGS, TALSA, WESTFALIA FRUIT, LAREDO, ADAS, CAMPO ANDINO
"""

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

        try:
            if self.provider == "claude":
                raw = self._call_claude(prompt)
            elif self.provider == "gemini":
                raw = self._call_gemini(prompt)
            elif self.provider == "openai":
                raw = self._call_openai(prompt)
            elif self.provider == "openrouter":
                raw = self._call_openrouter(prompt)
            else:
                log.error(f"AI_PROVIDER desconocido: {self.provider}")
                return None

            if not raw:
                return None

            raw   = raw.replace("```json", "").replace("```", "").strip()
            alert = json.loads(raw)

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

            # Correccion dura por departamento + limpiar NO ESPECIFICA
            alert = fix_client_by_dept(alert)

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
        import time as _time
        key   = self.config.OPENAI_API_KEY
        model = getattr(self.config, "OPENAI_MODEL", "gpt-4o-mini")

        if not key:
            log.error("OPENAI_API_KEY no configurado en .env")
            return None

        for attempt in range(4):
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
                    "temperature": 0.1,
                    "max_tokens":  700,
                },
                timeout=30
            )

            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                wait = int(float(retry_after)) + 2 if retry_after else 15 * (attempt + 1)
                log.warning(f"OpenAI rate limit (intento {attempt+1}). Esperando {wait}s...")
                _time.sleep(wait)
            else:
                resp.raise_for_status()

        log.error("OpenAI: reintentos agotados.")
        return None

