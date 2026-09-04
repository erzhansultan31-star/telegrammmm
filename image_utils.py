# -*- coding: utf-8 -*-
"""
Сурет өңдеу функциялары.
- Мәтін/watermark қосу үшін: Pillow (жеңіл, сапалы шрифт рендері)
- Фильтрлер үшін: OpenCV (жылдам, көп фильтр түрі)
"""

import io
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont


# ---------- Көмекші: bytes <-> PIL <-> OpenCV ----------

def bytes_to_pil(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def pil_to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=92)
    return buf.getvalue()


def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def cv_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


# ---------- Мәтін қосу (Pillow) ----------

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Жүйедегі DejaVuSans шрифтін қолданады (кириллицаны қолдайды).
    Табылмаса, Pillow-дың дефолт шрифтін қайтарады."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def add_text(
    img: Image.Image,
    text: str,
    position: str = "bottom",  # "top" | "bottom" | "center"
    color: str = "white",
    with_shadow: bool = True,
) -> Image.Image:
    """Суретке мәтін (есім/автор аты) қосады, оқуға ыңғайлы болу үшін көлеңке жасайды."""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size

    font_size = max(18, w // 18)
    font = _get_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = int(h * 0.03)
    if position == "top":
        x, y = (w - text_w) // 2, margin
    elif position == "center":
        x, y = (w - text_w) // 2, (h - text_h) // 2
    else:  # bottom
        x, y = (w - text_w) // 2, h - text_h - margin

    if with_shadow:
        shadow_offset = max(1, font_size // 20)
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill="black")

    draw.text((x, y), text, font=font, fill=color)
    return img


def add_name(img: Image.Image, name: str) -> Image.Image:
    """Есімді суреттің төменгі жағына қосады."""
    return add_text(img, name, position="bottom", color="white")


def add_author(img: Image.Image, author: str) -> Image.Image:
    """Автор атын (қолтаңба) суреттің жоғарғы жағына кішірек қосады."""
    return add_text(img, f"© {author}", position="top", color="white")


# ---------- Фильтрлер (OpenCV) ----------

def apply_filter(img: Image.Image, filter_name: str) -> Image.Image:
    cv_img = pil_to_cv(img)

    if filter_name == "bw":
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    elif filter_name == "sepia":
        kernel = np.array([[0.272, 0.534, 0.131],
                            [0.349, 0.686, 0.168],
                            [0.393, 0.769, 0.189]])
        sepia = cv2.transform(cv_img, kernel)
        result = np.clip(sepia, 0, 255).astype(np.uint8)

    elif filter_name == "blur":
        result = cv2.GaussianBlur(cv_img, (15, 15), 0)

    elif filter_name == "sharpen":
        kernel = np.array([[0, -1, 0],
                            [-1, 5, -1],
                            [0, -1, 0]])
        result = cv2.filter2D(cv_img, -1, kernel)

    else:  # "none"
        result = cv_img

    return cv_to_pil(result)


# ---------- Өлшемін өзгерту ----------

def resize_image(img: Image.Image, max_side: int) -> Image.Image:
    """Суретті max_side-ге дейін пропорционалды кішірейтеді/үлкейтеді."""
    w, h = img.size
    scale = max_side / max(w, h)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)
