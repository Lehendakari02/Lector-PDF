"""The work modes and the list of functions each one offers.

This list is the single source for the tool bar of every mode and for the
function finder (Ctrl+K). A function that is not built yet has no handler; the
window shows it and says it is not available yet.
"""

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

from app.core.text import normalize_for_search

_CONTEXT = "Features"


class Mode(Enum):
    """A work mode. The value is the visible Spanish name."""

    READ = QT_TRANSLATE_NOOP("Features", "Leer")
    STUDY = QT_TRANSLATE_NOOP("Features", "Estudiar")
    FILL_SIGN = QT_TRANSLATE_NOOP("Features", "Rellenar y firmar")
    ORGANIZE = QT_TRANSLATE_NOOP("Features", "Organizar")


MODES = list(Mode)


@dataclass(frozen=True)
class Feature:
    """One function of the program, as shown on a button and in the finder."""

    id: str
    mode: Mode
    name: str
    description: str
    keywords: str = ""
    # False: no button of its own (it is in the menu of another one); the
    # finder (Ctrl+K) still has it.
    toolbar: bool = True


def translate(text: str) -> str:
    """Return ``text`` in the language of the interface."""
    return QCoreApplication.translate(_CONTEXT, text)


def _f(
    feature_id: str,
    mode: Mode,
    name: str,
    description: str,
    keywords: str = "",
    toolbar: bool = True,
) -> Feature:
    return Feature(feature_id, mode, name, description, keywords, toolbar)


READ, STUDY, FILL, ORGANIZE = Mode.READ, Mode.STUDY, Mode.FILL_SIGN, Mode.ORGANIZE

FEATURES: list[Feature] = [
    # Leer
    _f("open", READ, "Abrir", "Abrir un PDF del ordenador", "archivo documento cargar"),
    _f("search", READ, "Buscar", "Buscar palabras o frases en el documento", "encontrar texto"),
    _f(
        "copy",
        READ,
        "Copiar",
        "Copiar el texto seleccionado con el ratón (Ctrl+C)",
        "texto seleccionar portapapeles pegar",
    ),
    _f("zoom_in", READ, "Acercar", "Ver el documento más grande", "zoom ampliar aumentar lupa"),
    _f("zoom_out", READ, "Alejar", "Ver el documento más pequeño", "zoom reducir disminuir"),
    _f(
        "fit_comfortable",
        READ,
        "Tamaño inicial",
        "Volver al tamaño con el que se abrió el documento (Ctrl+0)",
        "zoom predeterminado normal restablecer original cómodo",
    ),
    _f("fit_width", READ, "Ajustar al ancho", "La página ocupa todo el ancho", "zoom anchura"),
    _f(
        "fit_page", READ, "Ver página entera", "La página entera cabe en la ventana", "zoom ajustar"
    ),
    _f(
        "rotate_view",
        READ,
        "Girar vista",
        "Girar las páginas para leerlas del derecho (no cambia el archivo)",
        "rotar voltear tumbado",
    ),
    _f(
        "reading_mode",
        READ,
        "Modo lectura",
        "Papel en tono cálido (sepia) para leer muchas horas; no cambia el archivo",
        "sepia noche descanso vista ojos papel color fondo",
    ),
    _f("fullscreen", READ, "Pantalla completa", "Ver solo el documento (F11)", "completa entera"),
    _f("go_to_page", READ, "Ir a página", "Saltar a un número de página", "número saltar"),
    _f("outline", READ, "Índice", "Ver los apartados del documento y saltar a ellos", "esquema"),
    _f("thumbnails", READ, "Miniaturas", "Ver todas las páginas en pequeño", "páginas vista"),
    _f(
        "save",
        READ,
        "Guardar",
        "Guardar los cambios en el mismo archivo (Ctrl+S)",
        "grabar salvar cambios archivo",
    ),
    _f(
        "save_as",
        READ,
        "Guardar como",
        "Guardar una copia con otro nombre o en otra carpeta (Ctrl+Mayús+S)",
        "grabar salvar copia nombre duplicar",
    ),
    _f("print", READ, "Imprimir", "Imprimir el documento o unas páginas", "impresora papel"),
    # Estudiar
    _f("undo", STUDY, "Deshacer", "Quitar el último cambio (Ctrl+Z)", "atrás quitar volver error"),
    _f("redo", STUDY, "Rehacer", "Volver a poner el cambio deshecho (Ctrl+Y)", "adelante repetir"),
    _f("highlight", STUDY, "Resaltar", "Marcar texto con rotulador", "fosforito marcar color"),
    _f("underline", STUDY, "Subrayar", "Poner una línea debajo del texto", "línea marcar"),
    _f("strikeout", STUDY, "Tachar", "Tachar texto", "línea eliminar marcar"),
    _f("note", STUDY, "Nota", "Pegar una nota adhesiva en la página", "comentario apunte post-it"),
    _f("text_box", STUDY, "Cuadro de texto", "Escribir texto sobre la página", "escribir apunte"),
    _f("draw", STUDY, "Dibujar", "Dibujar a mano alzada", "lápiz bolígrafo trazo"),
    _f(
        "shapes",
        STUDY,
        "Formas",
        "Añadir flechas, líneas, recuadros y óvalos",
        "rectángulo círculo",
    ),
    _f("eraser", STUDY, "Borrador", "Borrar dibujos y anotaciones", "goma eliminar quitar"),
    _f(
        "hide_annotations",
        STUDY,
        "Ocultar anotaciones",
        "Ver el documento limpio, sin subrayados, notas ni dibujos; no se borra nada",
        "mostrar esconder limpio ver quitar original",
    ),
    _f(
        "bookmark",
        STUDY,
        "Marcador",
        "Guardar el sitio que lees para volver con un clic; sale en el Índice (Ctrl+M)",
        "favorito señal marcar página volver artículo clave",
    ),
    _f(
        "go_to_article",
        STUDY,
        "Ir a artículo",
        "Saltar a un artículo, apartado o capítulo escribiendo su número («art. 14», «3.2»)",
        "saltar número apartado capítulo título sección disposición ley boe tema",
    ),
    _f(
        "ocr",
        STUDY,
        "Reconocer texto",
        "Leer el texto de las páginas escaneadas para poder buscar, subrayar y copiar",
        "ocr escaneado foto imagen",
    ),
    _f(
        "ocr_again",
        STUDY,
        "Volver a reconocer texto",
        "Rehacer el texto de páginas escaneadas que se buscan mal o tienen fallos",
        "ocr escaneado repetir rehacer otra vez mal",
        toolbar=False,
    ),
    _f(
        "annotations",
        STUDY,
        "Anotaciones",
        "Lista de todos tus subrayados, notas y dibujos; por colores, y salta a cada uno",
        "panel resumen lista subrayados notas colores filtrar",
    ),
    _f(
        "review",
        STUDY,
        "Modo repaso",
        "Tapar lo resaltado y subrayado para intentar recordarlo; un clic lo destapa",
        "repasar estudiar memorizar tapar ocultar recordar examen",
    ),
    _f(
        "beside",
        STUDY,
        "Ver al lado",
        "Ver dos documentos a la vez, uno junto al otro (por ejemplo, el tema y la ley)",
        "dos documentos lado a lado dividir pantalla comparar tema ley",
    ),
    _f(
        "link",
        STUDY,
        "Enlazar a…",
        "Unas palabras que llevan al sitio exacto de otro documento (p. ej. un artículo de la ley)",
        "enlace enlazar vincular otro documento artículo ley ir a remitir referencia",
    ),
    _f(
        "library",
        STUDY,
        "Biblioteca",
        "Tu temario: todos los temas de una carpeta, buscar en todos a la vez y cuánto llevas",
        "biblioteca temario temas carpeta buscar en todos progreso leído repasado",
    ),
    _f(
        "summary",
        STUDY,
        "Exportar resumen",
        "Sacar en PDF o en Word todo lo subrayado y anotado, página a página",
        "resumen exportar subrayados notas apuntes word docx pdf imprimir",
    ),
    _f(
        "margins",
        STUDY,
        "Añadir margen",
        "Añadir espacio en blanco para apuntes",
        "márgenes ampliar",
    ),
    _f(
        "insert_sheet",
        STUDY,
        "Insertar hoja",
        "Añadir una hoja en blanco, de rayas o cuadriculada",
        "página rayas cuadrícula",
    ),
    # Rellenar y firmar
    _f(
        "fill_form",
        FILL,
        "Rellenar campos",
        "Escribir en los campos de un formulario, marcar casillas y elegir (Tab: el siguiente)",
        "formulario rellenar campos casilla solicitud impreso instancia",
    ),
    _f("type_text", FILL, "Escribir", "Escribir en cualquier parte del documento", "texto"),
    _f("my_data", FILL, "Mis datos", "Poner tu nombre, DNI o dirección con un clic", "personales"),
    _f("stamps", FILL, "Sellos", "Marcas rápidas: ✓, ✗, fecha, sellos propios", "marca casilla"),
    _f("sign_drawn", FILL, "Firmar", "Poner tu firma manuscrita guardada", "firma rúbrica"),
    _f(
        "sign_certificate",
        FILL,
        "Firmar con certificado",
        "Firma con validez legal: certificado digital, FNMT o DNIe",
        "firmar firma digital electrónica",
    ),
    _f(
        "check_signatures",
        FILL,
        "Comprobar firmas",
        "Ver quién ha firmado y si es válido",
        "firma firmar verificar validar",
    ),
    # Organizar
    _f(
        "pages",
        ORGANIZE,
        "Ordenar páginas",
        "Cambiar el orden arrastrando las páginas",
        "reordenar",
    ),
    _f("rotate", ORGANIZE, "Rotar", "Girar páginas", "girar voltear"),
    _f(
        "delete_pages",
        ORGANIZE,
        "Eliminar páginas",
        "Quitar páginas del documento",
        "borrar quitar",
    ),
    _f("merge", ORGANIZE, "Unir", "Juntar varios PDFs en uno", "juntar combinar fusionar"),
    _f("split", ORGANIZE, "Dividir", "Separar el documento en varios", "separar extraer partir"),
    _f(
        "photo_to_pdf",
        ORGANIZE,
        "De foto a PDF",
        "Convertir fotos de documentos en un PDF",
        "escanear",
    ),
    _f(
        "export", ORGANIZE, "Exportar", "Guardar páginas como imagen o como texto", "imagen png jpg"
    ),
    _f(
        "redact",
        ORGANIZE,
        "Tapar datos",
        "Borrar datos para siempre antes de enviar",
        "ocultar censurar",
    ),
    _f(
        "compress", ORGANIZE, "Comprimir", "Hacer que el archivo ocupe menos", "reducir tamaño peso"
    ),
    _f(
        "password", ORGANIZE, "Contraseña", "Poner o quitar la contraseña del PDF", "proteger clave"
    ),
    _f("compare", ORGANIZE, "Comparar", "Ver qué ha cambiado entre dos versiones", "diferencias"),
]


# Functions that begin a new group in the tool bar of their mode (a thin line
# is drawn before them), so related tools stay together.
GROUP_STARTS = frozenset(
    {
        "zoom_in",
        "reading_mode",
        "outline",
        "save",
        "highlight",
        "note",
        "hide_annotations",
        "bookmark",
        "annotations",
        "margins",
        "sign_drawn",
        "merge",
        "photo_to_pdf",
        "redact",
        "compare",
    }
)


def features_of(mode: Mode) -> list[Feature]:
    """The functions with a button on the tool bar of a mode."""
    return [feature for feature in FEATURES if feature.mode is mode and feature.toolbar]


def search_features(query: str, features: list[Feature] | None = None) -> list[Feature]:
    """Find functions by what the user typed, ignoring accents and capitals.

    Every typed word must appear in the name, the description, the keywords or
    the mode. Matches in the name come first.
    """
    words = normalize_for_search(query).split()
    candidates = FEATURES if features is None else features
    if not words:
        return list(candidates)

    scored = []
    for position, feature in enumerate(candidates):
        name = normalize_for_search(translate(feature.name))
        details = normalize_for_search(f"{translate(feature.description)} {feature.keywords}")
        mode = normalize_for_search(translate(feature.mode.value))
        if not all(word in name or word in details or word in mode for word in words):
            continue
        if name.startswith(words[0]):
            rank = 0
        elif any(part.startswith(words[0]) for part in name.split()):
            rank = 1
        elif all(word in name for word in words):
            rank = 2
        elif all(word in name or word in details for word in words):
            rank = 3
        else:
            rank = 4  # found only through the name of its mode
        scored.append((rank, position, feature))
    return [feature for _, _, feature in sorted(scored, key=lambda item: item[:2])]
