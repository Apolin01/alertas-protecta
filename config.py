"""
config.py — Configuración del sistema de alertas Protecta Perú.
Coincide exactamente con el Google Form existente (imágenes del formulario).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


class Config:
    # ─────────────────────────────────────────────
    # PROVEEDOR DE IA
    # ─────────────────────────────────────────────
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

    # ── OpenAI ────────────────────────────────────
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL   = "gpt-4o-mini"

    # ─────────────────────────────────────────────
    # RSS FEED CONFIGURATION (rss.app)
    # ─────────────────────────────────────────────
    RSS_API_KEY = os.getenv("RSS_API_KEY", "")
    RSS_API_SECRET = os.getenv("RSS_API_SECRET", "")

    RSS_BUNDLES = {
        "Antamina":                      "_vv3HkItEzKqytLHk",      # Ancash
        "Bechtel / Newmont":             "_dtKCh5CjRws0ai8H",      # Cajamarca
        "Clientes Sur":                  "_vuHd6hNkLlFj0nPK",      # Agro Sur (solo Ica — Arequipa bloqueada, ver fix_arequipa_block)
        "Clientes Norte":                "_i5tst4lPDJ5oTSW4",      # Agro Norte (La Libertad, etc)
        "Pisco":                         "_XgBrvIyMIWm5YzLP",      # Pisco
        "Ninguno (Coyuntura Nacional)":  "_pM02KT2QspbdR8os",      # Coyuntura Nacional
    }

    # ─────────────────────────────────────────────
    # SCHEDULER
    # ─────────────────────────────────────────────
    INTERVAL_MINUTES = 5   # tiempo entre ciclos completos

    # ─────────────────────────────────────────────
    # WHATSAPP BRIDGE (whatsapp-web.js)
    # ─────────────────────────────────────────────
    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "bridge")
    ENABLE_IMAGE_FALLBACK = os.getenv("ENABLE_IMAGE_FALLBACK", "true").lower() == "true"
    BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:3000")
    BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN", "")

    # ─────────────────────────────────────────────
    # ACORTADOR DE LINKS PROPIO (Cloudflare Worker) — ver cloudflare-shortener/
    # ─────────────────────────────────────────────
    SHORTENER_URL   = os.getenv("SHORTENER_URL", "")
    SHORTENER_TOKEN = os.getenv("SHORTENER_TOKEN", "")

    # ─────────────────────────────────────────────
    # GOOGLE SHEETS
    # ─────────────────────────────────────────────
    SHEETS_ENABLED = os.getenv("SHEETS_ENABLED", "false").lower() == "true"
    GOOGLE_CREDENTIALS_FILE = "credentials.json"
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
    SHEET_NAME = "Informacion"
    OPERADOR_AUTOMATICO = "Sistema Automático"
    EMAIL_SISTEMA = "protecta.dev@gmail.com"

    # ─────────────────────────────────────────────
    # CLIENTES VÁLIDOS (dropdown del Form — imagen 2)
    # ─────────────────────────────────────────────
    CLIENTES_VALIDOS = [
        "Ninguno (Coyuntura Nacional)",
        "Clientes Sur",
        "Clientes Norte",
        "Antamina",
        "Pisco",
        "Bechtel / Newmont",
        "Agrícola 3P",
        "Agrícola Chapi",
        "Campos Andino",
        "Campos del Sur",
        "Don Ricardo",
        "Hortifrut",
        "Mission",
        "RVR",
        "SunFruits",
        "Vanguard",
        "Uvica",
    ]

    # ─────────────────────────────────────────────
    # RUBROS (radio buttons — imagen 3)
    # ─────────────────────────────────────────────
    RUBROS_VALIDOS = [
        "No es un rubro",
        "Agroindustria",
        "Hidrocarburos",
        "Minería",
        "Pesca",
        "Otros",
    ]

    # ─────────────────────────────────────────────
    # MAPEO CLIENTE → GRUPO WHATSAPP
    # ─────────────────────────────────────────────
    CLIENTE_TO_WHATSAPP_GROUP = {
        "Antamina":                         "Antamina",
        "Bechtel / Newmont":                "Bechtel / Newmont",
        "Clientes Sur":                     "Clientes Sur",
        "Clientes Norte":                   "Clientes Norte",
        "Agrícola 3P":                      "Clientes Norte",
        "Agrícola Chapi":                   "Clientes Sur",
        "Campos Andino":                    "Clientes Norte",
        "Campos del Sur":                   "Clientes Sur",
        "Don Ricardo":                      "Clientes Sur",
        "Hortifrut":                        "Clientes Norte",
        "Mission":                          "Clientes Norte",
        "RVR":                              "Clientes Sur",
        "SunFruits":                        "Clientes Norte",
        "Vanguard":                         "Clientes Sur",
        "Uvica":                            "Clientes Sur",
        "Pisco":                            "Pisco",
        "Ninguno (Coyuntura Nacional)":     "Coyuntura Nacional",
    }

    # ─────────────────────────────────────────────
    # RUBRO POR CLIENTE (autocompletado)
    # ─────────────────────────────────────────────
    CLIENTE_TO_RUBRO = {
        "Antamina":                         "Minería",
        "Bechtel / Newmont":                "Minería",
        "Pisco":                            "Pesca",
        "Ninguno (Coyuntura Nacional)":     "No es un rubro",
    }

    def get_rubro(self, cliente: str) -> str:
        return self.CLIENTE_TO_RUBRO.get(cliente, "Agroindustria")

    # ─────────────────────────────────────────────
    # MAPEO COMPLETO: DEPARTAMENTO → PROVINCIAS → DISTRITOS
    # Estructura para validar y normalizar ubicaciones
    # ─────────────────────────────────────────────
    DEPT_PROV_DIST = {
        "ANCASH": {
            "HUARAZ": ["HUARAZ", "INDEPENDENCIA", "COCHABAMBA", "COLCABAMBA", "HUANCHAY", "JANGAS", "LA LIBERTAD", "OLLEROS", "PAMPAS GRANDE", "PARIACOTO", "PIRA", "TARICA"],
            "AIJA": ["AIJA", "CORIS", "HUACLLAN", "LA MERCED", "SUCCHA"],
            "ANTONIO RAYMONDI": ["LLAMELLIN", "ACZO", "CHACCHO", "CHINGAS", "MIRGAS", "SAN JUAN DE RONTOY"],
            "ASUNCION": ["CHACAS", "ACOCHACA"],
            "BOLOGNESI": ["CHIQUIAN", "ABELARDO PARDO LEZAMETA", "ANTONIO RAYMONDI", "AQUIA", "CAJACAY", "CANIS", "COLQUIOC", "HUALLANCA", "HUASTA", "HUAYLLACAYAN", "LA PRIMAVERA", "MANGAS", "PACLLON", "SAN MIGUEL DE CORPANQUI", "TICLLOS"],
            "CARHUAZ": ["CARHUAZ", "ACOPAMPA", "AMASHCA", "ANTA", "ATAQUERO", "MARCARA", "PARIAHUANCA", "SAN MIGUEL DE ACO", "SHILLA", "TINCO", "YUNGAR"],
            "CARLOS FERMIN FITZCARRALD": ["SAN LUIS", "SAN NICOLAS", "YAUYA"],
            "CASMA": ["CASMA", "BUENA VISTA ALTA", "COMANDANTE NOEL", "YAUTAN"],
            "CORONGO": ["CORONGO", "ACO", "BAMBAS", "CUSCA", "LA PAMPA", "YANAC", "YUPAN"],
            "HUARI": ["HUARI", "ANRA", "CAJAY", "CHAVIN DE HUANTAR", "HUACACHI", "HUACCHIS", "HUACHIS", "MASIN", "PAUCAS", "PONTO", "RAHUAPAMPA", "RAPAYAN", "SAN MARCOS", "SAN PEDRO DE CHANA", "UCO"],
            "HUARMEY": ["HUARMEY", "COCHAPETI", "CULEBRAS", "HUAYAN", "MALVAS"],
            "HUAYLAS": ["CARAZ", "HUALLANCA", "HUATA", "HUAYLAS", "MATO", "PAMPAROMAS", "PUEBLO LIBRE", "SANTA CRUZ", "SANTO TORIBIO", "YURACMARCA"],
            "MARISCAL LUZURIAGA": ["PISCOBAMBA", "CASCA", "ELEAZAR GUZMAN BARRON", "FIDEL OLIVAS ESCUDERO", "LLAMA", "LLUMPA", "LUCMA", "MUSGA"],
            "OCROS": ["OCROS", "ACAS", "CAJAMARQUILLA", "CARHUAPAMPA", "COCHAS", "CONGAS", "LLIPA", "SAN CRISTOBAL DE RAJAN", "SAN PEDRO", "SANTIAGO DE CHILCAS"],
            "PALLASCA": ["CABANA", "BOLOGNESI", "CONCHUCOS", "HUACASCHUQUE", "HUANDOVAL", "LACABAMBA", "LLAPO", "PALLASCA", "PAMPAS", "SANTA ROSA", "TAUCA"],
            "POMABAMBA": ["POMABAMBA", "HUAYLLAN", "PAROBAMBA", "QUINUABAMBA"],
            "RECUAY": ["RECUAY", "CATAC", "COTAPARACO", "HUAYLLAPAMPA", "LLACLLIN", "MARCA", "PAMPAS CHICO", "PARARIN", "TAPACOCHA", "TICAPAMPA"],
            "SANTA": ["CHIMBOTE", "CACERES DEL PERU", "COISHCO", "MACATE", "MORO", "NEPENA", "NUEVO CHIMBOTE", "SAMANCO", "SANTA"],
            "SIHUAS": ["SIHUAS", "ACOBAMBA", "ALFONSO UGARTE", "CASHAPAMPA", "CHINGALPO", "HUAYLLABAMBA", "QUICHES", "RAGASH", "SAN JUAN", "SICSIBAMBA"],
            "YUNGAY": ["YUNGAY", "CASCAPARA", "MANCOS", "MATACOTO", "QUILLO", "RANRAHIRCA", "SHUPLUY", "YANAMA"],
        },
        "CAJAMARCA": {
            "CAJAMARCA": ["CAJAMARCA", "ASUNCION", "CHETILLA", "COSPAN", "ENCANADA", "JESUS", "LLACANORA", "LOS BAÑOS DEL INCA", "MAGDALENA", "MATARA", "NAMORA", "SAN JUAN"],
            "CAJABAMBA": ["CAJABAMBA", "CACHACHI", "CONDEBAMBA", "SITACOCHA"],
            "CELENDIN": ["CELENDIN", "CHUMUCH", "CORTEGANA", "HUASMIN", "JORGE CHAVEZ", "JOSE GALVEZ", "MIGUEL IGLESIAS", "OXAMARCA", "SOROCHUCO", "SUCRE", "UTCO", "LA LIBERTAD DE PALLAN"],
            "CHOTA": ["CHOTA", "ANGUIA", "CHADIN", "CHIGUIRIP", "CHIMBAN", "CHOROPAMPA", "COCHABAMBA", "CONCHAN", "HUAMBOS", "LAJAS", "LLAMA", "MIRACOSTA", "PACCHA", "PION", "QUEROCOTO", "SAN JUAN DE LICUPIS", "TACABAMBA", "TOCMOCHE", "PALCAMARCA"],
            "CONTUMAZA": ["CONTUMAZA", "CHILETE", "CUPISNIQUE", "GUZMANGO", "SAN BENITO", "SANTA CRUZ DE TOLEDO", "TANTARICA", "YONAN"],
            "CUTERVO": ["CUTERVO", "CALLAYUC", "CHOROS", "CUJILLO", "LA RAMADA", "PIMPINGOS", "QUEROCOTILLO", "SAN ANDRES DE CUTERVO", "SAN JUAN DE CUTERVO", "SAN LUIS DE LUCMA", "SANTA CRUZ", "SANTO DOMINGO DE LA CAPILLA", "SANTO TOMAS", "SOCOTA", "TORIBIO CASANOVA"],
            "HUALGAYOC": ["BAMBAMARCA", "CHUGUR", "HUALGAYOC"],
            "JAEN": ["JAEN", "BELLAVISTA", "CHONTALI", "COLASAY", "HUABAL", "LAS PIRIAS", "POMAHUACA", "PUCARA", "SALLIQUE", "SAN FELIPE", "SAN JOSE DEL ALTO", "SANTA ROSA"],
            "SAN IGNACIO": ["SAN IGNACIO", "CHIRINOS", "HUARANGO", "LA COIPA", "NAMBALLE", "SAN JOSE DE LOURDES", "TABACONAS"],
            "SAN MARCOS": ["PEDRO GALVEZ", "CHANCAY", "EDUARDO VILLANUEVA", "GREGORIO PITA", "ICHOCAN", "JOSE MANUEL QUIROZ", "JOSE SABOGAL"],
            "SAN MIGUEL": ["SAN MIGUEL", "BOLIVAR", "CALQUIS", "CATILLUC", "EL PRADO", "LA FLORIDA", "LLAPA", "NANCHOC", "NIEPOS", "SAN GREGORIO", "SAN SILVESTRE DE COCHAN", "TONGOD", "UNION AGUA BLANCA"],
            "SAN PABLO": ["SAN PABLO", "SAN BERNARDINO", "SAN LUIS", "TUMBADEN"],
            "SANTA CRUZ": ["SANTA CRUZ", "ANDABAMBA", "CATACHE", "CHANCAYBAÑOS", "LA ESPERANZA", "NINABAMBA", "PULAN", "SAUCEPAMPA", "SEXI", "UTICYACU", "YAUYUCAN"],
        },
        "HUANUCO": {
            "HUANUCO": ["HUANUCO", "AMARILIS", "CHINCHAO", "CHURUBAMBA", "MARGOS", "PILLCO MARCA", "QUISQUI", "SAN FRANCISCO DE CAYRAN", "SAN PEDRO DE CHAULAN", "SANTA MARIA DEL VALLE", "YACUS", "YARUMAYO"],
            "AMBO": ["AMBO", "CAYNA", "COLPAS", "CONCHAMARCA", "HUACAR", "SAN FRANCISCO", "SAN RAFAEL", "TOMAY KICHWA"],
            "DOS DE MAYO": ["LA UNION", "CHUQUIS", "MARIAS", "PACHAS", "QUIVILLA", "RIPAN", "SHUNQUI", "SILLAPATA", "YANAS"],
            "HUACAYBAMBA": ["HUACAYBAMBA", "CANCHABAMBA", "COCHABAMBA", "PINRA"],
            "HUAMALIES": ["LLATA", "ARANCAY", "CHAVIN DE PARIARCA", "JACAS GRANDE", "JIRCAN", "MIRAFLORES", "MONZON", "PUNCHAO", "PUÑOS", "SINGA", "TANTAMAYO"],
            "LEONCIO PRADO": ["RUPA-RUPA", "DANIEL ALOMIA ROBLES", "HERMILIO VALDIZAN", "JOSE CRESPO Y CASTILLO", "LUYANDO", "MARIANO DAMASO BERAUN", "PUCAYACU", "CASTILLO GRANDE", "PUEBLO NUEVO", "SANTO DOMINGO DE ANDA"],
            "MARAÑON": ["HUACRACHUCO", "CHOLON", "SAN BUENAVENTURA", "LA MORADA", "SANTA ROSA DE ALTO YANAJANCA"],
            "PACHITEA": ["PANAO", "CHAGLLA", "MOLINO", "UMARI"],
            "PUERTO INCA": ["PUERTO INCA", "CODO DEL POZUZO", "HONORIA", "TOURNAVISTA", "YUYAPICHIS"],
            "LAURICOCHA": ["JESUS", "BAÑOS", "JIVIA", "QUEROPALCA", "RONDOS", "SAN FRANCISCO DE ASIS", "SAN MIGUEL DE CAURI"],
            "YAROWILCA": ["CHAVINILLO", "CAHUAC", "CHACABAMBA", "APARICIO POMARES", "JACAS CHICO", "OBAS", "PAMPAMARCA", "CHORAS"],
        },
        "LA LIBERTAD": {
            "TRUJILLO": ["TRUJILLO", "EL PORVENIR", "FLORENCIA DE MORA", "HUANCHACO", "LA ESPERANZA", "LAREDO", "MOCHE", "POROTO", "SALAVERRY", "SIMBAL", "VICTOR LARCO HERRERA"],
            "ASCOPE": ["ASCOPE", "CHICAMA", "CHOCOPE", "MAGDALENA DE CAO", "PAIJAN", "RAZURI", "SANTIAGO DE CAO", "CASA GRANDE"],
            "BOLIVAR": ["BOLIVAR", "BAMBAMARCA", "CONDORMARCA", "LONGOTEA", "UCHUMARCA", "UCUNCHA"],
            "CHEPEN": ["CHEPEN", "PACANGA", "PUEBLO NUEVO"],
            "GRAN CHIMU": ["CASCAS", "LUCMA", "MARMOT", "SAYAPULLO"],
            "JULCAN": ["JULCAN", "CALAMARCA", "CARABAMBA", "HUASO"],
            "OTUZCO": ["OTUZCO", "AGALLPAMPA", "CHARAT", "HUARANCHAL", "LA CUESTA", "MACHE", "PARANDAY", "SALPO", "SINSICAP", "USQUIL"],
            "PACASMAYO": ["SAN PEDRO DE LLOC", "GUADALUPE", "JEQUETEPEQUE", "PACASMAYO", "SAN JOSE"],
            "PATAZ": ["TAYABAMBA", "BULDIBUYO", "CHILLIA", "HUANCASPATA", "HUAYLILLAS", "HUAYO", "ONGON", "PARCOY", "PATAZ", "PIAS", "SANTIAGO DE CHALLAS", "TAURIJA", "URPAY"],
            "SANCHEZ CARRION": ["HUAMACHUCO", "CHUGAY", "COCHORCO", "CURGOS", "MARCABAL", "SANAGORAN", "SARIN", "SARTIMBAMBA"],
            "SANTIAGO DE CHUCO": ["SANTIAGO DE CHUCO", "ANGASMARCA", "CACHICADAN", "MOLLEBAMBA", "MOLLEPATA", "QUIRUVILCA", "SANTA CRUZ DE CHUCA", "SITABAMBA"],
            "VIRU": ["VIRU", "CHAO", "GUADALUPITO"],
        },
        "ICA": {
            "ICA": ["ICA", "LA TINGUIÑA", "LOS AQUIJES", "OCUCAJE", "PACHACUTEC", "PARCONA", "PUEBLO NUEVO", "SALAS", "SAN JOSE DE LOS MOLINOS", "SAN JUAN BAUTISTA", "SANTIAGO", "SUBTANJALLA", "TATE", "YAUCA DEL ROSARIO"],
            "CHINCHA": ["CHINCHA ALTA", "ALTO LARAN", "CHAVIN", "CHINCHA BAJA", "EL CARMEN", "GROCIO PRADO", "PUEBLO NUEVO", "SAN JUAN DE YANAC", "SAN PEDRO DE HUACARPANA", "SUNAMPE", "TAMBO DE MORA"],
            "NAZCA": ["NAZCA", "CHANGUILLO", "EL INGENIO", "MARCONA", "VISTA ALEGRE"],
            "NASCA": ["NASCA", "CHANGUILLO", "EL INGENIO", "MARCONA", "VISTA ALEGRE"],
            "PALPA": ["PALPA", "LLIPATA", "RIO GRANDE", "SANTA CRUZ", "TIBILLO"],
            "PISCO": ["PISCO", "HUANCANO", "HUMAY", "INDEPENDENCIA", "PARACAS", "SAN ANDRES", "SAN CLEMENTE", "TUPAC AMARU INCA"],
        },
        "LIMA": {
            "LIMA": ["LIMA", "ANCON", "ATE", "BARRANCO", "BREÑA", "CARABAYLLO", "CHACLACAYO", "CHORRILLOS", "CIENEGUILLA", "COMAS", "EL AGUSTINO", "INDEPENDENCIA", "JESUS MARIA", "LA MOLINA", "LA VICTORIA", "LINCE", "LOS OLIVOS", "LURIGANCHO", "LURIN", "MAGDALENA DEL MAR", "MIRAFLORES", "PACHACAMAC", "PUCUSANA", "PUEBLO LIBRE", "PUENTE PIEDRA", "PUNTA HERMOSA", "PUNTA NEGRA", "RIMAC", "SAN BARTOLO", "SAN BORJA", "SAN ISIDRO", "SAN JUAN DE LURIGANCHO", "SAN JUAN DE MIRAFLORES", "SAN LUIS", "SAN MARTIN DE PORRES", "SAN MIGUEL", "SANTA ANITA", "SANTA MARIA DEL MAR", "SANTA ROSA", "SANTIAGO DE SURCO", "SURQUILLO", "VILLA EL SALVADOR", "VILLA MARIA DEL TRIUNFO"],
            "BARRANCA": ["BARRANCA", "PARAMONGA", "PATIVILCA", "SUPE", "SUPE PUERTO"],
            "CAJATAMBO": ["CAJATAMBO", "COPA", "GORGOR", "HUANCAPON", "MANAS"],
            "CANTA": ["CANTA", "ARAHUAY", "HUAMANTANGA", "HUAROS", "LACHAQUI", "SAN BUENAVENTURA", "SANTA ROSA DE QUIVES"],
            "CAÑETE": ["SAN VICENTE DE CAÑETE", "ASIA", "CALANGO", "CERRO AZUL", "CHILCA", "COAYLLO", "IMPERIAL", "LUNAHUANA", "MALA", "NUEVO IMPERIAL", "PACARAN", "QUILMANA", "SAN ANTONIO", "SAN LUIS", "SANTA CRUZ DE FLORES", "ZUÑIGA"],
            "HUARAL": ["HUARAL", "ATAVILLOS ALTO", "ATAVILLOS BAJO", "AUCALLAMA", "CHANCAY", "IHUARI", "LAMPIAN", "PACARAOS", "SAN MIGUEL DE ACOS", "SANTA CRUZ DE ANDAMARCA", "SUMBILCA", "VEINTISIETE DE NOVIEMBRE"],
            "HUAROCHIRI": ["MATUCANA", "ANTIOQUIA", "CALLAHUANCA", "CARAMPOMA", "CHICLA", "CUENCA", "HUACHUPAMPA", "HUANZA", "HUAROCHIRI", "LAHUAYTAMBO", "LANGA", "LARAOS", "MARIATANA", "RICARDO PALMA", "SAN ANDRES DE TUPICOCHA", "SAN ANTONIO", "SAN BARTOLOME", "SAN DAMIAN", "SAN JUAN DE IRIS", "SAN JUAN DE TANTARANCHE", "SAN LORENZO DE QUINTI", "SAN LORENZO DE PUTI", "SAN MATEO", "SAN MATEO DE OTAO", "SAN PEDRO DE CASTA", "SAN PEDRO DE HUANCAYRE", "SANGALLAYA", "SANTA CRUZ DE COCACHACRA", "SANTA EULALIA", "SANTIAGO DE ANCHUCAYA", "SANTIAGO DE TUNA", "SANTO DOMINGO DE LOS OLLEROS", "SURCO"],
            "HUAURA": ["HUACHO", "AMBAR", "CALETA DE CARQUIN", "CHECRAS", "HUALMAY", "HUAURA", "LEONCIO PRADO", "PACCHO", "SANTA LEONOR", "SANTA MARIA", "SAYAN", "VEGUETA"],
            "OYON": ["OYON", "ANDAJES", "CAUJUL", "COCHAMARCA", "NAVAN", "PACHANGARA"],
            "YAUYOS": ["YAUYOS", "ALIS", "AYAUCA", "AYAVIRI", "AZANGARO", "CACRA", "CARANIA", "CATAHUASI", "CHOCOS", "COCHAS", "COLONIA", "HONGOS", "HUAMPARA", "HUANCAYA", "HUANGASCAR", "HUANTAN", "HUAÑEC", "LARAOS", "LINCHA", "MADEAN", "MIRAFLORES", "OMAS", "PUTINZA", "QUINCHES", "QUINOCAY", "SAN JOAQUIN", "SAN PEDRO DE PILAS", "TANTA", "TAURIPAMPA", "TOMAS", "TUPE", "VINAC", "VITIS"],
        },
        "PASCO": {
            "PASCO": ["CHAUPIMARCA", "HUACHON", "HUARIACA", "HUAYLLAY", "NINACACA", "PALLANCHACRA", "PAUCARTAMBO", "SAN FRANCISCO DE ASIS DE YARUSYACAN", "SIMON BOLIVAR", "TICLACAYAN", "TINYAHUARCO", "VICCO", "YANACANCHA"],
            "DANIEL ALCIDES CARRION": ["YANAHUANCA", "CHACAYAN", "GOYLLARISQUIZGA", "PAUCAR", "SAN PEDRO DE PILLAO", "SANTA ANA DE TUSI", "TAPUC", "VILCABAMBA"],
            "OXAPAMPA": ["OXAPAMPA", "CHONTABAMBA", "HUANCABAMBA", "PALCAZU", "POZUZO", "PUERTO BERMUDEZ", "VILLA RICA", "CONSTITUCION"],
        },
    }
    # ─────────────────────────────────────────────
    # REGLAS DE COYUNTURA NACIONAL
    # ─────────────────────────────────────────────
    NACIONAL_ALLOWED_DEPTS = ["NACIONAL", "LIMA"]


    NACIONAL_ALLOWED_CATEGORIES = [
        "Coyuntura Politica",
        "Coyuntura Social",
        "Protestas, Paros y Bloqueos",
        "Economia-Desarrollo",
        "Agro-Agua-Medioambiente",
    ]

    NACIONAL_MIN_LEVEL = "INFO"

    # ─────────────────────────────────────────────
    # WEBHOOKS (WEBHOOK_SERVER)
    # ─────────────────────────────────────────────
    WEBHOOKS_ENABLED = os.getenv("WEBHOOKS_ENABLED", "true").lower() == "true"
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

    # ─────────────────────────────────────────────
    # VALIDADOR AL ARRANQUE
    # ─────────────────────────────────────────────
    def __init__(self):
        """Valida que la configuración crítica esté presente y consistente."""
        errors = []

        if not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY no configurada en .env")
        if not self.RSS_API_KEY or not self.RSS_API_SECRET:
            errors.append(
                "RSS_API_KEY o RSS_API_SECRET faltan en .env. "
                "ROTAR credenciales en rss.app/dashboard si las anteriores se filtraron."
            )
        if not self.BRIDGE_TOKEN:
            errors.append("BRIDGE_TOKEN no configurado en .env")
        if self.SHEETS_ENABLED and not self.SPREADSHEET_ID:
            errors.append("SHEETS_ENABLED=true pero SPREADSHEET_ID vacío")

        # 2. RSS_BUNDLES vs CLIENTES_VALIDOS (forma canónica)
        clientes_validos = set(self.CLIENTES_VALIDOS)
        bundles_huerfanos = set(self.RSS_BUNDLES.keys()) - clientes_validos
        if bundles_huerfanos:
            errors.append(
                f"RSS_BUNDLES tiene keys que NO están en CLIENTES_VALIDOS: {sorted(bundles_huerfanos)}"
            )

        if errors:
            raise RuntimeError(
                "Configuración inválida:\n  - " + "\n  - ".join(errors)
            )
