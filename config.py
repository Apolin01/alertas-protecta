"""
config.py — Configuración del sistema de alertas Protecta Perú.
Coincide exactamente con el Google Form existente (imágenes del formulario).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ⭐ Cargar .env desde el directorio del módulo (no del cwd).
# Sin esta línea, lanzar el proceso desde otro directorio rompía la carga.
load_dotenv(Path(__file__).parent / ".env")


class Config:
    # ─────────────────────────────────────────────
    # PROVEEDOR DE IA
    # ─────────────────────────────────────────────
    # Solo "openai" está implementado actualmente. Otros providers (claude, gemini, etc.)
    # están stubbed en classifier.py y devuelven None con error.
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

    # ── OpenAI ────────────────────────────────────
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL   = "gpt-4o-mini"

    # ─────────────────────────────────────────────
    # RSS FEED CONFIGURATION (rss.app)
    # ─────────────────────────────────────────────
    # Referencias: https://api.rss.app/v1/bundles
    # ⚠️ SEGURIDAD: defaults previos estaban hardcodeados y quedaron en git history.
    # ROTAR esas credenciales en rss.app/dashboard antes de redeployar.
    RSS_API_KEY = os.getenv("RSS_API_KEY", "")
    RSS_API_SECRET = os.getenv("RSS_API_SECRET", "")
    
    # Mapeo de clientes a Bundle IDs en rss.app
    # Cada bundle contiene grupos de Facebook centralizados para una región/cliente
    RSS_BUNDLES = {
        "Antamina":                      "_vv3HkItEzKqytLHk",      # Ancash
        "Bechtel / Newmont":             "_dtKCh5CjRws0ai8H",      # Cajamarca
        "Clientes Sur":                  "_vuHd6hNkLlFj0nPK",      # Agro Sur (solo Ica — Arequipa bloqueada, ver fix_arequipa_block)
        "Clientes Norte":                "_i5tst4lPDJ5oTSW4",      # Agro Norte (La Libertad, etc)
        "Pisco":                         "_XgBrvIyMIWm5YzLP",      # Pisco
        "Agrícola Santa Azul":           "_oTreAE2PwVfx82Ds",      # Lima costa (Barranca, Supe, Huaura, Huaral)
        "Ninguno (Coyuntura Nacional)":  "_pM02KT2QspbdR8os",      # Coyuntura Nacional
    }
    
    # Usar RSS (rss.app) como fuente principal en lugar del scraper Playwright
    USE_RSS_FEED = os.getenv("USE_RSS_FEED", "true").lower() == "true"
    
    # Intervalo de consulta a RSS (en minutos)
    RSS_POLL_INTERVAL_MINUTES = 5  # Puede consultarse cada 5 minutos según API

    # ─────────────────────────────────────────────
    # SCHEDULER
    # ─────────────────────────────────────────────
    INTERVAL_MINUTES = 5   # tiempo entre ciclos completos
    MAX_WORKERS = 5        # paginas que se procesan en paralelo
    DELAY_BETWEEN_PAGES = 2  # segundos entre páginas en modo scraper

    # Mapeo directo: page_id → cliente (generado del Excel)
    # Sirve como hint para el clasificador cuando la region no es clara
    PAGE_TO_CLIENT = {
        "ABCNoticiasAncash": "Antamina",  # ABC Ancash
        "Zafiro.Imp": "Antamina",  # Áncash - Últimas Noticias
        "ancashaldia": "Antamina",  # Ancash al Día
        "rogerio.tocre" : "Antamina",
        "100083039331687": "Antamina",  # Ancash D' Impacto
        "ancashnoticiasoficial": "Antamina",  # Áncash Noticias
        "andres.loartelaguna": "Antamina",  # Andres Loarte
        "antonio.loarte.laguna.2025": "Antamina",  # Antonio Loarte Laguna
        "100074242929411": "Antamina",  # Aquia Bolognesi
        "CentralNoticiasAncash": "Antamina",  # Central De Noticias Ancash
        "apurayshe.sanmarquino": "Antamina",  # Chakuayonga Noticias
        "100063868508061": "Antamina",  # Lima Norte al Dia
        "100087558444092": "Antamina",  # Chavín de Huántar perú
        "chimboteperuhacenoticia": "Antamina",  # Chimbote Peru Hace Noticia
        "chimbotetelenoticias": "Antamina",  # Chimbote Telenoticias
        "MineraAntamina": "Antamina",  # Compañía Minera Antamina
        # "rondascampesinaseindigenasperu": "Antamina",  # ⭐ DEDUP: ver Coyuntura Nacional abajo (mismo username, tema nacional)
        "61560345096911": "Antamina",  # David Guerra
        "elsita.pereda": "Antamina",  # Dialogo Directo
        "Diariohuascaran": "Antamina",  # Diario Huascaran
        "diariopagina3huanuco": "Antamina",  # Diario Página3
        "61559141072588": "Antamina",  # El Aplicador
        "farrotv": "Antamina",  # FarroTv-
        "100009039772579": "Antamina",  # Fernando Salas Tapia
        "100008949794378": "Antamina",  # Heber Ocaña Granados
        "yudithtobebesita.espinoza": "Antamina",  # Huari Distritos
        "Huaripampamarca": "Antamina",  # Huaripampa - Gollanapinkush
        "ImpactoTVPeru": "Antamina",  # Impacto TV
        "in.situ.huari": "Antamina",  # In Situ Huari TV
        "infomarmadoperu2024": "Antamina",  # Informate.pe
        "yudithmelaniamedina": "Antamina",  # Jhudit Noticias Huari
        "juliocesar.rimacdamian": "Antamina",  # Julio Cesar Rimac Damian
        "Kaletalarevista": "Antamina",  # Kaleta La Revistas
        "LaCuevadelDuendeMineria": "Antamina",  # La Cueva del Duende
        "lenin.ramirez.397": "Antamina",  # Lenin Ramirez
        "marlongilbert.mogollongamarra": "Antamina",  # Marlon Mogollon Gamarra
        "maycol.ugarte": "Antamina",  # Maycol Ugarte
        "100074979673866": "Antamina",  # Messi Blas Vega
        "MtvNoticiasAncashPeru": "Antamina",  # Mtv Noticias Ancash
        "Municipalidadcatac": "Antamina",  # Municipalidad Distrital de Cátac
        "100089448216922": "Antamina",  # Noticia Caraz
        "Huaral.Noticias.Huaral": "Antamina",  # Noticia de Huaral
        "100063707250166": "Antamina",  # Pulso 7
        "LaFabulosa.pe": "Antamina",  # Radio La Fabulosa Oficial
        "100063835084929": "Antamina",  # Radio San Miguel 97.5 fm
        "roger.arizabrioso": "Antamina",  # Roger Ariza
        "100093310282043": "Antamina",  # Santa Cruz De Pichiu
        "100063502961149": "Antamina",  # Sin Censura
        "61561049853341": "Antamina",  # Tucu Willacoj
        "TV6Huarmey": "Antamina",  # Tv Huarmey
        "bolognesinoticias": "Antamina",  # Bolognesi Noticias - Actualidades de Pallasca, Áncash y el Perú.
        "Noticias.Huaraz.Peru": "Antamina",  # Agencia De Noticias Huaraz - Ancash
        "100087263666637": "Antamina",  # Huaraz con la Noticia
        "visiontvcasma": "Antamina",  # Vision TV Digital
        "100057328106252": "Antamina",  # Informativo Hoy
        "Noticiero.Huari": "Antamina",  # Noticiero Huari
        "Reporte6": "Antamina",  # Reporte 6 - Huaraz
        "huarilindo": "Antamina",  # Huari Lindo
        "angel.duranleon": "Antamina",  # Angel Duran Leon
        "100041995064479": "Antamina",  # El Inquisidor Noticias
        "kellyPortalatinoA": "Antamina",  # Kelly Portalatino Avalos
        "GobiernoRegionaldeAncash": "Antamina",  # Gobierno Regional de Ancash 2023-2026
        "100066327024231": "Antamina",  # Consejo Regional de Ancash
        "MunicipalidadDistritalDeSanMarcos2023": "Antamina",  # Municipalidad Distrital de San Marcos 2023 - 2026
        "radiollata92.3fm": "Antamina",  # RADIO LLATA 92.3 FM  (Radio Llata TV)
        "100088320954687": "Antamina",  # Curca-ancash Cunarc-perú
        "noticias.huarid": "Antamina",  # Noticias Huari Digital
        "visioninformativahuarazoficial": "Antamina",  # Visión Informativa Huaraz
        "erick.c.loli.morales": "Antamina",  # Erick C. Loli Morales  (Periodista)
        "100095310110797": "Antamina",  # Vehinler Yorlin Huayta Herrera
        "elfoco.peru": "Antamina",  # El Foco
        "ancashinfo": "Antamina",  # AncashInforma
        "manuelcaballeromana": "Antamina",  # Juan Manuel Caballero
        "DbateCajamarca": "Bechtel / Newmont",  # Dbate Cajamarca
        "escucho.ayudo.77": "Bechtel / Newmont",  # Fernando Chuquilin Ramos
        "lideradio": "Bechtel / Newmont",  # Radio Líder Cajamarca
        "RadioDiscoPlus": "Bechtel / Newmont",  # Radio Disco Plus -¡señal de Poder.
        # "people": "Bechtel / Newmont",  # ⭐ DEDUP: clave "people" es sospechosa (¿username FB real?) y duplicada en Clientes Sur — eliminada hasta verificar
        "100063883096756": "Bechtel / Newmont",  # El INFORMANTE CAJAMARCA
        "JaenNoticiasTeInforma": "Bechtel / Newmont",  # Jaén Noticias
        "100064383774051": "Bechtel / Newmont",  # Bambamarca Televisión
        "diarioelcajamarquino": "Bechtel / Newmont",  # El Cajamarquino
        "almanoticiascaj": "Bechtel / Newmont",  # Alma Noticias
        "HablaCajamarcaNoticias": "Bechtel / Newmont",  # Habla Cajamarca
        "Caxamarcaaldia": "Bechtel / Newmont",  # Caxamarca al Día
        # "redmuqui": "Bechtel / Newmont",  # ⭐ DEDUP: ver Coyuntura Nacional abajo (Red Muqui es ONG nacional)
        "espinoza.roja.yolanda": "Bechtel / Newmont",  # Yolanda Victoria Rojas Espinoza
        "100055208267487": "Bechtel / Newmont",  # Noticias en Conexión
        "PortafolioPeriodistico": "Bechtel / Newmont",  # Portafolio Periodístico Perú de Tony Alvarado A.
        "Continente820": "Bechtel / Newmont",  # Radio Continente de Cajamarca
        "elcapodelanoticia": "Bechtel / Newmont",  # El Capo
        "CodigoPeriodistico": "Bechtel / Newmont",  # Código Periodístico Cajamarca - Perú
        "MegaPlusTve": "Bechtel / Newmont",  # 𝑴𝒆𝒈𝒂 𝑷𝒍𝒖𝒔 𝑻𝒗𝒆
        "Caxamarcadigital": "Bechtel / Newmont",  # Prensa en Acción
        "radiocampesinanoticias": "Bechtel / Newmont",  # Radio Campesina
        "Hoyendia.Cajamarca": "Bechtel / Newmont",  # Hoy en Día
        "NoticiasImpactantesdeCajamarca": "Bechtel / Newmont",  # Noticias Impactantes de Cajamarca
        "ChotaTvNoticias": "Bechtel / Newmont",  # Chota TV Noticias
        "CajamarcaNoticia": "Bechtel / Newmont",  # Cajamarca Noticias
        "100087136487852": "Bechtel / Newmont",  # Noticias Región Cajamarca
        "agrochamba": "Clientes Sur",  # Agrochamba
        "agrokasaperu": "Clientes Sur",  # Agrokasa
        "Agromigiva": "Clientes Sur",  # Agromigiva
        "AgronegociosGenesis": "Clientes Sur",  # Agronegocios Génesis
        "fullRaleoIca": "Clientes Sur",  # Barrio chino ICA Perú
        "BorisBarrientosSutepRegionalYCGTPIca": "Clientes Sur",  # Boris Barrientos Sutep regional Ica
        "ReddigitalCanal29": "Clientes Sur",  # CANAL 29 - Red Digital ICA
        "Chincha.Central.Noticias": "Clientes Sur",  # Chincha Central - Noticias
        "100063655355542": "Clientes Sur",  # Chincha Noticiero
        "chinchafirstnoticias": "Clientes Sur",  # Chincha Primero - Noticias
        "61556081050844": "Clientes Sur",  # Chincha Provincia Segura
        "codehica": "Clientes Sur",  # CODEHICA
        "100077171993787": "Clientes Sur",  # Dan Sanchez
        "DebateyNoticiasIca": "Clientes Sur",  # Debate y Noticias Nasca
        "DonRicardopaginaoficial": "Clientes Sur",  # Don Ricardo
        "DunasTvNoticias": "Clientes Sur",  # DUNAS TV ICA
        "100064071190967": "Clientes Sur",  # Epa Chincha Noticias
        "61555501130868": "Clientes Sur",  # EPM Noticias Nasca
        "IcaExitosa": "Clientes Sur",  # Exitosa Ica
        "faustino.rodriguezquiroz": "Clientes Sur",  # Faustino Rodriguez Quiroz
        "fullraleo": "Clientes Sur",  # Full raleo/Ica.
        "GoreIcaOficial": "Clientes Sur",  # Gobierno Regional de Ica
        "guerreradelmicrofono": "Clientes Sur",  # Hablemos Claro - Noticias Ica
        "icaenportada.pe": "Clientes Sur",  # Ica en Portada
        "100063992083915": "Clientes Sur",  # ICA En VIVO
        "icanoticias21": "Clientes Sur",  # ICA Noticias XXI
        "100077766706082": "Clientes Sur",  # ICA REC-Noticias
        "100083063842591": "Clientes Sur",  # Región Policial Ica
        "INFORMATEICA": "Clientes Sur",  # Infórmate-Ica
        "jesus.shimabukuro": "Clientes Sur",  # Jesus Shimabukuro
        "inkarry.tawainti": "Clientes Sur",  # José Carlos Matías Calderón (El Inka)
        "OkeyTePone": "Clientes Sur",  # La Verdad De Ica noticias
        "100072226157454": "Clientes Sur",  # LAS Noticias De NASCA
        "leydy.loayzamendoza": "Clientes Sur",  # Leydy Loayza Mendoza
        "marleny.jalixtohuasco": "Clientes Sur",  # Marleny Jalixto Huasco (La Colla)
        "miguel.quijandria.921": "Clientes Sur",  # Miguel Quijandria
        "MunicipalidadProvincialDeIca": "Clientes Sur",  # Municipalidad de Ica
        "salasguadalupeica": "Clientes Sur",  # Municipalidad Distrital de Salas Guadalupe
        "MORAZZANI": "Clientes Sur",  # Nasca Noticias
        "100055947829841": "Clientes Sur",  # Online Noticias Ica
        "61551993545297": "Clientes Sur",  # Partido Comunista Peruano - Ica Page
        # "people": "Clientes Sur",  # ⭐ DEDUP: clave "people" sospechosa — eliminada
        # ⭐ DEDUP: las 4 páginas de Pisco abajo se reasignaron al cliente "Pisco" (ver sección Pisco)
        # "PiscoNoticiass": "Clientes Sur",  # PISCO Noticias
        # "PiscoteInforma": "Clientes Sur",  # Pisco te Informa
        # "plusnoticias.pe": "Clientes Sur",  # Plus Noticias Pisco Page
        # "prensadigitalpiscoperu": "Clientes Sur",  # Prensa Digital Pisco Page
        "PeriodismodeIca": "Clientes Sur",  # Proyección Informativa
        "ReclutamientoAthosIca": "Clientes Sur",  # Reclutamiento Ica
        "Magaly.Becerrae": "Clientes Sur",  # Regidora Nancy Becerra - MD Salas, Ica
        "MarketingChincha": "Clientes Sur",  # Revista Pandemia Chincha
        "SafcoPeru": "Clientes Sur",  # Safco Perú
        "safresco": "Clientes Sur",  # Safresco
        "100069071586685": "Clientes Sur",  # STCC Ica
        "SunFruitsExportsSa": "Clientes Sur",  # Sun Fruits Exports S.A.
        "100068649247660": "Clientes Sur",  # Susan Quintanilla
        "SutepRegionalIcaOficial": "Clientes Sur",  # Sutep Regional Ica
        "transmisiones.pisco": "Clientes Sur",  # Transmisiones Pisco Page
        "tvochincha": "Clientes Sur",  # TVO Chincha
        "UnionChinchana": "Clientes Sur",  # Unión Chinchana
        "GrupoVanguardInternacional": "Clientes Sur",  # Grupo Vanguard Internacional
        "pedrovictor.garciafernandez": "Clientes Sur",  # Pedro Víctor García Fernández
        "61567522762662": "Clientes Sur",  # Agrokasa Pisco (FB)
        "grupoathosoficial": "Clientes Sur",  # Athos (FB)
        "chapi.com.pe": "Clientes Sur",  # Chapi (FB)
        "agricoladonluis": "Clientes Sur",  # Don Luis (FB)
        "family.farms.oficial": "Clientes Sur",  # Family Farms (FB)
        "agricolariachuelo": "Clientes Sur",  # Riachuelo (FB)
        "adasperu.oficial": "Clientes Norte",  # ADAS
        "agualima.peru": "Clientes Norte",  # AguaLima
        "aldopaginaoficial": "Clientes Norte",  # Aldo Carlos Mariños
        "AzucareraCasaGrande1": "Clientes Norte",  # CasaGrande
        "CEPESRURAL": "Clientes Norte",  # CEPES
        "DanperPeru": "Clientes Norte",  # Danper
        "ExitosaTrujillo": "Clientes Norte",  # Exitosa Trujillo
        "61550669891428": "Clientes Norte",  # Federacion provincial de Rondas Campesinas de viru
        "felipe.arteagasaavedra.5": "Clientes Norte",  # Felipe Arteaga Saavedra
        "FetsaRLL": "Clientes Norte",  # FETSA
        "greenperurrhh": "Clientes Norte",  # GreenPeru
        "gruporocio.pe": "Clientes Norte",  # Grupo Rocio
        "hassperu": "Clientes Norte",  # Hass Perú
        "hortifrutperu": "Clientes Norte",  # Hortifrut Perú
        "KeBuenaNoticiasPaginaOficiall": "Clientes Norte",  # Ke Buena Noticias
        "MissionProducePeru": "Clientes Norte",  # Mission
        "noticiasviruoficial": "Clientes Norte",  # Noticias Virú
        "pedro.campospalacios": "Clientes Norte",  # Pedro Campos Palacios
        "100071043856616": "Clientes Norte",  # Red de Noticias - La Libertad
        "100090935898268": "Clientes Norte",  # Sapitos al Rescate
        "AgroindustrialLaredo": "Clientes Norte",  # Sol de Laredo
        "walter.campos.palacios": "Clientes Norte",  # Walter Campos Palacios
        "100064024635914": "Clientes Norte",  # CHAO Noticias Tv Digital
        "AgricolaCerroPrietoSA": "Clientes Norte",  # Agrícola Cerro Prieto
        "GiddingsBerriesPeru": "Clientes Norte",  # GIDDINGS (FB)
        "100083411587501": "Clientes Norte",  # TALSA (FB)
        "westfaliafruitperu": "Clientes Norte",  # WESTFALIA FRUIT (FB)
        "juan.jironsanchez": "Agrícola Santa Azul",  # Juan Jiron Sanchez
        "contrapoder.live": "Agrícola Santa Azul",  # Cuarto  Poder
        "municiaplidaddistritaldesupe20192022": "Agrícola Santa Azul",  # Municipalidad de Supe
        "MunicipalidadDeBarranca": "Agrícola Santa Azul",  # Municipalidad Provincial de Barranca
        "PiscoNoticiass": "Pisco",  # PISCO Noticias
        "PiscoteInforma": "Pisco",  # Pisco te Informa
        "plusnoticias.pe": "Pisco",  # Plus Noticias Pisco Page
        "prensadigitalpiscoperu": "Pisco",  # Prensa Digital Pisco Page
        "LaVozdePiscoOficial": "Pisco",  # La Voz de Pisco
        "MuniHuancano": "Pisco",  # Municipalidad Distrital de Huáncano
        "100083218815937": "Pisco",  # Pisqueño Verídico
        "AngelRojas.ComnSoc": "Pisco",  # Angel Pisco
        "munidistritalhumay": "Pisco",  # Municipalidad Distrital de Humay
        "megavision.pisco": "Pisco",  # Megavision Pisco
        "jaime.lorenzo.fernandez.hernandez.2024": "Pisco",  # Humay Tv
        "carmen.herrerasolis.754": "Pisco",  # Carmen Herrera Solis
        "mario.rengifo.125": "Pisco",  # Mario Rengifo
        "SANCLEMENTETEINFORMA": "Pisco",  # San Clemente Te Informa
        "100071701105635": "Pisco",  # Humay : Tierra Santa
        "ContactoPisco": "Pisco",  # Contacto Pisco
        "CoordinadoraNacionalUnitariadeLuch4": "Ninguno (Coyuntura Nacional)",  # CNUL
        "61554662620217": "Ninguno (Coyuntura Nacional)",  # Confemin
        "conulp": "Ninguno (Coyuntura Nacional)",  # CONULP
        "Gustavo.Minaya": "Ninguno (Coyuntura Nacional)",  # Gustavo Minaya
        "lalupa.pe": "Ninguno (Coyuntura Nacional)",  # LA LUPA
        "LiaValderramaa": "Ninguno (Coyuntura Nacional)",  # Lía Vladerrama
        "tomalacalletv": "Ninguno (Coyuntura Nacional)",  # Tomalacalle Tv Page
        "vladimir.cerronrojas": "Ninguno (Coyuntura Nacional)",  # Vladimir Cerrón
        "waykaperu": "Ninguno (Coyuntura Nacional)",  # Wayka Page
        "rondascampesinaseindigenasperu": "Ninguno (Coyuntura Nacional)",  # CUNARC-Perú
        "siterlimabasesregionales": "Ninguno (Coyuntura Nacional)",  # SITER Lima Metropolitana Base Regional
        "cnddhh": "Ninguno (Coyuntura Nacional)",  # Cnddhh Perú
        "liberacion.peru.9": "Ninguno (Coyuntura Nacional)",  # Movimiento Liberacion
        "redmuqui": "Ninguno (Coyuntura Nacional)",  # Red Muqui
        "pcdelp.patriaroja": "Ninguno (Coyuntura Nacional)",  # Partido Comunista del Perú - Patria Roja
        "Sutep.Peru": "Ninguno (Coyuntura Nacional)",  # SUTEP
        "amucep.peru": "Ninguno (Coyuntura Nacional)",  # AMUCEP PERÚ
        "cgtp.peru": "Ninguno (Coyuntura Nacional)",  # CGTP Perú
        "magno.ismael.palomino": "Ninguno (Coyuntura Nacional)",  # Magno Ismael Palomino
        "antaurohumalatassooficial": "Ninguno (Coyuntura Nacional)",  # Antauro Humala Oficial
        "diario.expreso": "Ninguno (Coyuntura Nacional)",  # Diario Expreso
        "elena.milo.villar.milo": "Ninguno (Coyuntura Nacional)",  # Elena Milo Villar Milo
        "61557857056881": "Ninguno (Coyuntura Nacional)",  # La Contra
        "canalnoficial": "Ninguno (Coyuntura Nacional)",  # Canal N
        "elmuquipodcast": "Ninguno (Coyuntura Nacional)",  # El Muqui
        "ONAMIAP.pe": "Ninguno (Coyuntura Nacional)",  # ONAMIAP
    }

    # Sin restriccion horaria — envio siempre al instante
    SEND_WINDOWS = {}

    # ─────────────────────────────────────────────
    # ORDEN DE ROTACION POR REGION
    # El sistema rota entre regiones en este orden
    # procesando N paginas de cada una antes de pasar a la siguiente
    # ─────────────────────────────────────────────
    # ⭐ Los nombres aquí deben coincidir EXACTAMENTE con los valores de PAGE_TO_CLIENT
    # y las keys de RSS_BUNDLES (forma canónica de CLIENTES_VALIDOS).
    REGION_ROTATION = [
        "Antamina",
        "Bechtel / Newmont",
        "Clientes Sur",
        "Clientes Norte",
        "Agrícola Santa Azul",
        "Pisco",
        "Ninguno (Coyuntura Nacional)",
    ]

    # Páginas por región por turno antes de rotar a la siguiente.
    # process_region usa wrap-around: si limit > len(pages) reprocesa la lista.
    # 50 cubre regiones grandes (Antamina ~72 paginas) sin reprocesar 7×.
    PAGES_PER_REGION_TURN = 50

    # ─────────────────────────────────────────────
    # FACEBOOK SCRAPING — lista de páginas a scrapear
    # ─────────────────────────────────────────────
    # ⭐ Derivada de PAGE_TO_CLIENT.keys() para garantizar consistencia automática
    # y eliminar duplicados. Si quieres agregar una página, hazlo en PAGE_TO_CLIENT
    # (no aquí) — esta lista se regenera sola.
    FACEBOOK_PAGES = list(PAGE_TO_CLIENT.keys())

    POSTS_PER_PAGE = 8
    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "bridge")
    ENABLE_IMAGE_FALLBACK = os.getenv("ENABLE_IMAGE_FALLBACK", "true").lower() == "true"


    # ─────────────────────────────────────────────
    # WHATSAPP BRIDGE (whatsapp-web.js)
    # ─────────────────────────────────────────────
    BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:3000")
    # ⚠️ SEGURIDAD: default "protecta2026" estaba en git history. ROTAR el token.
    BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN", "")

    # ─────────────────────────────────────────────
    # GOOGLE SHEETS — mismo Sheets del Google Form
    # ─────────────────────────────────────────────
    # Poner en True cuando tengas el credentials.json de Google
    SHEETS_ENABLED = os.getenv("SHEETS_ENABLED", "false").lower() == "true"
    GOOGLE_CREDENTIALS_FILE = "credentials.json"
    # ⚠️ El SPREADSHEET_ID estaba hardcodeado como default. Pasarlo via .env.
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
    SHEET_NAME = "Tabla_Informacion"       # pestaña visible en imagen 1
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
        "Agrícola Huarmey",
        "Campos Andino",
        "Campos del Sur",
        "Don Ricardo",
        "Hortifrut",
        "Mission",
        "RVR",
        "SunFruits",
        "Vanguard",
        "Uvica",
        "Agrícola Santa Azul",
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
    # MAPEO REGIÓN → CLIENTE(S) DEL FORM
    # ─────────────────────────────────────────────
    REGION_TO_CLIENTES = {
        # Minería
        "ANCASH":           ["Antamina"],
        "HUANUCO":          ["Antamina"],
        "CAJAMARCA":        ["Bechtel / Newmont"],
        "PASCO":            ["Antamina"],

        # Pisco
        "ICA PISCO":        ["Pisco"],
        "PISCO":            ["Pisco"],
        # Agroindustria Sur
        "ICA":              ["Agrícola Chapi", "Clientes Sur"],
        # AREQUIPA removido intencionalmente — ver fix_arequipa_block() en classifier.py.
        # Cualquier noticia de Arequipa va a IGNORAR salvo politica nacional pura.
        # Agroindustria Norte / Lima costa
        "LA LIBERTAD":      ["Clientes Norte"],
 
        "LIMA BARRANCA":    ["Agrícola Santa Azul", "Agrícola Huarmey"],
        "LIMA SUPE":        ["Agrícola Santa Azul"],
        "LIMA HUAURA":      ["Agrícola Santa Azul"],
        "LIMA HUARAL":      ["Agrícola Santa Azul"],  # ⭐ Sincronizado con classifier.py PROVINCIA_TO_CLIENT
        "ANCASH HUARMEY":   ["Agrícola Huarmey"],
        # Nacional
        "NACIONAL":         ["Ninguno (Coyuntura Nacional)"],
        "PERU":             ["Ninguno (Coyuntura Nacional)"],
    }

    # ─────────────────────────────────────────────
    # MAPEO CLIENTE → GRUPO WHATSAPP
    # ─────────────────────────────────────────────
    CLIENTE_TO_WHATSAPP_GROUP = {
        "Antamina":                         "Antamina",
        "Bechtel / Newmont":                "Bechtel / Newmont",
        "Clientes Sur":                     "Clientes Sur",
        "Clientes Norte":                   "Clientes Norte",
        "Agrícola Santa Azul":              "Agricola Santa Azul",
        "Agrícola Huarmey":                 "Antamina",
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
        # ANCASH — 20 provincias reales (Antamina opera en HUARI: San Marcos, Chavín de Huántar)
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
        # CAJAMARCA — 13 provincias reales (Bechtel / Newmont opera en CAJAMARCA y HUALGAYOC)
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
        # HUANUCO — 11 provincias reales (Antamina opera en HUAMALIES: Llata)
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
        # LA LIBERTAD — 12 provincias reales (Clientes Norte: agroindustria costa)
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
        # ICA — 5 provincias reales (Pisco: pesca; Chincha/Ica/Nazca/Palpa: agro sur)
        "ICA": {
            "ICA": ["ICA", "LA TINGUIÑA", "LOS AQUIJES", "OCUCAJE", "PACHACUTEC", "PARCONA", "PUEBLO NUEVO", "SALAS", "SAN JOSE DE LOS MOLINOS", "SAN JUAN BAUTISTA", "SANTIAGO", "SUBTANJALLA", "TATE", "YAUCA DEL ROSARIO"],
            "CHINCHA": ["CHINCHA ALTA", "ALTO LARAN", "CHAVIN", "CHINCHA BAJA", "EL CARMEN", "GROCIO PRADO", "PUEBLO NUEVO", "SAN JUAN DE YANAC", "SAN PEDRO DE HUACARPANA", "SUNAMPE", "TAMBO DE MORA"],
            "NAZCA": ["NAZCA", "CHANGUILLO", "EL INGENIO", "MARCONA", "VISTA ALEGRE"],
            "PALPA": ["PALPA", "LLIPATA", "RIO GRANDE", "SANTA CRUZ", "TIBILLO"],
            "PISCO": ["PISCO", "HUANCANO", "HUMAY", "INDEPENDENCIA", "PARACAS", "SAN ANDRES", "SAN CLEMENTE", "TUPAC AMARU INCA"],
        },
        # LIMA — 10 provincias (BARRANCA/SUPE/HUAURA/HUARAL: Agrícola Santa Azul; el resto: IGNORAR)
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
        # PASCO — 3 provincias (Antamina referenciada por DEPT_TO_CLIENT pero sin RSS bundle propio)
        "PASCO": {
            "PASCO": ["CHAUPIMARCA", "HUACHON", "HUARIACA", "HUAYLLAY", "NINACACA", "PALLANCHACRA", "PAUCARTAMBO", "SAN FRANCISCO DE ASIS DE YARUSYACAN", "SIMON BOLIVAR", "TICLACAYAN", "TINYAHUARCO", "VICCO", "YANACANCHA"],
            "DANIEL ALCIDES CARRION": ["YANAHUANCA", "CHACAYAN", "GOYLLARISQUIZGA", "PAUCAR", "SAN PEDRO DE PILLAO", "SANTA ANA DE TUSI", "TAPUC", "VILCABAMBA"],
            "OXAPAMPA": ["OXAPAMPA", "CHONTABAMBA", "HUANCABAMBA", "PALCAZU", "POZUZO", "PUERTO BERMUDEZ", "VILLA RICA", "CONSTITUCION"],
        },
    }
    # ─────────────────────────────────────────────
    # REGLAS DE COYUNTURA NACIONAL
    # Solo LIMA va a NACIONAL (política de Lima)
    # ─────────────────────────────────────────────
    NACIONAL_ALLOWED_DEPTS = [
        "NACIONAL",  # Política nacional pura
        "LIMA",      # Solo capital
    ]
    
    # Subcategorías que SÍ se envían a NACIONAL (filtro de política)
    NACIONAL_ALLOWED_CATEGORIES = [
        "Coyuntura Politica",
        "Coyuntura Social",
        "Protestas, Paros y Bloqueos",
    ]
    
    # Nivel mínimo para NACIONAL (INFO, ALRT y CRIT pasan)
    NACIONAL_MIN_LEVEL = "INFO"



    # ─────────────────────────────────────────────
    # WEBHOOKS (WEBHOOK_SERVER)
    # ─────────────────────────────────────────────
    WEBHOOKS_ENABLED = os.getenv("WEBHOOKS_ENABLED", "true").lower() == "true"
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # Opcional: para validar webhooks
    
    # (WEBHOOKS_WITH_POLLING_FALLBACK eliminado: nunca se usó en el código)

    # ─────────────────────────────────────────────
    # VALIDADOR AL ARRANQUE
    # ─────────────────────────────────────────────
    def __init__(self):
        """Valida que la configuración crítica esté presente y consistente.

        Si falla, lanza RuntimeError con un mensaje accionable.
        Llamar `Config()` antes de usar cualquier subsistema.
        """
        errors = []

        # 1. Credenciales mínimas
        if not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY no configurada en .env")
        if self.USE_RSS_FEED and (not self.RSS_API_KEY or not self.RSS_API_SECRET):
            errors.append(
                "RSS_API_KEY o RSS_API_SECRET faltan en .env (necesarias con USE_RSS_FEED=true). "
                "ROTAR credenciales en rss.app/dashboard si las anteriores se filtraron."
            )
        if not self.BRIDGE_TOKEN:
            errors.append("BRIDGE_TOKEN no configurado en .env")
        if self.SHEETS_ENABLED and not self.SPREADSHEET_ID:
            errors.append("SHEETS_ENABLED=true pero SPREADSHEET_ID vacío")

        # 2. Consistencia entre mapeos (forma canónica de CLIENTES_VALIDOS)
        clientes_validos = set(self.CLIENTES_VALIDOS)
        clientes_en_pages = set(self.PAGE_TO_CLIENT.values())
        huerfanos = clientes_en_pages - clientes_validos
        if huerfanos:
            errors.append(
                f"PAGE_TO_CLIENT usa clientes que NO están en CLIENTES_VALIDOS: {sorted(huerfanos)}. "
                "Estandariza nombres (tildes/paréntesis) o agrégalos a CLIENTES_VALIDOS."
            )

        # 3. RSS_BUNDLES vs CLIENTES_VALIDOS (solo si modo RSS)
        if self.USE_RSS_FEED:
            bundles_huerfanos = set(self.RSS_BUNDLES.keys()) - clientes_validos
            if bundles_huerfanos:
                errors.append(
                    f"RSS_BUNDLES tiene keys que NO están en CLIENTES_VALIDOS: {sorted(bundles_huerfanos)}"
                )

        # 4. REGION_ROTATION solo se usa en modo SCRAPER; en modo RSS se itera RSS_BUNDLES.keys().
        # Validamos que cada región en REGION_ROTATION tenga al menos 1 página en PAGE_TO_CLIENT.
        if not self.USE_RSS_FEED:
            clientes_con_pages = set(self.PAGE_TO_CLIENT.values())
            regiones_sin_pages = set(self.REGION_ROTATION) - clientes_con_pages
            if regiones_sin_pages:
                errors.append(
                    f"REGION_ROTATION (modo scraper) incluye regiones sin páginas en PAGE_TO_CLIENT: {sorted(regiones_sin_pages)}"
                )

        if errors:
            raise RuntimeError(
                "Configuración inválida:\n  - " + "\n  - ".join(errors)
            )
