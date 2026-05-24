"""
deduplicator.py — Evita enviar la misma noticia dos veces.

Tres niveles de deduplicacion:
  1. Por URL exacta del post (tabla 'processed')
  
  2. Por contenido exacto — si dos posts hablan del mismo evento
     basándose en: departamento + provincia + subcategoria + palabras_clave
     
  3. Por similitud de TÍTULO — El más importante para evitar duplicados
     de diferentes fuentes en el mismo bundle. Usa:
     - Similitud Jaccard >= 60% en títulos
     - Levenshtein distance en títulos normalizados
     - Ventana de 12 horas por departamento
     
  4. Por similitud de DESCRIPCIÓN — Si títulos no matchean pero contenido
     es muy similar (>= 70% Jaccard en descripción)
"""

import os
import re
import hashlib
import logging
import unicodedata
import psycopg2
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

log = logging.getLogger(__name__)

# Umbrales de similitud — ¡MUCHO MÁS AGRESIVOS para capturar variaciones!
JACCARD_THRESHOLD_TITULO = 0.35       # ⭐ REDUCIDO: 0.50 → 0.35 (captura "Disparo" vs "Homicidio" + mismo lugar)
JACCARD_THRESHOLD_CONTENIDO = 0.40    # ⭐ REDUCIDO: 0.55 → 0.40 (más sensible a parafraseos)
LEVENSHTEIN_THRESHOLD = 0.60          # ⭐ REDUCIDO: 0.65 → 0.60 (Nuevo Chimbote ≈ Chimbote)
SIMILITUD_EVENTO_MIN = 0.55           # Para detección semántica de mismo evento

# Ventanas de búsqueda
DEDUP_WINDOW_HOURS = 24               # ⭐ AMPLIADO: 12 → 24h (no repita en todo el día)
DEDUP_SAME_BUNDLE_HOURS = 0.5         # 30 MINUTOS - mismo bundle = mismo evento
DEDUP_SAME_SOURCE_HOURS = 6           # Ventana para misma fuente
DEDUP_SAME_LOCATION_HOURS = 0.25      # 15 minutos - mismo depto + prov = probablemente dup

# Stopwords español + palabras frecuentes en titulares
_STOPWORDS_ES = {
    "el","la","los","las","de","del","en","a","y","o","u","un","una","unos","unas",
    "que","se","por","con","para","su","sus","es","al","lo","como","mas","pero","le",
    "ya","este","esta","estos","estas","fue","ha","han","hay","ser","son","muy",
    "sin","sobre","tras","entre","donde","cuando","tambien","todo","todos","toda",
    "todas","esto","eso","hace","hizo","tuvo","dijo","ante","ese","esa","esos","esas",
    "sera","ser","fue","fui","tras","cada","otro","otra","otros","otras","desde",
    "hasta","aun","aun","tan","ahi","alli","aqui","yo","tu","el","ella","nos",
}

# Palabras clave que indican un EVENTO (para fingerprinting mejorado)
_EVENT_KEYWORDS = {
    "muerta", "muerto", "muerte", "homicidio", "asesinato", "crimen",
    "accidente", "choque", "colisión", "disparo", "tiroteo", "balazo",
    "incendio", "fuego", "explosión", "derrumbe", "desmoronamiento",
    "inundación", "flood", "deslizamiento", "caída", "derrumbe",
    "robo", "asalto", "hurto", "robobanc", "robocasa", "secuestro",
    "violencia", "agresión", "ataque", "combate", "enfrentamiento",
    "arrestado", "detenido", "capturado", "aprehendido", "encarcelado",
    "herido", "lesionado", "grave", "coma", "hospital", "urgencia",
    "desaparecido", "extraviado", "hallado", "búsqueda", "rescate",
    "canon", "minería", "explotacion", "protestas", "bloqueo", "huelga",
    "corte", "vía", "carretera", "emergencia", "estado de emergencia",
}

# Mapeo de ubicaciones normalizadas (variaciones → forma canónica)
_LOCATION_NORMALIZE = {
    "nuevochimbote": "chimbote",
    "nuevo chimbote": "chimbote",
    "villa maria": "villa maría",
    "chanchamayo": "chanchamayo",
    "pucallpa": "pucallpa",
    "huancayo": "huancayo",
}


def _strip_accents(s: str) -> str:
    """Remueve tildes y diacríticos."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _normalize_text(s: str) -> str:
    """Normaliza texto: lowercase, sin tildes, solo letras y números."""
    s = _strip_accents(s.lower())
    s = re.sub(r'[^a-z0-9\s]', ' ', s)  # Solo letras, números, espacios
    return re.sub(r'\s+', ' ', s).strip()


def _words_set(text: str) -> set:
    """Tokeniza: lowercase, sin tildes, solo letras, sin stopwords, longitud >= 3."""
    if not text:
        return set()
    norm = _strip_accents(text.lower())
    words = re.findall(r"[a-z]+", norm)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS_ES}


def _jaccard(a: set, b: set) -> float:
    """Calcula similitud Jaccard entre dos sets de palabras."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """
    Calcula similitud usando SequenceMatcher (más rápido que Levenshtein puro).
    Retorna 0.0 a 1.0 donde 1.0 es idéntico.
    """
    return SequenceMatcher(None, s1, s2).ratio()

def _normalize_url(url: str) -> str:
    """
    Normaliza URLs para evitar duplicados con parámetros distintos.
    Elimina utm, fbclid, mibextid, ref, locale y slash final.
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())

    clean_query = []
    for k, v in parse_qsl(parsed.query):
        key = k.lower()
        if not key.startswith("utm_") and key not in {
            "fbclid", "mibextid", "ref", "locale"
        }:
            clean_query.append((k, v))

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip("/"),
        "",
        urlencode(clean_query),
        ""
    ))


def _ai_are_same_event(titulo1: str, titulo2: str, desc1: str, desc2: str) -> bool:
    """
    NIVEL 6 FALLBACK: Usa IA para detectar si dos alertas hablan del MISMO EVENTO.
    
    Casos de uso:
    - "Disparo en Chimbote" vs "Homicidio en Chimbote" (mismo evento, diferente nivel)
    - "Empresario muere" vs "Hombre fallece" (parafraseo semántico)
    - "Canon minero aumenta" vs "Minería crecimiento" (mismo tema, diferentes palabras)
    
    IMPORTANTE: Solo se llama cuando otros niveles fallan pero hay similitud media.
    Es una RED FINAL para no dejar escapar duplicados.
    """
    try:
        import requests
        from config import Config
        
        config = Config()
        ai_provider = getattr(config, "AI_PROVIDER", "openai").lower()
        
        prompt = f"""Analiza estos dos titulares de noticias. ¿Reportan el MISMO EVENTO?
Responde con una palabra: "SI" o "NO"

TITULO 1: {titulo1[:100]}
{desc1[:80]}

TITULO 2: {titulo2[:100]}
{desc2[:80]}

Respuesta:"""
        
        # Usar OpenAI como fallback predeterminado
        if ai_provider == "openai":
            key = config.OPENAI_API_KEY
            if not key:
                return False
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0
                },
                timeout=5
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip().upper()
                # Comparación EXACTA: evita falsos positivos como "SIN DUDA NO" matcheando "SI"
                first_token = re.split(r'[\s.,;:!?]+', content, maxsplit=1)[0]
                if first_token == "SI":
                    log.info(f"[Dedup] ⚡ NIVEL 6 (IA Semántica) → DUPLICADO DETECTADO")
                    return True
            return False
        
        # Otros providers podrían añadirse aquí si es necesario
        return False
    
    except Exception as e:
        log.debug(f"[Dedup] IA fallback no disponible: {e}")
        return False


def _extract_event_signature(text: str) -> str:
    """
    Extrae firma de evento MEJORADA: ubicación normalizada + números + palabras clave de evento.
    Ej: "Canon minero 576.4M Cajamarca" → "cajamarca_mineria_576"
         "Disparo Nuevo Chimbote" → "chimbote_arma"
         "Homicidio Chimbote" → "chimbote_muerte"
    
    Esto ayuda a detectar el MISMO EVENTO reportado de forma diferente.
    """
    if not text:
        return ""
    
    # Normalizar
    text_norm = _strip_accents(text.lower())
    
    # Extraer ubicación (palabras de 4+ chars al inicio, o palabras conocidas de ciudades)
    location_words = []
    for word in text_norm.split():
        word_clean = re.sub(r'[^a-z]', '', word)
        if len(word_clean) >= 4 and word_clean not in _STOPWORDS_ES:
            # Aplicar mapeo de normalización
            normalized = _LOCATION_NORMALIZE.get(word_clean, word_clean)
            if normalized not in location_words:
                location_words.append(normalized)
            if len(location_words) >= 2:  # Max 2 ubicaciones
                break
    
    location_sig = "_".join(location_words[:2]) if location_words else ""
    
    # Extraer palabras clave de EVENTO (muertes, accidentes, etc)
    event_keyword = ""
    for keyword in _EVENT_KEYWORDS:
        if keyword in text_norm:
            event_keyword = keyword
            break
    
    # Extraer números significativos (cantidades, dinero)
    numbers = re.findall(r'\d+[.,]?\d*', text)
    number_sig = numbers[0] if numbers else ""
    
    # Construir firma
    sig_parts = []
    if location_sig:
        sig_parts.append(location_sig)
    if event_keyword:
        sig_parts.append(event_keyword[:8])  # Max 8 chars
    if number_sig:
        sig_parts.append(number_sig.replace('.', '').replace(',', '')[:6])  # Max 6 chars
    
    sig = "_".join(sig_parts)
    return sig[:120] if sig else ""


def _get_conn():
    url = os.environ.get("DATABASE_URL")

    if not url:
        raise RuntimeError(
            "DATABASE_URL no está configurado. "
            "Agrega la cadena de conexión PostgreSQL en el archivo .env"
        )

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return psycopg2.connect(url)

class Deduplicator:
    def __init__(self):
        self.conn = _get_conn()
        self._init_db()

    def _cursor(self):
        """Retorna cursor reconectando si la conexión cayó."""
        try:
            self.conn.cursor().execute("SELECT 1")
        except Exception:
            log.warning("[Dedup] Reconectando a PostgreSQL...")
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = _get_conn()
        return self.conn.cursor()

    def _init_db(self):
        cur = self._cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed (
                hash      TEXT PRIMARY KEY,
                url       TEXT,
                seen_at   TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sent_alerts (
                id               SERIAL PRIMARY KEY,
                content_hash     TEXT,
                titulo_hash      TEXT,
                titulo_norm      TEXT,
                descripcion_norm TEXT,
                departamento     TEXT,
                provincia        TEXT,
                subcategoria     TEXT,
                cliente          TEXT,
                resumen          TEXT,
                url              TEXT,
                sent_at          TEXT,
                UNIQUE(titulo_hash, departamento)
            )
        """)
        # Agregar nuevas columnas si no existen
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS titulo_hash TEXT")
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS descripcion_norm TEXT")
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS provincia TEXT")
        cur.execute("ALTER TABLE sent_alerts ADD COLUMN IF NOT EXISTS url TEXT")
        
        # Índices para búsquedas rápidas
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dept_sent ON sent_alerts (departamento, sent_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_titulo_hash ON sent_alerts (titulo_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cliente_sent ON sent_alerts (cliente, sent_at)")
        
        self.conn.commit()
        self._cleanup_old()

    def _url_hash(self, post: dict) -> str:
        """Hash de la URL normalizada para evitar duplicados entre ciclos."""
        key = _normalize_url(post.get("url") or "") or _normalize_text(post.get("text", ""))[:300]
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _content_hash(self, alert: dict) -> str:
        """
        Hash exacto basado en estructura clasificada.
        Identifica el mismo evento cuando la IA mantiene categorías estables.
        """
        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia")    or "").upper().strip()
        sub  = (alert.get("subcategoria") or "").upper().strip()
        kws  = sorted(str(k).upper().strip() for k in (alert.get("palabras_clave") or []))
        key  = f"{dept}|{prov}|{sub}|{'-'.join(kws)}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()
    
    def _titulo_hash(self, titulo: str) -> str:
        """
        Hash basado en el título normalizado.
        Dos títulos muy similares producen el mismo hash.
        """
        norm = _normalize_text(titulo)[:100]  # Primeras 100 chars normalizadas
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    # ─────────────────────────────────────────────
    # DEDUP DE POSTS (Nivel 1 — por URL)
    # ─────────────────────────────────────────────
    def already_processed(self, post: dict) -> bool:
        """¿Esta URL ya fue procesada?"""
        h = self._url_hash(post)
        cur = self._cursor()
        cur.execute("SELECT 1 FROM processed WHERE hash = %s", (h,))
        return cur.fetchone() is not None

    def mark_processed(self, post: dict):
        """Marca una URL como procesada."""
        h = self._url_hash(post)
        try:
            cur = self._cursor()
            cur.execute(
                "INSERT INTO processed (hash, url, seen_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (h, post.get("url", ""), datetime.now().isoformat())
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            log.error(f"Error en dedup BD: {e}")

    # ─────────────────────────────────────────────
    # DEDUP DE ALERTAS (Nivel 2,3,4 — por contenido)
    # ─────────────────────────────────────────────
    def is_duplicate_alert(self, alert: dict, window_hours: int = DEDUP_WINDOW_HOURS) -> bool:
        """
        Retorna True si ya se envió una alerta similar en las últimas N horas.

        SIETE niveles de verificación (en orden de rapidez):
          0. URL exacta (si existe) — SUPER RÁPIDO
          0.5. Content hash exacto — MÁS RÁPIDO
          1. Firma de evento (números + ubicaciones clave)
          2. Hash exacto de contenido (clasificación + palabras clave)
          2.5. ULTRA-AGRESIVO: Mismo dept/prov en 15 min
          3/4. Similitud Jaccard de títulos
          5. Similitud Jaccard de descripciones
          6. IA Fallback para casos ambiguos
        """
        
        # 🔴 NIVEL 0: URL EXACTA (si está disponible) — INSTANTÁNEO
        url = alert.get("url", "").strip()
        if url:
            cur = self._cursor()
            cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
            cur.execute(
                "SELECT 1 FROM sent_alerts WHERE url = %s AND sent_at > %s LIMIT 1",
                (url, cutoff)
            )
            if cur.fetchone():
                log.info(f"[Dedup] ✓ NIVEL 0 (URL exacta) → DUPLICADO")
                return True
        
        # 🔵 NIVEL 0.5: CONTENT HASH EXACTO — SUPER RÁPIDO
        ch = self._content_hash(alert)
        cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        cur = self._cursor()
        
        cur.execute(
            "SELECT 1 FROM sent_alerts WHERE content_hash = %s AND sent_at > %s LIMIT 1",
            (ch, cutoff)
        )
        if cur.fetchone():
            log.info(f"[Dedup] ✓ NIVEL 0.5 (Content Hash exacto) → DUPLICADO")
            return True
        
        # 🟣 NIVEL 1: FIRMA DE EVENTO (números + ubicaciones)
        titulo = alert.get("titulo", "").strip()
        desc = alert.get("resumen_whatsapp", "").strip()
        combined_text = f"{titulo} {desc}"
        
        if len(combined_text) > 20:
            sig = _extract_event_signature(combined_text)
            if sig:
                dept = (alert.get("departamento") or "").upper().strip()
                if dept:
                    cur = self._cursor()
                    # Ventana más corta para misma firma (1 hora)
                    cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
                    cur.execute(
                        "SELECT resumen FROM sent_alerts WHERE departamento = %s AND sent_at > %s AND resumen IS NOT NULL",
                        (dept, cutoff)
                    )
                    for (rec_resumen,) in cur.fetchall():
                        if rec_resumen:
                            sig_existente = _extract_event_signature(f"{rec_resumen}")
                            if sig == sig_existente and sig:
                                log.info(f"[Dedup] ✓ NIVEL 1 (Firma evento '{sig}') → DUPLICADO")
                                return True
        
        # 🔴 NIVEL 2: (Eliminado - ya cubierto por NIVEL 0.5)
        # El content_hash exacto ya se verifica en NIVEL 0.5 al inicio
        
        # ⚡ NIVEL 2.5: MISMO DEPARTAMENTO + PROVINCIA + SUBCATEGORIA EN 15 MIN
        # Antes era solo dept+prov, lo cual marcaba como duplicado eventos DISTINTOS
        # ocurridos en el mismo lugar (ej. robo y incendio en la misma provincia).
        # Ahora requiere también misma subcategoria para evitar falsos positivos.
        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia") or "").upper().strip()
        sub  = (alert.get("subcategoria") or "").upper().strip()

        if dept and prov and sub:
            cutoff_agressive = (datetime.now() - timedelta(hours=DEDUP_SAME_LOCATION_HOURS)).isoformat()

            # Búsqueda: mismo lugar + misma subcategoria en 15 minutos
            cur.execute(
                """SELECT 1 FROM sent_alerts
                   WHERE departamento = %s AND provincia = %s
                   AND UPPER(COALESCE(subcategoria, '')) = %s
                   AND sent_at > %s LIMIT 1""",
                (dept, prov, sub, cutoff_agressive)
            )
            if cur.fetchone():
                log.info(f"[Dedup] ✓ NIVEL 2.5 (Mismo Lugar+Subcat {dept}/{prov}/{sub} en 15min) → DUPLICADO")
                return True

        # 🟡 NIVEL 3: Hash de título (títulos casi idénticos)
        if titulo and len(titulo) > 10:
            th = self._titulo_hash(titulo)
            
            if dept:
                cur.execute(
                    "SELECT 1 FROM sent_alerts WHERE titulo_hash = %s AND departamento = %s AND sent_at > %s LIMIT 1",
                    (th, dept, cutoff)
                )
                if cur.fetchone():
                    log.info(f"[Dedup] ✓ NIVEL 3 (Hash título) → DUPLICADO")
                    return True

        # 🟠 NIVEL 4: Similitud Jaccard de TÍTULOS (>=50%)
        # Solo se ejecuta si hay título suficiente Y dept. Si falta algo, salta al siguiente nivel.
        if titulo and len(titulo) > 10 and dept:
            set_titulo_nuevo = _words_set(titulo)
            if len(set_titulo_nuevo) >= 2:  # Reducido a 2 palabras (de 3)
                cur.execute(
                    "SELECT DISTINCT titulo_norm FROM sent_alerts "
                    "WHERE departamento = %s AND sent_at > %s AND titulo_norm IS NOT NULL",
                    (dept, cutoff)
                )

                for (titulo_norm,) in cur.fetchall():
                    if not titulo_norm:
                        continue
                    set_existente = set(titulo_norm.split())
                    score_jaccard = _jaccard(set_titulo_nuevo, set_existente)

                    # También verificar similitud de strings directa (Levenshtein)
                    titulo_norm_completo = " ".join(titulo_norm.split())[:100]
                    titulo_nuevo_norm = _normalize_text(titulo)[:100]
                    score_leven = _levenshtein_ratio(titulo_nuevo_norm, titulo_norm_completo)

                    if score_jaccard >= JACCARD_THRESHOLD_TITULO:
                        log.info(
                            f"[Dedup] ✓ NIVEL 4 (Jaccard Título={score_jaccard:.2f}) → DUPLICADO"
                        )
                        return True

                    if score_leven >= LEVENSHTEIN_THRESHOLD:
                        log.info(
                            f"[Dedup] ✓ NIVEL 4 (Levenshtein={score_leven:.2f}) → DUPLICADO"
                        )
                        return True

        # 🔴 NIVEL 5: Similitud Jaccard de DESCRIPCIONES (>=55%)
        # Solo se ejecuta si hay desc suficiente Y dept. Si falta algo, salta al NIVEL 6.
        if desc and len(desc) > 15 and dept:
            set_desc_nuevo = _words_set(desc)
            if len(set_desc_nuevo) >= 3:  # Reducido a 3 palabras
                cur.execute(
                    "SELECT descripcion_norm FROM sent_alerts "
                    "WHERE departamento = %s AND sent_at > %s AND descripcion_norm IS NOT NULL",
                    (dept, (datetime.now() - timedelta(hours=6)).isoformat())
                )

                for (desc_norm,) in cur.fetchall():
                    if not desc_norm:
                        continue
                    set_desc_existente = set(desc_norm.split())
                    score = _jaccard(set_desc_nuevo, set_desc_existente)

                    if score >= JACCARD_THRESHOLD_CONTENIDO:
                        log.info(
                            f"[Dedup] ✓ NIVEL 5 (Jaccard DESC={score:.2f}) → DUPLICADO"
                        )
                        return True
        
        # ⚡ NIVEL 6: IA FALLBACK — Comparación semántica (último recurso)
        # Se ejecuta SOLO cuando:
        # - Los 5 niveles anteriores fallaron
        # - Hay similitud media (0.35+) pero no es definitoria
        # - Mismo departamento + últimas 6 horas
        if titulo and desc and (alert.get("departamento") or "").strip():
            dept = (alert.get("departamento") or "").upper().strip()
            cutoff_ia = (datetime.now() - timedelta(hours=6)).isoformat()
            
            # Buscar candidatos con similitud media que podrían ser duplicados
            cur.execute(
                "SELECT titulo_norm, descripcion_norm FROM sent_alerts "
                "WHERE departamento = %s AND sent_at > %s AND titulo_norm IS NOT NULL",
                (dept, cutoff_ia)
            )
            
            for (titulo_existente, desc_existente) in cur.fetchall():
                if not titulo_existente:
                    continue
                
                # Solo aplicar IA si hay similitud media (0.3+)
                set_t_new = _words_set(titulo)
                set_t_exist = set(titulo_existente.split())
                score_medio = _jaccard(set_t_new, set_t_exist)
                
                if 0.30 <= score_medio < JACCARD_THRESHOLD_TITULO:
                    # Usar IA para confirmar si es el mismo evento
                    log.debug(f"[Dedup] Comparando semánticamente (Jaccard={score_medio:.2f}): podría ser duplicado")
                    
                    if _ai_are_same_event(
                        titulo, 
                        titulo_existente,
                        desc[:150],
                        desc_existente[:150] if desc_existente else ""
                    ):
                        return True
        
        return False

    def mark_alert_sent(self, alert: dict):
        """
        Registra una alerta como enviada para futuras dedups.
        
        ⚠️ IMPORTANTE: 
        - SOLO guarda si NO es duplicado (doble-check)
        - Usa transacción atómica para evitar race conditions
        - No guarda alertas con nivel IGNORAR
        """
        # No guardar alertas ignoradas
        if alert.get("nivel") == "IGNORAR":
            return
        
        # Double-check: verificar UNA VEZ MÁS que no sea duplicado ANTES de guardar
        if self.is_duplicate_alert(alert):
            log.info(f"[Dedup] Rechazado: duplicado detectado en mark_alert_sent, NO se guarda")
            return
        
        ch = self._content_hash(alert)
        titulo = alert.get("titulo", "").strip()
        desc = alert.get("resumen_whatsapp", "").strip()
        url = alert.get("url", "").strip()
        
        # Normalizar para búsquedas futuras
        titulo_words = " ".join(sorted(_words_set(titulo)))[:500] if titulo else ""
        desc_words = " ".join(sorted(_words_set(desc)))[:500] if desc else ""
        titulo_hash = self._titulo_hash(titulo) if titulo else None
        
        try:
            cur = self._cursor()

            # psycopg2 maneja transacciones implícitamente (autocommit=OFF).
            # NO usar BEGIN/COMMIT manual — causa warnings y comportamiento indefinido.

            # Verificación final antes de insertar (mismo bloque transaccional)
            if titulo_hash and alert.get("departamento"):
                cur.execute(
                    "SELECT 1 FROM sent_alerts WHERE titulo_hash = %s AND departamento = %s LIMIT 1",
                    (titulo_hash, alert.get("departamento"))
                )
                if cur.fetchone():
                    log.info(f"[Dedup] Rechazo en transacción: ya existe titulo_hash + dept")
                    self.conn.rollback()
                    return

            # Insertar nuevo registro
            cur.execute(
                """INSERT INTO sent_alerts
                   (content_hash, titulo_hash, titulo_norm, descripcion_norm,
                    departamento, provincia, subcategoria, cliente, resumen, url, sent_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (titulo_hash, departamento) DO NOTHING""",
                (
                    ch,
                    titulo_hash,
                    titulo_words,
                    desc_words,
                    alert.get("departamento", ""),
                    alert.get("provincia", ""),
                    alert.get("subcategoria", ""),
                    alert.get("cliente", ""),
                    desc[:250],
                    url,
                    datetime.now().isoformat()
                )
            )

            rows_affected = cur.rowcount
            self.conn.commit()

            if rows_affected > 0:
                log.info(f"[Dedup] ✓ Alerta registrada para futuras dedups")
            else:
                log.info(f"[Dedup] ℹ️ Alerta ya existe (ON CONFLICT), no se insertó")

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            log.error(f"[Dedup] Error registrando alerta: {e}")

    # ─────────────────────────────────────────────
    # LIMPIEZA
    # ─────────────────────────────────────────────
    def _cleanup_old(self):
        """Limpia registros antiguos para evitar tabla gigante."""
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        # Margen 2x sobre DEDUP_WINDOW_HOURS para que una alerta en el borde
        # de la ventana no sea borrada justo antes del próximo chequeo.
        cutoff_alerts = (datetime.now() - timedelta(hours=DEDUP_WINDOW_HOURS * 2)).isoformat()
        cur = self._cursor()
        
        cur.execute("DELETE FROM processed WHERE seen_at < %s", (cutoff,))
        count_processed = cur.rowcount
        
        cur.execute("DELETE FROM sent_alerts WHERE sent_at < %s", (cutoff_alerts,))
        count_alerts = cur.rowcount
        
        self.conn.commit()
        
        if count_processed > 0 or count_alerts > 0:
            log.info(f"[Dedup] Limpieza: {count_processed} URLs, {count_alerts} alertas antiguas")
