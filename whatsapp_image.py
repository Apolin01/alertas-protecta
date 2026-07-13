"""
whatsapp_image.py — Generador de imágenes para WhatsApp bridge.

Este módulo crea una imagen JPEG a partir de los datos de la alerta
cuando no hay imagen original disponible. Está optimizado para el bridge
local de WhatsApp que acepta `data:` URIs y omite payloads muy grandes.
"""

import base64
import io
import random
import textwrap
import unicodedata
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

# =========================
# CONFIGURACIÓN DE IMAGEN
# =========================
IMAGE_WIDTH = 1200
IMAGE_HEIGHT = 630
FONT_SIZE_INITIAL = 74
FONT_MIN_SIZE = 36
WRAP_WIDTH = 24
LINE_SPACING = 14
MARGIN_X = 80
MARGIN_Y = 60

FONT_CANDIDATES = [
    "arialbd.ttf",
    "Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]

KEYWORD_STYLES = {
    "homicidio": {"bg": (120, 20, 20), "text": (255, 230, 230)},
    "asesinato": {"bg": (120, 20, 20), "text": (255, 230, 230)},
    "robo": {"bg": (25, 70, 140), "text": (230, 240, 255)},
    "asalto": {"bg": (25, 70, 140), "text": (230, 240, 255)},
    "extorsion": {"bg": (90, 35, 110), "text": (245, 225, 255)},
    "secuestro": {"bg": (80, 25, 90), "text": (245, 225, 255)},
    "droga": {"bg": (25, 100, 60), "text": (230, 255, 235)},
    "tid": {"bg": (25, 100, 60), "text": (230, 255, 235)},
    "transporte": {"bg": (30, 100, 60), "text": (220, 245, 220)},
    "derrumbe": {"bg": (130, 85, 35), "text": (255, 245, 220)},
    "accidente": {"bg": (170, 90, 20), "text": (255, 240, 220)},
    "incendio": {"bg": (180, 60, 20), "text": (255, 235, 220)},
    "protesta": {"bg": (140, 120, 20), "text": (255, 250, 220)},
    "clima": {"bg": (40, 90, 140), "text": (230, 240, 255)},
    "lluvia": {"bg": (40, 90, 140), "text": (230, 240, 255)},
}

RANDOM_STYLES = [
    {"bg": (38, 139, 44), "text": (170, 235, 150)},
    {"bg": (33, 82, 160), "text": (220, 235, 255)},
    {"bg": (115, 45, 140), "text": (240, 220, 255)},
    {"bg": (170, 80, 20), "text": (255, 235, 210)},
    {"bg": (90, 30, 30), "text": (255, 220, 220)},
]

BRIDGE_BASE64_LIMIT = 400_000
DATA_URI_PREFIX = "data:image/jpeg;base64,"
TARGET_IMAGE_BYTES = int((BRIDGE_BASE64_LIMIT - len(DATA_URI_PREFIX)) * 3 / 4)

# Paleta por nivel: mantiene identidad visual según `nivel` (CRIT/ALRT/INFO)
LEVEL_STYLES = {
    # Rojo / Amarillo / Verde (fácil asociación por nivel)
    "CRIT": {"bg": (200, 30, 30),  "text": (255, 245, 245)},
    "ALRT": {"bg": (235, 185, 30), "text": (40, 40, 40)},
    "INFO": {"bg": (40, 160, 60),  "text": (245, 255, 245)},
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def load_font(size: int):
    for font_path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def choose_style(alert: Dict) -> Dict:
    # Priorizar estilo por nivel si está presente
    nivel = (alert.get("nivel") or "").upper().strip()
    if nivel and nivel in LEVEL_STYLES:
        return LEVEL_STYLES[nivel]

    search_parts = []
    if alert.get("categoria"):
        search_parts.append(alert["categoria"])
    if alert.get("palabras_clave"):
        search_parts.extend(alert["palabras_clave"])
    if alert.get("titulo"):
        search_parts.append(alert["titulo"])
    if alert.get("resumen_whatsapp"):
        search_parts.append(alert["resumen_whatsapp"])

    joined = normalize_text(" ".join(search_parts))
    for keyword, style in KEYWORD_STYLES.items():
        if keyword in joined:
            return style
    return random.choice(RANDOM_STYLES)


def get_main_text(alert: Dict) -> str:
    if alert.get("descripcion_visual"):
        return alert["descripcion_visual"]
    if alert.get("titulo"):
        return alert["titulo"]
    return alert.get("resumen_whatsapp", "Alerta sin contenido")


def get_multiline_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, spacing: int = LINE_SPACING):
    return draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int):
    font_size = FONT_SIZE_INITIAL
    while font_size >= FONT_MIN_SIZE:
        font = load_font(font_size)
        wrapped = textwrap.fill(text, width=WRAP_WIDTH)
        bbox = get_multiline_bbox(draw, wrapped, font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= max_width and text_h <= max_height:
            return font, wrapped
        font_size -= 2
    return load_font(FONT_MIN_SIZE), textwrap.fill(text, width=WRAP_WIDTH)


def create_centered_alert_image_bytes(alert: Dict, max_bytes: int = TARGET_IMAGE_BYTES) -> bytes:
    style = choose_style(alert)
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), color=style["bg"])
    draw = ImageDraw.Draw(image)
    main_text = get_main_text(alert)
    max_text_width = IMAGE_WIDTH - (MARGIN_X * 2)
    max_text_height = IMAGE_HEIGHT - (MARGIN_Y * 2)
    font, wrapped_text = fit_text(draw, main_text, max_text_width, max_text_height)
    bbox = get_multiline_bbox(draw, wrapped_text, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (IMAGE_WIDTH - text_w) / 2
    y = (IMAGE_HEIGHT - text_h) / 2
    draw.multiline_text(
        (x, y),
        wrapped_text,
        font=font,
        fill=style["text"],
        align="center",
        spacing=LINE_SPACING,
    )

    def compress_to_target(img: Image.Image, max_bytes: int = max_bytes,
                           init_quality: int = 85, min_quality: int = 30,
                           quality_step: int = 5, resize_step: float = 0.9,
                           min_width: int = 400) -> bytes:
        quality = init_quality
        cur_img = img.copy()
        while True:
            buf = io.BytesIO()
            try:
                cur_img.save(buf, format="JPEG", quality=quality, optimize=True)
            except OSError:
                cur_img.save(buf, format="JPEG", quality=quality)
            data = buf.getvalue()
            if len(data) <= max_bytes or (cur_img.width <= min_width and quality <= min_quality):
                return data
            if quality - quality_step >= min_quality:
                quality -= quality_step
            else:
                new_w = max(int(cur_img.width * resize_step), min_width)
                new_h = max(int(cur_img.height * resize_step), 1)
                cur_img = cur_img.resize((new_w, new_h), resample=Image.LANCZOS)
                quality = init_quality

    return compress_to_target(image, max_bytes=max_bytes)


def image_bytes_to_data_uri(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def generate_alert_image_data_uri(alert: Dict, max_base64_len: int = BRIDGE_BASE64_LIMIT) -> str:
    if not alert:
        return ""
    image_bytes = create_centered_alert_image_bytes(alert)
    data_uri = image_bytes_to_data_uri(image_bytes)
    if len(data_uri) > max_base64_len:
        return ""
    return data_uri