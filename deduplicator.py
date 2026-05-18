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

log = logging.getLogger(__name__)

# Umbrales de similitud
JACCARD_THRESHOLD_TITULO = 0.50       # MUCHO MÁS SENSIBLE - reducido para capturar variaciones
JACCARD_THRESHOLD_CONTENIDO = 0.55    # Reducido para descripción
LEVENSHTEIN_THRESHOLD = 0.65          # Más bajo para capturar parafraseos
SIMILITUD_EVENTO_MIN = 0.65           # Para detección de mismo evento

# Ventanas de búsqueda
DEDUP_WINDOW_HOURS = 12               # Ventana de dedup
DEDUP_SAME_BUNDLE_HOURS = 0.5         # ⚡ REDUCIDO A 30 MINUTOS - mismo bundle = mismo evento rápido
DEDUP_SAME_SOURCE_HOURS = 6           # Ventana para misma fuente
DEDUP_SAME_LOCATION_HOURS = 0.25      # ⚡ NUEVO: 15 minutos - mismo depto + prov = probablemente dup

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


def _extract_event_signature(text: str) -> str:
    """
    Extrae firma de evento: ubicaciones + números significativos.
    Ej: "Canon minero 576.4 millones Cajamarca" → "canon_cajamarca_576"
    Sirve para detectar mismo evento en diferentes fuentes.
    """
    if not text:
        return ""
    
    # Normalizar
    text = _strip_accents(text.lower())
    
    # Extraer números significativos (cantidades)
    numbers = re.findall(r'\d+[.,]?\d*', text)
    number_sig = numbers[0] if numbers else ""
    
    # Palabras clave (ubicaciones + tipos de evento)
    important_words = re.findall(r'\b([a-z]{4,})\b', text)
    important_words = [w for w in important_words if w not in _STOPWORDS_ES and len(w) >= 4][:3]
    
    sig = "_".join(important_words)
    if number_sig:
        sig += f"_{number_sig.replace('.', '').replace(',', '')}"
    
    return sig[:60] if sig else ""


def _get_conn():
    url = os.environ["DATABASE_URL"]
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
        """Hash de la URL original."""
        key = post.get("url") or post.get("text", "")
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

        Cinco niveles de verificación (en orden):
          1. URL exacta (si existe)
          2. Firma de evento (números + ubicaciones clave)
          3. Hash exacto de contenido (clasificación + palabras clave)
          4. Similitud Jaccard de títulos >= 55% en el mismo departamento
          5. Similitud Jaccard de descripciones >= 60% en el mismo departamento
        """
        
        # 🔴 NIVEL 0: URL EXACTA (si está disponible)
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
        
        # 🔴 NIVEL 2: Hash exacto de contenido
        ch = self._content_hash(alert)
        cutoff = (datetime.now() - timedelta(hours=window_hours)).isoformat()
        cur = self._cursor()
        
        cur.execute(
            "SELECT 1 FROM sent_alerts WHERE content_hash = %s AND sent_at > %s",
            (ch, cutoff)
        )
        if cur.fetchone():
            log.info(f"[Dedup] ✓ NIVEL 2 (Hash exacto) → DUPLICADO")
            return True
        
        # ⚡ NIVEL 2.5: ULTRA-AGRESIVO - MISMO DEPARTAMENTO + PROVINCIA EN 15 MIN
        dept = (alert.get("departamento") or "").upper().strip()
        prov = (alert.get("provincia") or "").upper().strip()
        
        if dept and prov:
            cutoff_agressive = (datetime.now() - timedelta(hours=DEDUP_SAME_LOCATION_HOURS)).isoformat()
            
            # Búsqueda ultra-rápida: mismo lugar en 15 minutos
            cur.execute(
                """SELECT 1 FROM sent_alerts 
                   WHERE departamento = %s AND provincia = %s 
                   AND sent_at > %s LIMIT 1""",
                (dept, prov, cutoff_agressive)
            )
            if cur.fetchone():
                log.info(f"[Dedup] ✓ NIVEL 2.5 (Mismo Lugar {dept}/{prov} en 15min) → DUPLICADO")
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
        if titulo and len(titulo) > 10:
            dept = (alert.get("departamento") or "").upper().strip()
            if not dept:
                return False
            
            set_titulo_nuevo = _words_set(titulo)
            if len(set_titulo_nuevo) < 2:  # Reducido a 2 palabras (de 3)
                return False
            
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
        if desc and len(desc) > 15:
            if not dept:
                return False
            
            set_desc_nuevo = _words_set(desc)
            if len(set_desc_nuevo) < 3:  # Reducido a 3 palabras
                return False
            
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
        
        return False

    def mark_alert_sent(self, alert: dict):
        """Registra una alerta como enviada para futuras dedups."""
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
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            log.error(f"[Dedup] Error registrando alerta: {e}")

    # ─────────────────────────────────────────────
    # LIMPIEZA
    # ─────────────────────────────────────────────
    def _cleanup_old(self):
        """Limpia registros antiguos para evitar tabla gigante."""
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        cutoff_alerts = (datetime.now() - timedelta(hours=24)).isoformat()
        cur = self._cursor()
        
        cur.execute("DELETE FROM processed WHERE seen_at < %s", (cutoff,))
        count_processed = cur.rowcount
        
        cur.execute("DELETE FROM sent_alerts WHERE sent_at < %s", (cutoff_alerts,))
        count_alerts = cur.rowcount
        
        self.conn.commit()
        
        if count_processed > 0 or count_alerts > 0:
            log.info(f"[Dedup] Limpieza: {count_processed} URLs, {count_alerts} alertas antiguas")
