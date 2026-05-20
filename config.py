"""
config.py — Configuración del sistema de alertas Protecta Perú.
Coincide exactamente con el Google Form existente (imágenes del formulario).
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ─────────────────────────────────────────────
    # PROVEEDOR DE IA — cambia aqui para usar otro modelo
    # Opciones: "claude" | "gemini" | "groq" | "openrouter"
    # ─────────────────────────────────────────────
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

    # ── OpenAI ────────────────────────────────────
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL   = "gpt-4o-mini"

    # ─────────────────────────────────────────────
    # RSS FEED CONFIGURATION (rss.app)
    # ─────────────────────────────────────────────
    # Referencias: https://api.rss.app/v1/bundles
    RSS_API_KEY = os.getenv("RSS_API_KEY", "c_7aE06O3k7WkZ0S")
    RSS_API_SECRET = os.getenv("RSS_API_SECRET", "s_wrrdXjFLUPmdULTkqJ1FfJ")
    
    # Mapeo de clientes a Bundle IDs en rss.app
    # Cada bundle contiene grupos de Facebook centralizados para una región/cliente
    RSS_BUNDLES = {
        "Antamina":                      "_vv3HkItEzKqytLHk",      # Ancash
        "Bechtel / Newmont":             "_dtKCh5CjRws0ai8H",      # Cajamarca
        "Clientes Sur":                  "_vuHd6hNkLlFj0nPK",      # Agro Sur (Ica, Arequipa)
        "Clientes Norte":                "_i5tst4lPDJ5oTSW4",      # Agro Norte (La Libertad, etc)
        "Pisco":                         "_XgBrvIyMIWm5YzLP",      # Pisco
        "Ninguno (Coyuntura Nacional)":  "_pM02KT2QspbdR8os",      # Coyuntura Nacional
    }
    
    # Usar RSS como fuente en lugar de Apify/Facebook scraper
    USE_RSS_FEED = os.getenv("USE_RSS_FEED", "true").lower() == "true"
    
    # Intervalo de consulta a RSS (en minutos)
    RSS_POLL_INTERVAL_MINUTES = 5  # Puede consultarse cada 5 minutos según API

    # ─────────────────────────────────────────────
    # SCHEDULER
    # ─────────────────────────────────────────────
    INTERVAL_MINUTES = 5  # Cambiar a 5 minutos para RSS (era 30 con Apify)

    # Paginas que se procesan en paralelo simultaneamente
    MAX_WORKERS = 5

    DELAY_BETWEEN_PAGES  = 2    # segundos entre páginas (Playwright: carga natural ya toma ~10s)

    # Timeout por pagina: si Apify no responde en N segundos, pasar a la siguiente
    PAGE_TIMEOUT_SECONDS = 45

    # Maximo de paginas sin alertas antes de rotar a la siguiente region
    # Si una region lleva N paginas seguidas sin noticias utiles, avanza
    MAX_EMPTY_PAGES_BEFORE_ROTATE = 5
                                    # 239 paginas x 15s = ~60 min para un ciclo completo
                                    # Reduce esto si tienes plan de pago en Apify

    # Pausa entre ciclos completos (segundos)
    # Despues de leer las 239 paginas, espera antes de volver a empezar
    # 1800 = 30 minutos entre ciclos completos
    DELAY_BETWEEN_CYCLES = 300   # pausa entre ciclos completos (5 min)

    # Paginas leidas por ciclo (rotacion para ahorrar credito Apify)
    # 239 paginas / 25 por ciclo = ~10 grupos → cada pagina se lee cada 5h
    # Sube este numero si quieres cobertura mas frecuente (mas costo)
    PAGES_PER_CYCLE = 25

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
        "rondascampesinaseindigenasperu": "Antamina",  # CUNARC-Perú
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
        "people": "Bechtel / Newmont",  # Ultima HORA, Celendín
        "100063883096756": "Bechtel / Newmont",  # El INFORMANTE CAJAMARCA
        "JaenNoticiasTeInforma": "Bechtel / Newmont",  # Jaén Noticias
        "100064383774051": "Bechtel / Newmont",  # Bambamarca Televisión
        "diarioelcajamarquino": "Bechtel / Newmont",  # El Cajamarquino
        "almanoticiascaj": "Bechtel / Newmont",  # Alma Noticias
        "HablaCajamarcaNoticias": "Bechtel / Newmont",  # Habla Cajamarca
        "Caxamarcaaldia": "Bechtel / Newmont",  # Caxamarca al Día
        "redmuqui": "Bechtel / Newmont",  # Red Muqui
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
        "people": "Clientes Sur",  # Partido Comunista Peruano - Ica
        "PiscoNoticiass": "Clientes Sur",  # PISCO Noticias
        "PiscoteInforma": "Clientes Sur",  # Pisco te Informa
        "plusnoticias.pe": "Clientes Sur",  # Plus Noticias Pisco Page
        "prensadigitalpiscoperu": "Clientes Sur",  # Prensa Digital Pisco Page
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
        "juan.jironsanchez": "Agricola Santa Azul",  # Juan Jiron Sanchez
        "contrapoder.live": "Agricola Santa Azul",  # Cuarto  Poder
        "municiaplidaddistritaldesupe20192022": "Agricola Santa Azul",  # Municipalidad de Supe
        "MunicipalidadDeBarranca": "Agricola Santa Azul",  # Municipalidad Provincial de Barranca
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
        "CoordinadoraNacionalUnitariadeLuch4": "Coyuntura Nacional",  # CNUL
        "61554662620217": "Coyuntura Nacional",  # Confemin
        "conulp": "Coyuntura Nacional",  # CONULP
        "Gustavo.Minaya": "Coyuntura Nacional",  # Gustavo Minaya
        "lalupa.pe": "Coyuntura Nacional",  # LA LUPA
        "LiaValderramaa": "Coyuntura Nacional",  # Lía Vladerrama
        "tomalacalletv": "Coyuntura Nacional",  # Tomalacalle Tv Page
        "vladimir.cerronrojas": "Coyuntura Nacional",  # Vladimir Cerrón
        "waykaperu": "Coyuntura Nacional",  # Wayka Page
        "rondascampesinaseindigenasperu": "Coyuntura Nacional",  # CUNARC-Perú
        "siterlimabasesregionales": "Coyuntura Nacional",  # SITER Lima Metropolitana Base Regional
        "cnddhh": "Coyuntura Nacional",  # Cnddhh Perú
        "liberacion.peru.9": "Coyuntura Nacional",  # Movimiento Liberacion
        "redmuqui": "Coyuntura Nacional",  # Red Muqui
        "pcdelp.patriaroja": "Coyuntura Nacional",  # Partido Comunista del Perú - Patria Roja
        "Sutep.Peru": "Coyuntura Nacional",  # SUTEP
        "amucep.peru": "Coyuntura Nacional",  # AMUCEP PERÚ
        "cgtp.peru": "Coyuntura Nacional",  # CGTP Perú
        "magno.ismael.palomino": "Coyuntura Nacional",  # Magno Ismael Palomino
        "antaurohumalatassooficial": "Coyuntura Nacional",  # Antauro Humala Oficial
        "diario.expreso": "Coyuntura Nacional",  # Diario Expreso
        "elena.milo.villar.milo": "Coyuntura Nacional",  # Elena Milo Villar Milo
        "61557857056881": "Coyuntura Nacional",  # La Contra
        "canalnoficial": "Coyuntura Nacional",  # Canal N
        "elmuquipodcast": "Coyuntura Nacional",  # El Muqui
        "ONAMIAP.pe": "Coyuntura Nacional",  # ONAMIAP
    }

    # Sin restriccion horaria — envio siempre al instante
    SEND_WINDOWS = {}

    # ─────────────────────────────────────────────
    # ORDEN DE ROTACION POR REGION
    # El sistema rota entre regiones en este orden
    # procesando N paginas de cada una antes de pasar a la siguiente
    # ─────────────────────────────────────────────
    REGION_ROTATION = [
        "Antamina",
        "Bechtel / Newmont",
        "Clientes Sur",
        "Clientes Norte",
        "Agricola Santa Azul",
        "Pisco",
        "Coyuntura Nacional",
    ]

    # Paginas por region por turno antes de rotar a la siguiente
    PAGES_PER_REGION_TURN = 500   # cubrir todas las páginas de cada región en un ciclo

    # ─────────────────────────────────────────────
    # FACEBOOK SCRAPING (Apify)
    # ─────────────────────────────────────────────
    FACEBOOK_PAGES = [

        # ── Antamina (72 paginas) ──
        "ABCNoticiasAncash",  # ABC Ancash
        "Zafiro.Imp",  # Áncash - Últimas Noticias
        "ancashaldia",  # Ancash al Día
        "100083039331687",  # Ancash D Impacto
        "ancashnoticiasoficial",  # Áncash Noticias
        "andres.loartelaguna",  # Andres Loarte
        "antonio.loarte.laguna.2025",  # Antonio Loarte Laguna
        "100074242929411",  # Aquia Bolognesi
        "CentralNoticiasAncash",  # Central De Noticias Ancash
        "apurayshe.sanmarquino",  # Chakuayonga Noticias
        "100063868508061",  # Lima Norte al Dia
        "100087558444092",  # Chavín de Huántar perú
        "chimboteperuhacenoticia",  # Chimbote Peru Hace Noticia
        "chimbotetelenoticias",  # Chimbote Telenoticias
        "MineraAntamina",  # Compañía Minera Antamina
        "rondascampesinaseindigenasperu",  # CUNARC-Perú
        "61560345096911",  # David Guerra
        "elsita.pereda",  # Dialogo Directo
        "Diariohuascaran",  # Diario Huascaran
        "diariopagina3huanuco",  # Diario Página3
        "61559141072588",  # El Aplicador
        "farrotv",  # FarroTv-
        "100009039772579",  # Fernando Salas Tapia
        "100008949794378",  # Heber Ocaña Granados
        "yudithtobebesita.espinoza",  # Huari Distritos
        "Huaripampamarca",  # Huaripampa - Gollanapinkush
        "ImpactoTVPeru",  # Impacto TV
        "in.situ.huari",  # In Situ Huari TV
        "infomarmadoperu2024",  # Informate.pe
        "yudithmelaniamedina",  # Jhudit Noticias Huari
        "juliocesar.rimacdamian",  # Julio Cesar Rimac Damian
        "Kaletalarevista",  # Kaleta La Revistas
        "LaCuevadelDuendeMineria",  # La Cueva del Duende
        "lenin.ramirez.397",  # Lenin Ramirez
        "marlongilbert.mogollongamarra",  # Marlon Mogollon Gamarra
        "maycol.ugarte",  # Maycol Ugarte
        "100074979673866",  # Messi Blas Vega
        "MtvNoticiasAncashPeru",  # Mtv Noticias Ancash
        "Municipalidadcatac",  # Municipalidad Distrital de Cátac
        "100089448216922",  # Noticia Caraz
        "Huaral.Noticias.Huaral",  # Noticia de Huaral
        "100063707250166",  # Pulso 7
        "LaFabulosa.pe",  # Radio La Fabulosa Oficial
        "100063835084929",  # Radio San Miguel 97.5 fm
        "roger.arizabrioso",  # Roger Ariza
        "100093310282043",  # Santa Cruz De Pichiu
        "100063502961149",  # Sin Censura
        "61561049853341",  # Tucu Willacoj
        "TV6Huarmey",  # Tv Huarmey
        "bolognesinoticias",  # Bolognesi Noticias - Actualidades de Pallasca, Áncash y el Perú.
        "Noticias.Huaraz.Peru",  # Agencia De Noticias Huaraz - Ancash
        "100087263666637",  # Huaraz con la Noticia
        "visiontvcasma",  # Vision TV Digital
        "100057328106252",  # Informativo Hoy
        "Noticiero.Huari",  # Noticiero Huari
        "Reporte6",  # Reporte 6 - Huaraz
        "huarilindo",  # Huari Lindo
        "angel.duranleon",  # Angel Duran Leon
        "100041995064479",  # El Inquisidor Noticias
        "kellyPortalatinoA",  # Kelly Portalatino Avalos
        "GobiernoRegionaldeAncash",  # Gobierno Regional de Ancash 2023-2026
        "100066327024231",  # Consejo Regional de Ancash
        "MunicipalidadDistritalDeSanMarcos2023",  # Municipalidad Distrital de San Marcos 2023 - 2026
        "radiollata92.3fm",  # RADIO LLATA 92.3 FM  (Radio Llata TV)
        "100088320954687",  # Curca-ancash Cunarc-perú
        "noticias.huarid",  # Noticias Huari Digital
        "visioninformativahuarazoficial",  # Visión Informativa Huaraz
        "erick.c.loli.morales",  # Erick C. Loli Morales  (Periodista)
        "100095310110797",  # Vehinler Yorlin Huayta Herrera
        "elfoco.peru",  # El Foco
        "ancashinfo",  # AncashInforma
        "manuelcaballeromana",  # Juan Manuel Caballero

        # ── Bechtel / Newmont (27 paginas) ──
        "DbateCajamarca",  # Dbate Cajamarca
        "escucho.ayudo.77",  # Fernando Chuquilin Ramos
        "lideradio",  # Radio Líder Cajamarca
        "RadioDiscoPlus",  # Radio Disco Plus -¡señal de Poder.
        "people",  # Ultima HORA, Celendín
        "100063883096756",  # El INFORMANTE CAJAMARCA
        "JaenNoticiasTeInforma",  # Jaén Noticias
        "100064383774051",  # Bambamarca Televisión
        "diarioelcajamarquino",  # El Cajamarquino
        "almanoticiascaj",  # Alma Noticias
        "HablaCajamarcaNoticias",  # Habla Cajamarca
        "Caxamarcaaldia",  # Caxamarca al Día
        "redmuqui",  # Red Muqui
        "espinoza.roja.yolanda",  # Yolanda Victoria Rojas Espinoza
        "100055208267487",  # Noticias en Conexión
        "PortafolioPeriodistico",  # Portafolio Periodístico Perú de Tony Alvarado A.
        "Continente820",  # Radio Continente de Cajamarca
        "elcapodelanoticia",  # El Capo
        "CodigoPeriodistico",  # Código Periodístico Cajamarca - Perú
        "MegaPlusTve",  # 𝑴𝒆𝒈𝒂 𝑷𝒍𝒖𝒔 𝑻𝒗𝒆
        "Caxamarcadigital",  # Prensa en Acción
        "radiocampesinanoticias",  # Radio Campesina
        "Hoyendia.Cajamarca",  # Hoy en Día
        "NoticiasImpactantesdeCajamarca",  # Noticias Impactantes de Cajamarca
        "ChotaTvNoticias",  # Chota TV Noticias
        "CajamarcaNoticia",  # Cajamarca Noticias
        "100087136487852",  # Noticias Región Cajamarca

        # ── Clientes Sur (67 paginas) ──
        "agrochamba",  # Agrochamba
        "agrokasaperu",  # Agrokasa
        "Agromigiva",  # Agromigiva
        "AgronegociosGenesis",  # Agronegocios Génesis
        "fullRaleoIca",  # Barrio chino ICA Perú
        "BorisBarrientosSutepRegionalYCGTPIca",  # Boris Barrientos Sutep regional Ica
        "ReddigitalCanal29",  # CANAL 29 - Red Digital ICA
        "Chincha.Central.Noticias",  # Chincha Central - Noticias
        "100063655355542",  # Chincha Noticiero
        "chinchafirstnoticias",  # Chincha Primero - Noticias
        "61556081050844",  # Chincha Provincia Segura
        "codehica",  # CODEHICA
        "100077171993787",  # Dan Sanchez
        "DebateyNoticiasIca",  # Debate y Noticias Nasca
        "DonRicardopaginaoficial",  # Don Ricardo
        "DunasTvNoticias",  # DUNAS TV ICA
        "100064071190967",  # Epa Chincha Noticias
        "61555501130868",  # EPM Noticias Nasca
        "IcaExitosa",  # Exitosa Ica
        "faustino.rodriguezquiroz",  # Faustino Rodriguez Quiroz
        "fullraleo",  # Full raleo/Ica.
        "GoreIcaOficial",  # Gobierno Regional de Ica
        "guerreradelmicrofono",  # Hablemos Claro - Noticias Ica
        "icaenportada.pe",  # Ica en Portada
        "100063992083915",  # ICA En VIVO
        "icanoticias21",  # ICA Noticias XXI
        "100077766706082",  # ICA REC-Noticias
        "100083063842591",  # Región Policial Ica
        "INFORMATEICA",  # Infórmate-Ica
        "jesus.shimabukuro",  # Jesus Shimabukuro
        "inkarry.tawainti",  # José Carlos Matías Calderón (El Inka)
        "OkeyTePone",  # La Verdad De Ica noticias
        "100072226157454",  # LAS Noticias De NASCA
        "leydy.loayzamendoza",  # Leydy Loayza Mendoza
        "marleny.jalixtohuasco",  # Marleny Jalixto Huasco (La Colla)
        "miguel.quijandria.921",  # Miguel Quijandria
        "MunicipalidadProvincialDeIca",  # Municipalidad de Ica
        "salasguadalupeica",  # Municipalidad Distrital de Salas Guadalupe
        "MORAZZANI",  # Nasca Noticias
        "100055947829841",  # Online Noticias Ica
        "61551993545297",  # Partido Comunista Peruano - Ica Page
        "people",  # Partido Comunista Peruano - Ica
        "PiscoNoticiass",  # PISCO Noticias
        "PiscoteInforma",  # Pisco te Informa
        "plusnoticias.pe",  # Plus Noticias Pisco Page
        "prensadigitalpiscoperu",  # Prensa Digital Pisco Page
        "PeriodismodeIca",  # Proyección Informativa
        "ReclutamientoAthosIca",  # Reclutamiento Ica
        "Magaly.Becerrae",  # Regidora Nancy Becerra - MD Salas, Ica
        "MarketingChincha",  # Revista Pandemia Chincha
        "SafcoPeru",  # Safco Perú
        "safresco",  # Safresco
        "100069071586685",  # STCC Ica
        "SunFruitsExportsSa",  # Sun Fruits Exports S.A.
        "100068649247660",  # Susan Quintanilla
        "SutepRegionalIcaOficial",  # Sutep Regional Ica
        "transmisiones.pisco",  # Transmisiones Pisco Page
        "tvochincha",  # TVO Chincha
        "UnionChinchana",  # Unión Chinchana
        "GrupoVanguardInternacional",  # Grupo Vanguard Internacional
        "pedrovictor.garciafernandez",  # Pedro Víctor García Fernández
        "61567522762662",  # Agrokasa Pisco (FB)
        "grupoathosoficial",  # Athos (FB)
        "chapi.com.pe",  # Chapi (FB)
        "agricoladonluis",  # Don Luis (FB)
        "family.farms.oficial",  # Family Farms (FB)
        "agricolariachuelo",  # Riachuelo (FB)

        # ── Agro Norte (27 paginas) ──
        "adasperu.oficial",  # ADAS
        "agualima.peru",  # AguaLima
        "aldopaginaoficial",  # Aldo Carlos Mariños
        "AzucareraCasaGrande1",  # CasaGrande
        "CEPESRURAL",  # CEPES
        "DanperPeru",  # Danper
        "ExitosaTrujillo",  # Exitosa Trujillo
        "61550669891428",  # Federacion provincial de Rondas Campesinas de viru
        "felipe.arteagasaavedra.5",  # Felipe Arteaga Saavedra
        "FetsaRLL",  # FETSA
        "greenperurrhh",  # GreenPeru
        "gruporocio.pe",  # Grupo Rocio
        "hassperu",  # Hass Perú
        "hortifrutperu",  # Hortifrut Perú
        "KeBuenaNoticiasPaginaOficiall",  # Ke Buena Noticias
        "MissionProducePeru",  # Mission
        "noticiasviruoficial",  # Noticias Virú
        "pedro.campospalacios",  # Pedro Campos Palacios
        "100071043856616",  # Red de Noticias - La Libertad
        "100090935898268",  # Sapitos al Rescate
        "AgroindustrialLaredo",  # Sol de Laredo
        "walter.campos.palacios",  # Walter Campos Palacios
        "100064024635914",  # CHAO Noticias Tv Digital
        "AgricolaCerroPrietoSA",  # Agrícola Cerro Prieto
        "GiddingsBerriesPeru",  # GIDDINGS (FB)
        "100083411587501",  # TALSA (FB)
        "westfaliafruitperu",  # WESTFALIA FRUIT (FB)

        # ── Agricola Santa Azul (4 paginas) ──
        "juan.jironsanchez",  # Juan Jiron Sanchez
        "contrapoder.live",  # Cuarto  Poder
        "municiaplidaddistritaldesupe20192022",  # Municipalidad de Supe
        "MunicipalidadDeBarranca",  # Municipalidad Provincial de Barranca

        # ── Pisco (16 paginas) ──
        "PiscoNoticiass",  # PISCO Noticias
        "PiscoteInforma",  # Pisco te Informa
        "plusnoticias.pe",  # Plus Noticias Pisco Page
        "prensadigitalpiscoperu",  # Prensa Digital Pisco Page
        "LaVozdePiscoOficial",  # La Voz de Pisco
        "MuniHuancano",  # Municipalidad Distrital de Huáncano
        "100083218815937",  # Pisqueño Verídico
        "AngelRojas.ComnSoc",  # Angel Pisco
        "munidistritalhumay",  # Municipalidad Distrital de Humay
        "megavision.pisco",  # Megavision Pisco
        "jaime.lorenzo.fernandez.hernandez.2024",  # Humay Tv
        "carmen.herrerasolis.754",  # Carmen Herrera Solis
        "mario.rengifo.125",  # Mario Rengifo
        "SANCLEMENTETEINFORMA",  # San Clemente Te Informa
        "100071701105635",  # Humay : Tierra Santa
        "ContactoPisco",  # Contacto Pisco

        # ── Coyuntura Nacional (26 paginas) ──
        "CoordinadoraNacionalUnitariadeLuch4",  # CNUL
        "61554662620217",  # Confemin
        "conulp",  # CONULP
        "Gustavo.Minaya",  # Gustavo Minaya
        "lalupa.pe",  # LA LUPA
        "LiaValderramaa",  # Lía Vladerrama
        "tomalacalletv",  # Tomalacalle Tv Page
        "vladimir.cerronrojas",  # Vladimir Cerrón
        "waykaperu",  # Wayka Page
        "rondascampesinaseindigenasperu",  # CUNARC-Perú
        "siterlimabasesregionales",  # SITER Lima Metropolitana Base Regional
        "cnddhh",  # Cnddhh Perú
        "liberacion.peru.9",  # Movimiento Liberacion
        "redmuqui",  # Red Muqui
        "pcdelp.patriaroja",  # Partido Comunista del Perú - Patria Roja
        "Sutep.Peru",  # SUTEP
        "amucep.peru",  # AMUCEP PERÚ
        "cgtp.peru",  # CGTP Perú
        "magno.ismael.palomino",  # Magno Ismael Palomino
        "antaurohumalatassooficial",  # Antauro Humala Oficial
        "diario.expreso",  # Diario Expreso
        "elena.milo.villar.milo",  # Elena Milo Villar Milo
        "61557857056881",  # La Contra
        "canalnoficial",  # Canal N
        "elmuquipodcast",  # El Muqui
        "ONAMIAP.pe",  # ONAMIAP
    ]

    POSTS_PER_PAGE = 8
    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "bridge")


    # ─────────────────────────────────────────────
    # WHATSAPP BRIDGE (whatsapp-web.js)
    # ─────────────────────────────────────────────
    BRIDGE_URL   = os.getenv("BRIDGE_URL",   "http://localhost:3000")
    BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN", "protecta2026")

    # ─────────────────────────────────────────────
    # GOOGLE SHEETS — mismo Sheets del Google Form
    # ─────────────────────────────────────────────
    # Poner en True cuando tengas el credentials.json de Google
    SHEETS_ENABLED        = os.getenv("SHEETS_ENABLED", "false").lower() == "true"
    GOOGLE_CREDENTIALS_FILE = "credentials.json"
    SPREADSHEET_ID = os.getenv(
        "SPREADSHEET_ID",
        "1hWfu3EymR5Li4qWQv3RcBaaJruI9wOA0m44KnTGnZhs"
    )
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
        "Petrotal",
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
        "AREQUIPA":         ["Clientes Sur"],
        # Agroindustria Norte / Lima costa
        "LA LIBERTAD":      ["Clientes Norte"],
 
        "LIMA BARRANCA":    ["Agrícola Santa Azul", "Agrícola Huarmey"],
        "LIMA SUPE":        ["Agrícola Santa Azul"],
        "LIMA HUAURA":      ["Agrícola Santa Azul"],
        "LIMA HUARAL":      ["Clientes Norte"],
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
        "Agrícola Santa Azul":              "Agrícola Santa Azul",
        "Agrícola Huarmey":                 "Clientes Norte",
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
        "Petrotal":                         "Petrotal",
        "Ninguno (Coyuntura Nacional)":     "Coyuntura Nacional",
    }

    # ─────────────────────────────────────────────
    # RUBRO POR CLIENTE (autocompletado)
    # ─────────────────────────────────────────────
    CLIENTE_TO_RUBRO = {
        "Antamina":                         "Minería",
        "Bechtel / Newmont":                "Minería",
        "Petrotal":                         "Hidrocarburos",
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
            "HUARAZ": ["ACOBAMBA", "AMASHCA", "AQUIA", "ARI", "ASUNCION", "CATAC", "CHACOS", "CHAVÍN DE HUANTAR", "COCHAS", "COMAS", "HUARAZ", "HUARI", "HUATA", "HUAYLLA", "JANGAS", "LA LIBERTAD", "MARCA", "MARISCAL CASTILLA", "OLLEROS", "PAMPAS", "PARIACOTO", "PIRA", "PUEBLO LIBRE", "PUIRA", "RECUAY", "SAN MIGUEL DE AVE", "SAN RAFAEL"],
            "AIJA": ["AIJA", "CORIS", "HUACLLAN", "SUCCHA"],
            "BOLOGNESI": ["AIJA", "AQUIA", "BOLOGNESI", "CHIQUIAN", "HUALLANCA", "HUAMANIN", "HUARAZ", "PACLLON", "SAN MIGUEL DE AVE"],
            "CARHUAZ": ["ACOPAMPA", "AMASHCA", "CARHUAZ", "CHINGALPO", "LA PAMPA", "LAJAS", "MARCARA", "PARIACOTO", "SAN MIGUEL DE AVE", "TINCO", "UCHUCCHACUA"],
            "CASMA": ["CASMA", "COMANDANCIA", "DOLORES", "HUACHO", "NUÑOA", "YAUTAN"],
            "CORONGO": ["ACO", "CORONGO", "CUSCA", "YANAC"],
            "HUARI": ["ANRA", "ANGUIA", "ASUNCION", "CHAVÍN DE HUANTAR", "HUACHIS", "HUARI", "HUARANCHAL", "HUASO", "JIRCÁN", "LACSABAMBA", "MARAYCAY", "PAUCAS", "PIRA", "SAN PEDRO DE CHANA"],
            "HUARMEY": ["CASMA", "CHAVÍN DE HUANTAR", "COCHAS", "CULEBRAS", "HUACHO", "HUARMEY", "HUAYAN", "HUAYNA", "SUPE PUERTO", "VÉGUETA"],
            "HUAYTARA": ["AYAYA", "CASTROVIRREYNA", "COCHAS", "HUAYTARA", "LACHUAS", "MIRAFLORES", "QUERCO", "SANTO DOMINGO"],
            "MARISCAL CASTILLA": ["ACOPAMPA", "CHACAS", "CHIQUIAN", "HUALLANCA", "HUAMANIN", "HUARAZ"],
            "OCROS": ["CAJAMARQUILLA", "COCHAS", "OCROS", "PUQUIO", "SAN CRISTÓBAL", "SAN PEDRO"],
            "PALLASCA": ["BOLOGNESI", "CATAC", "COCHAS", "HUACASCHUCHO", "LACABAMBA", "PALLASCA", "PAMPAS", "SANTA ROSA"],
            "POMABAMBA": ["ACOBAMBA", "HUARAZ", "NISCOSHUAYLLA", "PACLLON", "POMABAMBA", "QUINHUABAMBA"],
            "RECUAY": ["ACOBAMBA", "CATAC", "COTAPARACO", "HUARAZ", "HUANCAHUANCA", "MARCA", "RECUAY", "TICAPAMPA"],
            "SANTA": ["CASMA", "CHIMBOTE", "HUACHO", "NUEVO CHIMBOTE", "SANTA"],
            "SIHUAS": ["ACOBAMBA", "AQUIA", "CASHAPAMPA", "COLQUIOC", "HUACHIS", "HUARAZ", "HUASO", "SIHUAS"],
            "TINCO": ["ACOPAMPA", "CARHUAZ", "COCHAPETI", "COSA", "HUACASCHUCHO", "HUACLLACYÁN", "HUANCAHUANCA", "JECUPEN", "OJOSHUAIN", "TINCO"],
            "YUNGAY": ["ANCASH", "CARHUAZ", "CASCAPAMPA", "COCHAS", "HUARAZ", "LLAMA", "MATACOTO", "TINCO", "YUNGAY"],
        },
        "CAJAMARCA": {
            "CAJABAMBA": ["BAMBAMARCA", "CAJABAMBA", "CONDEBAMBA"],
            "CELENDÍN": ["BAMBAMARCA", "CELENDÍN", "CHUMUCH", "DV. BELEN", "LAJAS", "SOROCHUCO"],
            "CHOTA": ["BAMBAMARCA", "BAMBAMQUILLO", "CATILLA", "CHIGUIRIP", "CHOTA", "LAJAS", "TACABAMBA"],
            "CONTUMAZÁ": ["BAMBAMARCA", "CHILETE", "CONTUMAZÁ", "CURIMBA", "GUAMBOS", "RAYAN", "SAN BENITO", "TANTARICA", "YONAN"],
            "HUALGAYOC": ["BAMBAMARCA", "CHIGUIRIP", "HUALGAYOC", "HUAMBOS", "PIMPINGOS"],
            "HUAMACHUCO": ["BAMBAMARCA", "COCHORCO", "HUAMACHUCO", "HUAMALI", "HUANCAY", "LA CUESTA", "ANGUIA", "LAJAS", "MARCABAL", "SARTIMBAMBA"],
            "JAÉN": ["JAÉN", "PUCARÁ", "SALLIQUE"],
            "SAN IGNACIO": ["NAMBALLE", "PUCARÁ", "SAN IGNACIO"],
            "SAN MIGUEL": ["BOLOGNESI", "CATILLA", "CHIGUIRIP", "LAJAS", "TACABAMBA", "SAN MIGUEL"],
            "SANTA CRUZ": ["BAMBAMARCA", "CHIGUIRIP", "LAJAS", "SANTA CRUZ", "TACABAMBA"],
        },
        "HUANUCO": {
            "AMBO": ["AMBO", "CAURI", "COLPAS", "CONCHAMARCA", "HUACAR", "HUACHIS", "HUANABAMBA", "LACATAMBO", "PAMPAS", "QUIVILLA", "SAN FRANCISCO", "TOMAY KICHWA"],
            "DOS DE MAYO": ["ASCENSION", "CHUQUIS", "CORAPONGO", "DOS DE MAYO", "LA MORADA", "MARISCAL CASTILLA", "PACHAS", "QUIVILLA", "RIPAN", "SILLAPATA", "YANAHUANCA"],
            "HUACAYBAMBA": ["COCHABAMBA", "HUACAYBAMBA", "PINRA", "QUIULLA"],
            "HUANUCO": ["AMARILIS", "CHAVINILLO", "CHURUBAMBA", "CUSMA", "HUANUCO", "HUACHIS", "HUACRACHUCO", "HUACAR", "HUANCACHUPA", "HUANCAMBO", "HUAQUIN", "HUARI", "HUARHUA", "JACAS GRANDE", "JACAS CHICO", "LEONCIO PRADO", "LLATA", "MARGOS", "MIRAFLORES", "MOLINO", "MONZON", "NUNOA", "ORIZABA", "PILLCO MARCA", "RONDOS", "SAN FERNANDO", "SAN FRANCISCO DE ASIS", "SAN JUAN DE MOTUPE", "SAN RAFAEL", "SANTA BARBARA", "SANTA MARIA DEL VALLE", "SAYAN", "TOMAY KICHWA", "UNCHOG", "XICRA", "YARUMAYO"],
            "HUARIACA": ["ANDA", "CHACABAMBA", "HUAMBOS", "HUANAHUANUCA", "HUANCHAC", "HUANCHAN", "HUANIPATIA", "HUANQUI", "HUANTA", "HUARACA", "HUARIACA", "HUARICHACA", "HUARÍN", "LLATA", "NATIVIDAD", "PAMPAS", "QUERO", "QUICHCAS", "RONDOS", "SANTA ROSA"],
            "LEONCIO PRADO": ["CONSTITUCIÓN", "DANIEL ALOMÍA ROBLES", "HERMILIO VALDIZÁN", "JIGUAS", "JOSÉ CRESPO Y CASTILLO", "LUYANDO", "MARISCAL CASTILLA", "ÑUFLO DE CHÁVEZ", "PACHITEA", "PUCALLPA", "PUEBLO NUEVO", "REMO", "RONDOS", "SANTA ROSA", "SUPTE", "TÍNGORAS", "TINGO MARÍA", "TULUMAYO", "UCHIZA"],
            "MARAÑÓN": ["BAGAZÁN", "CHAGLLA", "CHUPAMARCA", "HUACRACHUCO", "HUACAR", "HUALLAGA", "HUAMBO", "HUAMBOS", "HUANTA", "HUNUCO", "LLATA", "MARAÑÓN", "MONZÓN", "PAMPAS", "PUÑOS", "QUICHCAS", "SILLACTA", "TAMBO", "UCHIZA"],
            "PACHITEA": ["AMBO", "CAURI", "CHAGLLA", "HUACACHUCO", "HUACHIS", "HUACHÓN", "HUAMBOS", "LLATA", "MARISCAL CASTILLA", "MOLINO", "PACHITEA", "PUERTO INCA", "QUICHCAS", "San MIGUEL", "Tambo"],
            "PUERTO INCA": ["CHAGLLA", "HUACHÓN", "LLATA", "MARISCAL CASTILLA", "PUERTO INCA", "TAMBO"],
            "TINGO MARIA": ["ANUHUATI", "CHAGLLA", "MARISCAL CASTILLA", "RONDOS", "SAN CRISTOBAL", "SANTA ROSA", "TINGO MARIA"],
        },
        "LA LIBERTAD": {
            "TRUJILLO": ["AGUSTINO", "ALEXANDER VON HUMBOLDT", "AMERICANO", "ARTHUR", "CENTRO", "CHICAMA", "ESPAÑA", "FLORENCIA", "GRAU", "ITCHIMIS", "JUNÍN", "LA PAZ", "LARGO", "MARAÑÓN", "MARISCAL CASTILLA", "MÉXICO", "MIRAFLORES", "MONSERRATE", "NACIONAL", "ORMEÑO", "PANDO", "PURÍSIMA", "SANTA MARÍA", "SCHOFIELD", "SIMÓN BOLÍVAR", "TRUJILLO"],
            "ASCOPE": ["ASCOPE", "CHEPÉN", "JEQUETEPEQUE", "MAGDALENA DE CAO", "PAIJÁN"],
            "BOLOGNESI": ["BOLOGNESI", "CHIPAO", "SAYAPULLO"],
            "CHEPÉN": ["CHEPÉN", "PACANGA"],
            "CHICAMA": ["CHICAMA", "PAIJAN"],
            "JICAMARCA": ["JICAMARCA", "JOSÉ MANUEL QUIROZ"],
            "JULCÁN": ["HUASO", "JULCÁN", "QUIRUVILCA"],
            "MOTUPE": ["MOTUPE", "QUIRUVILCA"],
            "OTUZCO": ["AGALLPAMPA", "ASQUIPAMPA", "BULDIBUYO", "CHARAT", "OTUZCO", "PARANDAY", "USQUIL"],
            "PACASMAYO": ["CHÉRREPE", "GUADALUPE", "JEQUETEPEQUE", "PACASMAYO", "SAN PEDRO DE LLOC"],
            "PATAZ": ["BULDIBUYO", "ANGUIA", "BAMBAMARCA", "BAMBAMQUILLO", "BULDIBUYO", "ANGUIA", "CABANA", "CHILLIA", "CHUMBIBONGO", "HUAMBACHANO", "HUAMBO", "HUAMOTÁN", "HUANCASPATA", "HUANCAYO", "HUANTA", "HUANZA", "HUARIPAMPA", "HUARIPAMPA GRANDE", "HUARMACA", "HUARMACA BAJA", "HUARMACA GRANDE", "HUARMEY", "HUAROCHIRÍ", "HUARÓN", "HUARQUI", "HUARRANGAL", "HUARRANQUIYOC", "HUARRAPAMPA", "HUARRATAMBO", "HUARRANCAYO", "HUARRANQUIYOC", "HUARRANQUIYOC", "HUARRAQUIYOC", "HUARRARÁ", "HUARRANQUIYOC", "HUARRANQUIYOC", "HUARRARA", "HUARRANQUIYOC", "HUARRÓ", "HUARYAN", "HUASAHUASI", "HUASCACHINA", "HUASCARÁN", "HUASCARÁN", "HUASCARAY", "HUASCAS", "HUASCCACANCHA", "HUASCACANCHA", "HUASCHI", "HUASCOCCHADA", "HUASCOMAYO", "HUASCRACHUCO", "HUASCUY", "HUASTAY", "HUASTAYO", "HUASTAYOC", "HUASUAYU", "HUASTAYOC", "HUASTAYOC", "HUASTAYQUIYOC", "HUASTAYQUYOC", "HUATA", "HUATACAY", "HUATACAYO", "HUATAJAMBO", "HUATAJAMBO", "HUATAJAMBO", "HUATAJAMBO", "HUATAMACHAY", "HUATAMODAHUANO", "HUATANAY", "HUATANGAY", "HUATANGAY", "HUATANOR", "HUATAPAMPA", "HUATAPAMPA", "HUATAPUCA", "HUATAQUI", "HUATAQUICHA", "HUATAQUI", "HUATARES", "HUATAREQUI", "HUATARIPAMPA", "HUATARIPAMPA", "HUATARIQUIMBA", "HUATARITAMBO", "HUATAROAMAYO", "HUATARQUIYOC", "HUATARRACA", "HUATARRAMA", "HUATARREMATE", "HUATARRIALTO", "HUATARRIMBA", "HUATARRÍO", "HUATARRORQUIYOC", "HUATARSAHUANAY", "HUATARSUCCHA", "HUATASALLA", "HUATASANCO", "HUATASAYO", "HUATASAYA", "HUATASAYANA", "HUATASECUI", "HUATASEMA", "HUATASENA", "HUATASENACHIMBO", "HUATASEPAMPA", "HUATASI", "HUATASIA", "HUATASICA", "HUATASIGA", "HUATASILLA", "HUATASIMANA", "HUATASINA", "HUATASINGA", "HUATASINO", "HUATASIO", "HUATASISICA", "HUATASIZGA", "HUATASJA", "HUATASJAI", "HUATASLLAHUA", "HUATASMA", "HUATASMAMAY", "HUATASMALCA", "HUATASMARA", "HUATASMASCA", "HUATASMASILLA", "HUATASMAY", "HUATASPAMPA", "HUATASPAPI", "HUATASPAQUI", "HUATASQUELLO", "HUATASRA", "HUATASRAYA", "HUATASRICRA", "HUATASRIO", "HUATASROMA", "HUATASROMAQUE", "HUATASROPA", "HUATASROQUE", "HUATASRUMI", "HUATASRUMI", "HUATASRÚN", "HUATASRUMI", "HUATASRUNUNCA", "HUATASRUNYO", "HUATASRUTO", "HUATASSTAMBO", "HUATASSTAMBO", "HUATASTAMBO", "HUATASSTAMBO", "HUATASSTAMBO", "HUATASTAMOCHA", "HUATASTANA", "HUATASTANCHO", "HUATASTAÑO", "HUATASTAO", "HUATASTAPA", "HUATASTAPAMPA", "HUATASTAPIA", "HUATASTAPUCHA", "HUATASTAR", "HUATASTARA", "HUATASQUE", "HUATASTAYA", "HUATASTAYO", "HUATASTAYOC", "HUATASTAYQUIYOC", "PATAZ"],
            "SANCHÉZ CARRIÓN": ["ACOPALCA", "ACZO", "AGALLPAMPA", "AQUIA", "ASQUIPAMPA", "BULDIBUYO", "CACHICADAN", "CHARAT", "CHUCCHUCHAMBI", "CHUGAY", "CHURCAMPA", "CHURUBAMBA", "COEBAMBA", "COCHORCO", "COSHCAMARCA", "CULANTRILLO", "CUNCATAMBO", "CUYAMALCA", "CUZMALCA", "DIOS NUESTRO", "FUERTE MARAÑÓN", "GUALLAN", "HUAJAMBO", "HUAMBACHANO", "HUAMBO", "HUAMOTÁN", "HUANCACAMPA", "HUANCACHACRA", "HUANCACHIMBA", "HUANCACIMA", "HUANCACIRCA", "HUANCACIRQUI", "HUANCACIRQUICHINA", "HUANCACOCHA", "HUANCACOYAMARCA", "HUANCÁCUPE", "HUANCADIPA", "HUANCAHUARINCA", "HUANCAHUASI", "HUANCAIMA", "HUANCAIÑA", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCAJUYO", "HUANCALIMA", "HUANCALLIMA", "HUANCAMAL", "HUANCAMAPA", "HUANCAMAPAMPA", "HUANCAMARA", "HUANCAMARCA", "HUANCAMARCAMARCA", "HUANCAMARO", "HUANCAMARQUINA", "HUANCAMATA", "HUANCAMATACTA", "HUANCAMATAMBO", "HUANCAMAYA", "HUANCAMAYO", "HUANCAMAYO", "HUANCAMAYON", "HUANCAMAYORDOMO", "HUANCAMAYO", "HUANCAMAYO", "HUANCAMAYO", "HUANCAMAYA", "HUANCAMAYA", "HUANCAMAYACASA", "HUANCAMAYOCHA", "HUANCAMAYOCHACRA", "HUANCAMAYOCHA", "HUANCAMAYOCHICO", "HUANCAMAYOCUCHO", "HUANCAMAYOCHIMBO", "HUANCAMAYOCHUCHA", "HUANCAMAYOCOCHA", "HUANCAMAYOCOIMA", "HUANCAMAYOCONA", "HUANCAMAYOCONDOR", "HUANCAMAYOCONDORCHUCHA", "HUANCAMAYOCONDORHUAYCOCHUCHA", "HUANCAMAYOCONDORPUQUIO", "HUANCAMAYOCONDOR", "HUANCAMAYOCONDOR", "HUANCAMAYOCOCONDOR", "HUANCAMAYOCHO", "HUANCAMAYOCHUCHAC", "HUANCAMAYOCHUCHAGUA", "HUANCAMAYOCHUCHAHUACA", "HUANCAMAYOCHUCHAHUAN", "HUANCAMAYOCHUCHAHUANUCA", "HUANCAMAYOCHUCHAHUANGA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHACO", "HUANCAMAYOCHUCHACHO", "HUANCAMAYOCHUCHACHUCHA", "HUANCAMAYOCHUCHACO", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "HUANCAMAYOCHUCHA", "PATAZ", "HUAMACHUCO", "SANCHÉZ CARRIÓN"],
            "SANTIAGO DE CHUCO": ["AGALLPAMPA", "AGUADA", "AMANERA", "ARCABUCO", "ASQUIPAMPA", "ASQUIPAMPA", "ASQUIPAMPA", "ASQUIPAMPA", "AZUFRERAL", "AZUFRERAL", "AZUFRERAL", "AZUFRERA", "AYABACA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACA", "AYAMBLACACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLA CHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "AYAMBLACHIMBA", "SANTIAGO DE CHUCO", "USQUIL", "AGALLPAMPA", "USQUIL"],
            "VIRÚ": ["CASA GRANDE", "PAIJAN", "VIRU", "VIRU"],
        },
        "ICA": {
            "CHINCHA": ["ALTO LARAN", "CHAVIN", "CHINCHA ALTA", "CHINCHA BAJA", "EL CARMEN", "GROCIO", "TAMBO DE MORA"],
            "ICA": ["ICA", "LA TINGUIÑA", "LOS AQUIJES", "OCUCAJE", "PACHACAMAC", "PARCONA", "PUEBLO NUEVO", "SALAS", "SAN JOSE DE LOS MOLINOS", "SAN JUAN BAUTISTA", "SANTIAGO", "TATE", "YAUCA DEL NAZCA"],
            "NAZCA": ["ACARI", "CHANGUILLO", "EL INGENIO", "MARCONA", "NASCA", "OCUCAJE", "PUQUIO"],
            "PALPA": ["LLIPATA", "PALPA", "SANTA ROSA"],
            "PISCO": ["HUANCANO", "HUMAY", "INDEPENDENCIA", "PARACAS", "PISCO", "SAN ANDRÉS DE PISCO", "SAN CLEMENTE", "TUPAC AMARU"],
        },
        "LIMA": {
            "BARRANCA": ["ALMIRANTE COCHRANE", "BARRANCA", "PARAMONGA", "PATIVILCA", "SUPE", "SUPE PUERTO"],
            "SUPE": ["BARRANCA", "SUPE", "SUPE PUERTO"],
            "HUAURA": ["ALMIRANTE COCHRANE", "HUACHO", "HUALMAY", "HUANUSCO", "HUAURA", "LEYVA JORGE CHAVEZ", "SAYAN", "VEGUETA"],
            "HUARAL": ["ACOS", "CHANCAY", "CHICAMA", "HUARAL", "OQUENDO", "SANTA ROSA DE QUIVES", "VEINTISEÍS DE OCTUBRE"],
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
    
    # Nivel mínimo para NACIONAL (solo ALRT y CRIT, no INFO)
    NACIONAL_MIN_LEVEL = "ALRT"  # Solo alertas importantes



    # ─────────────────────────────────────────────
    # WEBHOOKS (WEBHOOK_SERVER)
    # ─────────────────────────────────────────────
    WEBHOOKS_ENABLED = os.getenv("WEBHOOKS_ENABLED", "true").lower() == "true"
    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # Opcional: para validar webhooks
    
    # Si True, mantiene polling RSS como fallback
    # Si False, solo procesa webhooks
    WEBHOOKS_WITH_POLLING_FALLBACK = os.getenv("WEBHOOKS_WITH_POLLING_FALLBACK", "true").lower() == "true"