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
SYSTEM_PROMPT = """Eres un clasificador de alertas operacionales para Protecta Peru. Analizas posts de Facebook y devuelves SOLO JSON valido (sin markdown, sin texto extra):

{
  "nivel": "CRIT|ALRT|INFO|IGNORAR",
  "cliente": "<cliente valido>",
  "rubro": "No es un rubro|Agroindustria|Hidrocarburos|Mineria|Pesca|Otros",
  "relevancia": "Alto|Medio|Bajo",
  "tipo": "Noticia|Incidente",
  "region": "<DEPARTAMENTO o DEPARTAMENTO PROVINCIA>",
  "departamento": "<MAYUS SIN TILDES. NACIONAL si alcance nacional. Vacio solo si totalmente desconocido>",
  "provincia":   "<MAYUS SIN TILDES. Si no se menciona: mismo que departamento. Si nacional: NACIONAL>",
  "distrito":    "<MAYUS SIN TILDES. Si no se menciona: mismo que provincia. Si nacional: ''>",
  "fecha_str": "<DD-MM-AA>",
  "categoria": "<una de las 6 categorias>",
  "palabras_clave": ["<max 3>"],
  "titulo": "<titular>",
  "resumen_whatsapp": "<max 2 oraciones, telegrama, sin emojis>",
  "subcategoria": "<MAYUSCULAS-CON-GUIONES>",
  "tags": ["PALABRAS","CLAVE"]
}

CATEGORIAS (usar EXACTAMENTE estos nombres):
- Agro-Agua-Medioambiente: agro, agua, medioambiente, inundaciones, sismos, agroindustria
- Coyuntura Social: conflictos sociales, reclamos, denuncias, accidentes transito, conflictos laborales, festividades
- Coyuntura Politica: funcionarios publicos, instituciones, corrupcion, politica regional/nacional
- Economia-Desarrollo: obras infraestructura, indicadores economicos, inversiones, nuevos proyectos
- Protestas, Paros y Bloqueos: protestas, paros, bloqueos, huelgas
- Seguridad y delincuencia: detenciones, bandas, robos, homicidios, extorsion, violencia, balaceras

PALABRAS_CLAVE (MAX 3):
Preferentes (usar si aplica): DETENCION, HOMICIDIO, SEGURIDAD, AGRO, AGRICULTORES, AGUA, MEDIOAMBIENTE, SOCIAL, POLITICA, SALUD, DENGUE, FENOMENO DEL NINO, ECONOMIA, EXPORTACIONES.
- Una palabra: MAYUSCULAS normales (HOMICIDIO, AGUA, SEGURIDAD).
- Compuestas o frases: CamelCase (PozoDeAgua, ObrasPorImpuesto, NuevosRiegos).
- Nombres de personas: CamelCase (JorgeHurtado, CarlosZegarra, LuzCanales).
- Usar HOMICIDIO en lugar de ASESINATO. En homicidios NO incluir nombre de victimas.
- Conflicto laboral: LABORAL + sindicato (SUTEP, CGTP, FETSA) o SUNAFIL si se menciona.
- AGRO = agroindustria; AGRICULTORES = pequenos productores con dificultades economicas.
- Si la noticia ocurre en zona del cliente o lo mencionan, incluir el cliente:
  Mineria: ANTAMINA, YANACOCHA, NEWMONT, BECHTEL, CONGA.
  Agro Sur (ICA/Arequipa): ATHOS, CHAPI, AGROKASA, RIACHUELO, SAFRESCO, SAFCO, FAMILY-FARMS, SUN-FRUITS, VANGUARD, RVR, UVICA, CAMPOS-DEL-SUR, DON-LUIS, DON-RICARDO.
  Agro Norte (La Libertad/costa): CASA-GRANDE, DANPER, MISSION, HORTIFRUT, GREEN-PERU, HASS, CAMPOSOL, GIDDINGS, TALSA, WESTFALIA, LAREDO, ADAS, CAMPO-ANDINO.
  Otros: PETROTAL, AGRICOLA-SANTA-AZUL.
- Abreviaciones si aparecen literalmente en el texto: CODEHICA, CNDDHH, SEDYS, FETSA, CAMPOSOL, SITECASA-CAMPOSOL, CNUL, CPUL-ICA, STCCI, SUTEP, CGTP, TUAGRAP.

TITULO:
- Una oracion estilo titular. Primera letra y nombres propios en mayuscula.
- PROHIBIDO: CamelCase, todo en mayusculas, caracteres : ; ! ?
- NO incluir DD-MM-AA salvo que aparezca literalmente en el titular original.
- Ej: "Buscan mineros perdidos en la sierra", "Asaltan a familia en Viru", "Regidora pierde dedo tras agresion", "Choque de camion y combi en via".

REGLA 1 — UBICACION SIN TILDES en departamento/provincia/distrito. Nunca escribir "NO ESPECIFICA" / "DESCONOCIDO" / "NO INDICA" ni similar.
  Sin provincia → mismo que departamento. Sin distrito → mismo que provincia.
  Multi-departamento o nacional → departamento="NACIONAL", provincia="NACIONAL", distrito="".

REGLA 2 — UBICACION MANDA, NO LA FUENTE. La pagina que publica NO determina cliente ni region. Lee el TEXTO completo. Una pagina de Ancash puede publicar de Cajamarca o Lima. USA CONOCIMIENTO GEOGRAFICO:
  Huaraz, Casma, Chimbote, Recuay, Carhuaz, Caraz, Yungay, Huari → ANCASH.
  Cajabamba, Celendin, Jaen, Bambamarca, Chota, Hualgayoc → CAJAMARCA.
  Tingo Maria, Huanuco ciudad, Leoncio Prado → HUANUCO.
  Cerro de Pasco, Oxapampa, Pasco ciudad → PASCO.
  Chincha, Nasca, Nazca, Palpa, Pisco ciudad → ICA.
  Trujillo, Viru, Chao, Ascope, Otuzco → LA LIBERTAD.
  Barranca, Supe, Huaura, Huaral → LIMA (provincia rural).

REGLA 3 — MAPA FIJO DEPARTAMENTO → CLIENTE:
  ANCASH, HUANUCO, PASCO → "Antamina".
  CAJAMARCA → "Bechtel / Newmont" (incluye Minera Yanacocha, Newmont, Conga, Gold Fields La Cima).
  LA LIBERTAD → "Clientes Norte" (NUNCA "Bechtel / Newmont").
  HUANCAVELICA, JUNIN, AREQUIPA, PUNO, CUSCO → IGNORAR (salvo politica nacional).

REGLA 4 — LIMA: solo procesar si menciona EXPLICITAMENTE BARRANCA, SUPE, HUAURA, HUARAL → "Agricola Santa Azul". Lima ciudad / Callao / Lima sin provincia → IGNORAR (salvo politica nacional).

REGLA 5 — "Ninguno (Coyuntura Nacional)": SOLO para gobierno central (presidente, congreso, ministerios) sin mencionar region de operacion. Si menciona Ancash → Antamina. Si menciona Cajamarca → Bechtel.

REGLA 6 — Sin ubicacion clara reconocible de zonas de operacion → IGNORAR. No inventar ubicaciones.

REGLA 7 — EMPRESA CLIENTE NOMBRADA EXPLICITAMENTE: minimo ALRT y agregar a palabras_clave. Protesta/bloqueo/accidente/denuncia CONTRA ella → CRIT.
  Mineria: ANTAMINA, COMPANIA MINERA ANTAMINA / YANACOCHA, MINERA YANACOCHA, NEWMONT, CONGA, BECHTEL.
  Agro Sur (ICA/Arequipa): ATHOS, CHAPI, AGROKASA, RIACHUELO, SAFRESCO, SAFCO, FAMILY FARMS, SUN FRUITS, VANGUARD, RVR, UVICA, CAMPOS DEL SUR, DON LUIS, DON RICARDO, AGROMIGIVA.
  Agro Norte (La Libertad/costa): CASA GRANDE, DANPER, MISSION, HORTIFRUT, GREEN PERU, HASS PERU, CAMPOSOL, GIDDINGS, TALSA, WESTFALIA FRUIT, LAREDO, ADAS, CAMPO ANDINO.

NIVELES:
- CRIT: homicidios, balaceras, denuncias a empresas cliente, bloqueos de operaciones, explosivos, derrames, secuestros, feminicidios.
- ALRT: accidentes en vias, huaicos, derrumbes, cortes de via, huelgas, incendios, robos a empresas, protestas, detencion de dirigentes.
- INFO: inauguraciones, inversiones, avances de obra, reuniones con comunidades, produccion positiva, acuerdos, proyectos, politica regional.
- IGNORAR: deportes, farandula, publicidad, sin impacto operacional, fuera de zonas de operacion, sin ubicacion clara.

CLIENTES VALIDOS:
"Ninguno (Coyuntura Nacional)" — politica nacional gobierno central.
"Antamina" — ANCASH, HUANUCO
"Bechtel / Newmont" — CAJAMARCA (todas sus provincias). Empresas: Minera Yanacocha, Newmont, Conga, Bechtel.
"Petrotal" — LORETO, UCAYALI.
"Pisco" — ICA provincia Pisco, costera pesquera.
"Agricola Santa Azul" — LIMA: BARRANCA, SUPE, HUAURA solamente.
"Agricola Huarmey" — ANCASH provincia HUARMEY.
"Agricola 3P" — LA LIBERTAD.
"Agricola Chapi" — ICA (no Pisco).
"Campos Andino" — LA LIBERTAD costa norte.
"Campos del Sur" — ICA / Arequipa.
"Don Ricardo" — ICA / Arequipa zona sur.
"Hortifrut" — LA LIBERTAD costa norte.
"Mission" — LA LIBERTAD costa norte.
"RVR" — ICA / Arequipa zona sur.
"SunFruits" — LA LIBERTAD costa norte.
"Vanguard" — ICA / La Libertad.
"Uvica" — ICA zona sur.
"Clientes Sur" — ICA
"Clientes Norte" — LA LIBERTAD
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

