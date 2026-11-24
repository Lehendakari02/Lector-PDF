"""The built-in help: what every function does and how to use it.

Every function of ``app.ui.features`` has its page here (a test makes sure of
it), plus pages for what has no button: saving and recovering, tabs, settings,
keys, pen and touch… The help window (F1) shows them and finds them by what the
user wants to do, with the same rules as the search of the documents (no
accents, no capitals).

The text is written for someone who does not know the program: short steps,
the words of the buttons, nothing technical. A key is never written here: the
window says the key each function has now, because each person can change them.
"""

import datetime
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication

from app.core.settings import Settings
from app.core.text import normalize_for_search
from app.ui.features import FEATURES, MODES, Feature

_CONTEXT = "Help"

# Sections that are not a mode.
SAVING = "Guardar y no perder nada"
COMFORT = "Comodidad y ajustes"
SECTIONS = [mode.value for mode in MODES] + [SAVING, COMFORT]


def translate(text: str) -> str:
    """``text`` in the language of the interface (the names and descriptions of
    the functions are translated with the tool bars)."""
    done = QCoreApplication.translate(_CONTEXT, text)
    return done if done != text else QCoreApplication.translate("Features", text)


@dataclass(frozen=True)
class Topic:
    """One page of the help."""

    id: str
    section: str
    title: str
    summary: str
    steps: tuple[str, ...] = ()
    tips: tuple[str, ...] = ()
    keywords: str = ""
    # "Hazlo ahora" runs this function of the tool bars…
    feature: str | None = None
    # …or this command of the menus (an id of ``MainWindow.key_commands``).
    command: str | None = None


_FEATURES = {feature.id: feature for feature in FEATURES}

# What to say about each function, by its id: (steps, tips, more keywords).
# A function not built yet has no steps: the window says it is coming.
_HOW: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    # ---- Leer ----
    "open": (
        (
            "Pulsa «Abrir» y elige el PDF.",
            "También puedes arrastrar uno o varios PDF a la ventana: cada uno se abre "
            "en su pestaña.",
            "Para abrirlos con doble clic, haz que Lector-PDF sea tu programa de PDF "
            "(Ajustes → General → «Usar Lector-PDF para abrir los PDF…»).",
        ),
        (
            "Menú → Archivo → Abrir recientes guarda los 12 últimos; los 5 últimos "
            "salen también en la pantalla de bienvenida.",
            "Al abrir el programa vuelven las pestañas de la última vez, cada una en su página.",
            "Si el PDF tiene contraseña, la pide. La contraseña nunca se guarda.",
        ),
        "doble clic arrastrar soltar predeterminado contraseña recientes",
    ),
    "search": (
        (
            "Escribe en la casilla «Buscar» de arriba.",
            "Intro va al siguiente resultado y Mayús+Intro al anterior (también las "
            "flechas abajo y arriba).",
            "A la izquierda sale la lista de resultados con la frase de cada uno: un "
            "clic te lleva a él.",
        ),
        (
            "No distingue tildes ni mayúsculas: «articulo» encuentra «Artículo». La ñ "
            "no es una n: «año» no encuentra «ano».",
            "Encuentra palabras partidas con guion al final de línea y frases que "
            "pasan a la línea o a la página siguiente.",
            "Opciones: «Palabra completa», «Coincidencia exacta» y «Aproximada, para "
            "escaneados» (para los fallos típicos del texto reconocido: 1 y l, 0 y o, "
            "rn y m).",
            "Para buscar en todos tus temas a la vez, usa la Biblioteca (modo Estudiar).",
        ),
        "lupa palabra frase tildes aproximada escaneado resultados",
    ),
    "copy": (
        (
            "Arrastra el ratón sobre el texto para seleccionarlo.",
            "Pulsa «Copiar», o el botón derecho → Copiar, y pégalo donde quieras.",
        ),
        (
            "Doble clic selecciona una palabra; Mayús+clic, hasta ese punto; Ctrl+A, "
            "todo el documento. Esc quita la selección.",
            "Lo copiado sale como texto seguido: las líneas de un párrafo se unen y "
            "las palabras partidas con guion vuelven a estar enteras.",
            "En una página escaneada no hay texto que copiar: primero «Reconocer "
            "texto» (modo Estudiar).",
        ),
        "seleccionar pegar portapapeles word apuntes",
    ),
    "zoom_in": (
        (
            "Pulsa «Acercar», o Ctrl + la rueda del ratón, o pellizca con dos dedos.",
            "Abajo a la derecha está el tamaño en % con una barra para cambiarlo.",
        ),
        ("Con mucho zoom solo se dibuja lo que se ve, así que sigue yendo fluido.",),
        "más grande lupa ampliar porcentaje",
    ),
    "zoom_out": (
        ("Pulsa «Alejar», o Ctrl + la rueda del ratón hacia atrás, o junta dos dedos.",),
        ("Abajo a la derecha está el tamaño en % con una barra para cambiarlo.",),
        "más pequeño porcentaje",
    ),
    "fit_comfortable": (
        ("Pulsa «Tamaño inicial» y el documento vuelve al tamaño con el que se abrió.",),
        (
            "Los documentos se abren ajustados al ancho, pero nunca a más del 125 %, "
            "para que se lean cómodos.",
        ),
        "",
    ),
    "fit_width": (
        ("Pulsa «Ajustar al ancho»: la página ocupa todo el ancho de la ventana.",),
        ("Si abres un panel o cambias el tamaño de la ventana, se queda ajustada.",),
        "",
    ),
    "fit_page": (("Pulsa «Ver página entera»: cabe la hoja completa en la pantalla.",), (), ""),
    "rotate_view": (
        ("Pulsa «Girar vista»: las páginas se giran solo en la pantalla.",),
        (
            "El archivo no cambia. Para girar las páginas de verdad, usa «Rotar» en el "
            "modo Organizar.",
        ),
        "dar la vuelta tumbar de lado",
    ),
    "reading_mode": (
        ("Pulsa «Modo lectura»: el papel pasa a un tono sepia, cálido, para leer muchas horas.",),
        (
            "Menú → Ver → Papel de las páginas elige Blanco, Sepia o Noche (papel oscuro "
            "y letra clara).",
            "Menú → Ver → Tema pone el programa claro u oscuro.",
            "Solo cambia lo que ves: el PDF y lo que se imprime no cambian.",
        ),
        "sepia noche oscuro cansancio ojos",
    ),
    "fullscreen": (
        ("Pulsa «Pantalla completa»: solo se ve el documento.",),
        ("Esc vuelve a la ventana normal.",),
        "",
    ),
    "go_to_page": (
        (
            "Abajo, en «Página [12] de 39», escribe el número y pulsa Intro.",
            "Si escribes «art. 14» o «3.2», te lleva a ese artículo o apartado.",
        ),
        (),
        "número saltar",
    ),
    "outline": (
        (
            "Pulsa «Índice»: se abre el panel de la izquierda con los apartados del documento.",
            "Un clic en un apartado te lleva allí.",
        ),
        (
            "Arriba del todo salen tus marcadores («Mis marcadores»).",
            "Si el PDF no trae índice, lo dice. Para ir a un artículo, usa «Ir a artículo».",
        ),
        "apartados capítulos panel lateral",
    ),
    "thumbnails": (
        ("Pulsa «Miniaturas»: el panel de la izquierda enseña las páginas en pequeño.",),
        (
            "Un clic en una te lleva a ella.",
            "Arrastrándolas se cambia el orden de las páginas (ver «Ordenar páginas»).",
        ),
        "panel lateral",
    ),
    "save": (
        (
            "Pulsa «Guardar»: tus cambios se escriben en el mismo PDF.",
            "Está apagado cuando no hay nada pendiente.",
        ),
        (
            "El PDF solo cambia cuando guardas. Abajo a la derecha siempre ves si está "
            "«Guardado» o con «Cambios sin guardar»; la pestaña lleva un punto.",
            "Si el archivo está ocupado (otro programa, OneDrive…), avisa y no pierdes nada.",
            "Si prefieres que guarde solo, actívalo en Ajustes → Guardado.",
        ),
        "",
    ),
    "save_as": (
        (
            "Pulsa «Guardar como» y elige nombre y carpeta: se crea una copia nueva.",
            "Sigues trabajando en la copia nueva; el original queda como estaba.",
        ),
        (),
        "copia duplicar otro nombre",
    ),
    "print": (
        (
            "Pulsa «Imprimir» y elige la impresora.",
            "En «Páginas» puedes poner todas, la que estás viendo o unas concretas, "
            "como «1-5, 8, 12-».",
        ),
        (
            "La casilla «Con las anotaciones» decide si salen tus subrayados y notas.",
            "Se imprime en segundo plano: puedes seguir leyendo.",
        ),
        "papel impresora",
    ),
    "undo": (
        ("Pulsa «Deshacer» para quitar el último cambio; puedes ir hacia atrás sin límite.",),
        ("Cada documento tiene su propio deshacer.",),
        "atrás error equivocado",
    ),
    "redo": (("Pulsa «Rehacer» para volver a poner lo que deshiciste.",), (), ""),
    # ---- Estudiar ----
    "highlight": (
        (
            "Selecciona el texto y pulsa «Resaltar».",
            "Sin nada seleccionado, el rotulador se queda en la mano: todo lo que "
            "selecciones queda resaltado. Esc lo suelta.",
            "La flecha de al lado elige el color (cualquiera) y la opacidad.",
        ),
        (
            "Con el rotulador en la mano, doble clic resalta una palabra.",
            "Para cambiar el color de algo ya resaltado, haz clic en él y elige otro en "
            "la barra pequeña que sale.",
            "En la flecha también está «Guardar en favoritas».",
        ),
        "fosforito rotulador marcar amarillo",
    ),
    "underline": (
        (
            "Selecciona el texto y pulsa «Subrayar».",
            "Sin nada seleccionado, se queda en la mano hasta que pulses Esc.",
            "La flecha de al lado elige el color y la opacidad.",
        ),
        ("Para cambiar el color de un subrayado, haz clic en él y elige otro.",),
        "raya debajo",
    ),
    "strikeout": (
        (
            "Selecciona el texto y pulsa «Tachar».",
            "Sin nada seleccionado, se queda en la mano hasta que pulses Esc.",
        ),
        (),
        "",
    ),
    "note": (
        (
            "Pulsa «Nota» y haz clic en la página donde quieres dejarla.",
            "Escribe y pulsa Guardar (o Ctrl+Intro). Esc la descarta.",
        ),
        (
            "Un clic en una nota la abre para leerla, cambiarla o borrarla. Al pasar el "
            "ratón por encima se lee.",
            "Desde una nota puedes enlazar a otro documento (botón derecho).",
        ),
        "comentario post-it pósit adhesiva",
    ),
    "text_box": (
        (
            "Pulsa «Cuadro de texto» y haz clic donde quieras escribir: se escribe en "
            "la propia página.",
            "Encima sale una barra pequeña: letra más grande o más pequeña (A+, A−), "
            "negrita y colores.",
            "Ctrl+Intro, «Hecho» o un clic fuera lo dejan puesto. Esc lo deja todo como estaba.",
        ),
        (
            "Al escribir -> sale →, y => sale ⇒. El botón «→ ✓» tiene muchos más símbolos.",
            "Arrastrando el borde derecho del marco cambias el ancho.",
            "Para cambiar un texto ya puesto, haz doble clic en él.",
            "La flecha del botón elige el tipo de letra, el tamaño y el color.",
        ),
        "escribir encima símbolos flecha negrita letra",
    ),
    "draw": (
        (
            "Pulsa «Dibujar» y dibuja con el ratón pulsado, con el lápiz o con el dedo.",
            "La flecha de al lado elige color, grosor y opacidad.",
        ),
        (
            "Con un lápiz que nota la presión, el trazo es más grueso donde aprietas.",
            "La goma del lápiz, o su botón, borran sin cambiar de herramienta.",
        ),
        "mano alzada lápiz boli bolígrafo pintar",
    ),
    "shapes": (
        (
            "En la flecha del botón elige la forma: flecha, línea, recuadro, óvalo, "
            "triángulo, rombo, llave…",
            "Arrastra en la página para dibujarla.",
        ),
        (
            "Con Mayús, las líneas salen rectas, los recuadros cuadrados y los óvalos redondos.",
            "En el menú están «Relleno claro» y «Línea discontinua».",
            "La forma recién hecha queda elegida: puedes ajustarla con sus tiradores "
            "sin soltar la herramienta.",
        ),
        "esquema flecha recuadro círculo llave",
    ),
    "eraser": (
        ("Pulsa «Borrador» y toca lo que quieras quitar, o pasa por encima de varias cosas.",),
        (
            "Quita entero lo que toca (un trazo, una forma, un subrayado, una nota).",
            "Deshacer lo devuelve.",
            "En un recuadro o un óvalo hay que tocar el borde.",
        ),
        "goma quitar",
    ),
    "hide_annotations": (
        (
            "Pulsa «Ocultar anotaciones» para ver el documento limpio.",
            "El mismo botón las vuelve a enseñar.",
        ),
        (
            "No se borra nada: siguen ahí y se guardan igual.",
            "Al imprimir, la casilla «Con las anotaciones» decide si salen.",
        ),
        "limpio esconder mostrar",
    ),
    "bookmark": (
        (
            "Pulsa «Marcador» y se guarda el sitio que estás leyendo, con el nombre del "
            "primer título que se ve.",
            "Salen en el «Índice», dentro de «Mis marcadores»: un clic te devuelve allí.",
        ),
        (
            "Con el botón derecho sobre un marcador le cambias el nombre o lo quitas.",
            "Se guardan en el PDF como marcadores normales: Adobe y Edge también los ven.",
        ),
        "favorito señal marcar página",
    ),
    "go_to_article": (
        (
            "Pulsa «Ir a artículo» y escribe, por ejemplo, «art. 14», «3.2», «capítulo "
            "II» o «disposición adicional primera».",
        ),
        (
            "También funciona en la casilla de la página, abajo.",
            "Si lo escribes otra vez, te lleva al siguiente con ese número.",
            "Necesita el texto del documento: en un escaneado, primero «Reconocer texto».",
        ),
        "artículo apartado sección capítulo ley boe tema",
    ),
    "ocr": (
        (
            "Si el documento está escaneado, arriba sale una franja con «Reconocer texto». "
            "Púlsala (o el botón del modo Estudiar).",
            "Se hace en segundo plano: puedes seguir leyendo. «Cancelar» lo para y "
            "conserva las páginas ya leídas.",
            "Después ya puedes buscar, subrayar y copiar. Guarda para que el texto quede "
            "en el PDF.",
        ),
        (
            "La página se sigue viendo igual: el texto va invisible encima.",
            "Todo se hace en tu ordenador.",
        ),
        "ocr escaneado escanear foto imagen sin texto",
    ),
    "ocr_again": (
        (
            "En la flecha de «Reconocer texto», elige «Volver a reconocer texto».",
            "Elige qué páginas: todas las escaneadas, la que lees o las que escribas.",
        ),
        ("Úsalo cuando un PDF escaneado trae un texto malo y la búsqueda no encuentra nada.",),
        "ocr malo repetir",
    ),
    "annotations": (
        (
            "Pulsa «Anotaciones»: el panel de la izquierda lista todo lo que has marcado "
            "y escrito, en orden de lectura.",
            "Arriba eliges un color o un tipo (subrayados, notas, dibujos).",
            "Un clic te lleva a su sitio.",
        ),
        (),
        "lista subrayados notas filtrar color",
    ),
    "review": (
        (
            "Pulsa «Modo repaso»: todo lo resaltado y subrayado queda tapado.",
            "Intenta recordarlo y haz clic en un trozo para destaparlo; otro clic lo "
            "vuelve a tapar.",
            "Esc o el mismo botón terminan el repaso.",
        ),
        ("No cambia nada del documento.",),
        "repasar estudiar memorizar tapar",
    ),
    "beside": (
        (
            "Pulsa «Ver al lado»: con dos documentos abiertos, el otro se pone a la "
            "derecha; con más, te pregunta cuál.",
            "La raya del medio se puede mover.",
        ),
        (
            "También con el botón derecho sobre una pestaña → «Ver al lado».",
            "La X de la barra del de la derecha deja de verlo al lado sin cerrarlo.",
        ),
        "dos documentos a la vez tema y ley comparar",
    ),
    "link": (
        (
            "Selecciona unas palabras, botón derecho → «Enlazar a…».",
            "Elige el documento (de los abiertos, de la Biblioteca u otro) y, si lo "
            "sabes, el sitio («art. 14»).",
            "El otro documento se abre al lado: ajusta el sitio y pulsa «Enlazar aquí».",
        ),
        (
            "Un clic en el enlace abre el otro documento al lado, en ese sitio.",
            "Si el archivo se ha movido, el programa lo busca o te pregunta dónde está y "
            "corrige todos los enlaces a él.",
            "Adobe respeta estos enlaces; los navegadores (Edge, Chrome) suelen bloquearlos.",
        ),
        "enlace vínculo otro documento",
    ),
    "library": (
        (
            "Pulsa «Biblioteca» y elige la carpeta de tu temario (solo la primera vez).",
            "Salen todos los temas con su progreso: leído, subrayados y repasado.",
            "Doble clic abre un tema.",
        ),
        ("«Buscar en todos los temas» busca a la vez en todos, con las reglas del buscador.",),
        "temario carpeta temas progreso buscar en todos",
    ),
    "summary": (
        (
            "Pulsa «Exportar resumen» y elige si lo quieres en PDF o en Word.",
            "Sale todo lo resaltado, subrayado y anotado, ordenado por página.",
        ),
        ("El PDF no cambia. Al terminar se abre el resumen.",),
        "resumen apuntes word docx sacar",
    ),
    "margins": (
        (
            "Pulsa «Añadir margen» y elige dónde (derecha, izquierda, los dos lados o "
            "abajo), cuánto y en qué páginas.",
            "En el espacio nuevo puedes escribir y dibujar tus apuntes.",
        ),
        ("El contenido no se mueve. Deshacer lo quita.",),
        "espacio apuntes blanco",
    ),
    "insert_sheet": (
        (
            "Pulsa «Insertar hoja»: se pone una hoja nueva después de la página que lees.",
            "La flecha elige en blanco, de rayas o cuadriculada.",
        ),
        ("Es una página normal: en ella puedes escribir, dibujar y hacer esquemas.",),
        "página en blanco rayas cuadros esquema",
    ),
    # ---- Rellenar y firmar ----
    "fill_form": (
        (
            "Los campos del formulario se ven en azul claro. Haz clic en uno y escribe.",
            "Tab guarda lo escrito y pasa al siguiente; Mayús+Tab, al anterior.",
            "Las casillas se marcan con un clic; los desplegables enseñan sus opciones.",
        ),
        ("Con «Mis datos» rellenas tu nombre, DNI, dirección… de una vez.",),
        "formulario campos casillas instancia solicitud",
    ),
    "type_text": (
        (
            "Pulsa «Escribir» y haz clic donde quieras poner el texto: se escribe en la "
            "propia página.",
            "Ctrl+Intro o un clic fuera lo dejan puesto. Después se puede mover.",
        ),
        ("Sirve en cualquier PDF, también escaneado o sin campos.",),
        "escribir encima texto sin campos",
    ),
    "my_data": (
        (
            "Pulsa «Mis datos». La primera vez te pide tus datos (nombre, DNI, "
            "dirección, teléfono, correo…).",
            "Después, «Rellenar el formulario con mis datos» pone cada dato en su campo.",
            "En un PDF sin campos, elige un dato y haz clic donde va.",
        ),
        (
            "Tus datos se guardan solo en este ordenador; nunca se envían.",
            "Los campos que ya tienen algo no se tocan.",
        ),
        "dni nie dirección teléfono correo nombre",
    ),
    "my_data_edit": (("Pulsa «Editar mis datos» para cambiar los datos guardados.",), (), ""),
    "stamps": (
        (
            "Pulsa «Sellos» y elige uno: ✓, ✗, ●, la fecha de hoy, «Recibido» o uno tuyo.",
            "Haz clic donde va. Sigue en la mano para poner más, hasta que pulses Esc.",
        ),
        ("«Nuevo sello…» guarda un sello con tus palabras. «Tamaño» elige lo grande que sale.",),
        "marca casilla visto bueno cruz fecha",
    ),
    "sign_drawn": (
        (
            "Pulsa «Firmar» → «Poner mi firma» y haz clic donde va.",
            "La primera vez te pide crear tu firma.",
            "Se mueve y se cambia de tamaño como cualquier dibujo.",
        ),
        (
            "Debajo se pone la fecha de hoy (se puede quitar en el menú de Firmar).",
            "Al guardar, propone el nombre con «-firmado» para no pisar el original.",
            "Para una firma con validez legal, usa «Firmar con certificado».",
        ),
        "firma manuscrita contrato",
    ),
    "initials_everywhere": (
        (
            "Pulsa «Firmar» → «Poner mis iniciales en todas las páginas».",
            "Haz clic donde van: se ponen en el mismo sitio de todas las hojas.",
        ),
        ("Deshacer las quita de todas de una vez.",),
        "rubricar rúbrica",
    ),
    "my_signature": (
        (
            "Crea tu firma de una de tres formas: dibujándola, escribiendo tu nombre "
            "con letra manuscrita o desde una foto de tu firma en papel.",
            "Haz lo mismo con las iniciales.",
        ),
        (
            "De la foto se quita el papel y queda solo la tinta.",
            "Se guarda solo en este ordenador.",
        ),
        "crear firma foto imagen iniciales",
    ),
    "sign_certificate": (
        (
            "Pulsa «Firmar con certificado» y haz clic donde quieres el recuadro de la "
            "firma (si el documento trae un hueco de firma, haz clic dentro).",
            "Elige tu certificado (FNMT, DNIe…) o «Usar un archivo .p12 o .pfx…».",
            "Pon el PIN o la contraseña cuando Windows te lo pida.",
        ),
        (
            "Se guarda una copia «-firmado» y se abre en una pestaña nueva.",
            "Con DNIe: mete la tarjeta en el lector y pulsa «Actualizar» en la ventana "
            "del certificado.",
            "Ajustes → Firma: firma visible o invisible y sello de tiempo.",
            "El PIN y la contraseña nunca se guardan.",
        ),
        "firma digital electrónica fnmt dnie certificado validez legal pades autofirma",
    ),
    "sign_many": (
        (
            "Pulsa «Firmar varios documentos» y añade los documentos.",
            "Elige dónde va la firma (o invisible) y el certificado, una sola vez.",
        ),
        (
            "Cada uno se guarda como «nombre-firmado.pdf»; los originales no se tocan.",
            "Según el certificado, Windows pide el PIN una vez o en cada firma.",
        ),
        "lote muchos a la vez",
    ),
    "check_signatures": (
        (
            "Pulsa «Comprobar firmas»: sale cada firma del documento, quién firmó, cuándo "
            "y si es válida.",
        ),
        (
            "Se comprueba sin internet. Para la comprobación oficial, usa VALIDe.",
            "Al abrir un PDF firmado, la barra de abajo lo dice.",
        ),
        "validar verificar firma válida",
    ),
    # ---- Organizar ----
    "pages": (
        (
            "Pulsa «Ordenar páginas»: se abren las miniaturas.",
            "Arrastra una página (o varias, con Ctrl o Mayús) a otro sitio.",
            "Con el botón derecho: girar, mover al principio o al final, eliminar, "
            "extraer, insertar.",
        ),
        ("Alt + las flechas mueven las páginas elegidas desde el teclado.",),
        "reordenar mover orden",
    ),
    "rotate": (
        (
            "Pulsa «Rotar»: gira las páginas elegidas en las miniaturas, o la que lees.",
            "La flecha ofrece otras direcciones y «todas las páginas».",
        ),
        ("Este giro sí cambia el archivo al guardar (al contrario que «Girar vista»).",),
        "girar dar la vuelta",
    ),
    "delete_pages": (
        ("Elige las páginas en las miniaturas (o la que lees) y pulsa «Eliminar páginas».",),
        ("Siempre pregunta antes. Deshacer las recupera.",),
        "borrar quitar páginas",
    ),
    "insert_pages": (
        (
            "Pulsa «Insertar páginas» y elige PDF o imágenes (varios a la vez).",
            "Elige dónde van: después de la página que lees, al principio, al final o "
            "tras la página que digas.",
        ),
        ("Cada imagen es una hoja A4 con la foto entera.",),
        "añadir meter páginas imagen foto",
    ),
    "merge": (
        (
            "Pulsa «Unir» y añade los documentos; ordénalos subiendo, bajando o arrastrando.",
            "Se crea un PDF nuevo, que se abre. Los originales no se tocan.",
        ),
        ("Cada documento queda como un apartado del índice.",),
        "juntar combinar varios en uno",
    ),
    "split": (
        (
            "Pulsa «Dividir» y elige cómo: cada cierto número de páginas, por páginas "
            "(«1-3, 4-10, 11-») o por los apartados del índice.",
        ),
        ("Se crean archivos nuevos; nunca pisa uno que ya exista.",),
        "separar partir trocear",
    ),
    "extract_pages": (
        (
            "Elige las páginas en las miniaturas y, con el botón derecho, «Extraer páginas».",
            "Se crea un documento nuevo con ellas, que se abre.",
        ),
        (),
        "sacar copiar páginas",
    ),
    "photo_to_pdf": (
        (
            "Pulsa «De foto a PDF» y elige una o varias fotos de documentos (del móvil, "
            "por ejemplo).",
            "El programa encuentra la hoja: si hace falta, arrastra sus esquinas.",
            "Elige el aspecto (Documento, Gris, Blanco y negro o Foto sin retocar) y se "
            "crea un PDF, una página por foto.",
        ),
        (
            "Queda recto y sin sombras, como un escaneado.",
            "Después puedes «Reconocer texto» para buscar y subrayar en él.",
        ),
        "escanear escáner móvil foto imagen convertir",
    ),
    "export": (
        (
            "Pulsa «Exportar» y elige: las páginas como imagen (PNG o JPG) o el texto "
            "en un archivo .txt.",
            "Elige qué páginas: la que lees, las elegidas, todas o las que escribas.",
        ),
        ("Las imágenes pueden salir con o sin tus anotaciones.",),
        "imagen png jpg txt texto convertir",
    ),
    "redact": (
        (
            "Pulsa «Tapar datos» y arrastra un recuadro sobre lo que quieres borrar.",
            "La flecha ofrece tapar el texto seleccionado o «Buscar y tapar en todo el "
            "documento…» (un DNI, una cuenta).",
            "Guarda para que quede borrado en el archivo.",
        ),
        (
            "Se borra de verdad: debajo de la caja negra no queda nada que copiar.",
            "Mientras el documento está abierto, Deshacer lo recupera. Te propone "
            "«Guardar como» para conservar el original.",
        ),
        "tachar ocultar censurar dni cuenta privado",
    ),
    "compress": ((), (), "reducir tamaño peso ocupa menos"),
    "password": ((), (), "proteger clave cifrar"),
    "compare": ((), (), "diferencias cambios versiones ley modificada"),
}

# Pages with no button of their own.
_EXTRA: list[Topic] = [
    Topic(
        "recover_crash",
        SAVING,
        "Tras un apagón o un cierre inesperado",
        "No pierdes lo que estabas haciendo.",
        (
            "Abre el programa otra vez: vuelven tus pestañas, cada una en su página.",
            "Te pregunta si quieres recuperar los cambios sin guardar. Pulsa «Recuperar».",
        ),
        (
            "Cada cambio se apunta al instante en un archivo aparte; el PDF no se toca.",
            "También se salva lo que estabas escribiendo en una nota o un texto.",
            "Si dices «Ahora no», siguen en «Recuperar cambios descartados» unos días.",
        ),
        "apagón luz cuelgue bloqueo perder trabajo recuperar",
    ),
    Topic(
        "recover_discarded",
        SAVING,
        "Recuperar cambios descartados",
        "Si dijiste «No guardar» con prisa, aún puedes recuperarlo.",
        ("Menú → Archivo → «Recuperar cambios descartados» y elige el documento.",),
        ("Se conservan 7 días (se cambia en Ajustes → Guardado).",),
        "no guardar sin querer perdido",
        command="recover_discarded",
    ),
    Topic(
        "versions",
        SAVING,
        "Versiones anteriores",
        "Vuelve a como estaba el PDF antes de guardarlo.",
        (
            "Menú → Archivo → «Versiones anteriores».",
            "«Ver» abre esa versión en otra pestaña; «Restaurar» deja el documento así.",
        ),
        (
            "La primera vez que guardas en cada sesión, se conserva una copia de cómo estaba.",
            "Restaurar también se puede deshacer.",
            "Cuántas se conservan se elige en Ajustes → Guardado.",
        ),
        "copia antigua restaurar volver atrás historial",
        command="versions",
    ),
    Topic(
        "revert",
        SAVING,
        "Volver a como estaba al abrirlo",
        "Quita de una vez todos los cambios de esta sesión.",
        ("Menú → Archivo → «Volver a como estaba al abrirlo».",),
        ("No se pierde nada: «Rehacer» los devuelve uno a uno.",),
        "descartar todo deshacer todo",
        command="revert",
    ),
    Topic(
        "autosave",
        SAVING,
        "Guardar solo y qué hacer al cerrar",
        "Elige si el programa pregunta al cerrar o guarda por su cuenta.",
        (
            "Abre Ajustes → Guardado.",
            "«Al cerrar con cambios»: Preguntar (lo normal), Guardar siempre o No "
            "guardar nunca sin que lo pida.",
            "«Guardar solo mientras trabajo» guarda tras un rato sin editar.",
        ),
        ("Un PDF firmado nunca se guarda solo.",),
        "automático autoguardado cerrar preguntar",
        command="settings",
    ),
    Topic(
        "tabs",
        COMFORT,
        "Pestañas",
        "Ten varios documentos abiertos a la vez.",
        (
            "Cada PDF se abre en su pestaña. Un clic en una pestaña la pone delante.",
            "Ctrl+Tab pasa a la siguiente; la X, Ctrl+W o un clic con la rueda la cierran.",
            "Arrastrando las pestañas cambias su orden.",
        ),
        (
            "Al abrir el programa vuelven las pestañas de la última vez.",
            "Las pestañas que llevan rato sin mirarse «duermen» para gastar menos memoria.",
        ),
        "varios documentos abiertos",
    ),
    Topic(
        "pick_and_move",
        COMFORT,
        "Elegir, mover y cambiar lo que has puesto",
        "Corrige una nota, un dibujo o un subrayado sin hacerlo otra vez.",
        (
            "Haz clic en lo que has puesto: queda elegido, con un marco y tiradores.",
            "Arrástralo para moverlo, o usa las flechas. Los tiradores cambian el tamaño.",
            "En la barra pequeña que sale encima puedes cambiarle el color o borrarlo.",
        ),
        (
            "Supr lo borra; Ctrl+C, Ctrl+V y Ctrl+D lo copian, pegan y duplican.",
            "Lo hecho con otros programas solo se puede borrar.",
        ),
        "mover cambiar color tamaño borrar copiar pegar anotación",
    ),
    Topic(
        "favourites",
        COMFORT,
        "Herramientas favoritas",
        "Guarda tus combinaciones, como «rotulador amarillo fino».",
        (
            "Prepara una herramienta (color, grosor…) y, en la flecha de su botón, pulsa "
            "«Guardar en favoritas».",
            "Sale en una barra fina debajo de las herramientas del modo Estudiar: un clic la coge.",
        ),
        (
            "Los números 1 a 9 cogen las favoritas en su orden.",
            "Con el botón derecho las renombras, mueves o quitas.",
        ),
        "favorita rápida combinación",
    ),
    Topic(
        "color_names",
        COMFORT,
        "Poner nombre a tus colores",
        "Si quieres, da un significado a cada color («Definiciones», «Plazos»…).",
        ("Botón derecho sobre un color → «Ponerle nombre a este color…».",),
        (
            "El nombre sale al pasar el ratón y en el panel de anotaciones.",
            "No viene nada de fábrica: si no los usas, son simplemente colores.",
        ),
        "código de colores significado",
    ),
    Topic(
        "finder",
        COMFORT,
        "Buscar una función",
        "Escribe lo que quieres hacer y te lleva a la función, esté donde esté.",
        (
            "Pulsa el botón «Funciones» de arriba y escribe, por ejemplo, «firmar», «unir» "
            "o «rotar».",
            "Elige la función con las flechas e Intro.",
        ),
        ("Con F1 sobre una función de la lista, ves cómo se usa.",),
        "buscador funciones dónde está",
        command="finder",
    ),
    Topic(
        "appearance",
        COMFORT,
        "Tema oscuro, tamaño de letra y botones",
        "Ajusta el programa a tu vista y a tu pantalla.",
        (
            "Abre Ajustes → General.",
            "Elige el tema (claro, oscuro o el de Windows), el papel de las páginas y el "
            "tamaño de la interfaz.",
        ),
        ("En «Barra de herramientas» puedes dejar solo los iconos para ganar sitio.",),
        "oscuro claro grande pequeño letra tamaño iconos accesibilidad",
        command="settings",
    ),
    Topic(
        "keys",
        COMFORT,
        "Cambiar las teclas",
        "Elige la tecla de cada función, como los controles de un videojuego.",
        (
            "Abre Ajustes → Teclado.",
            "Doble clic en una función y pulsa la tecla nueva.",
        ),
        (
            "Si la tecla ya era de otra función, te lo dice y se la quita.",
            "«Restablecer todas» vuelve a las de siempre.",
        ),
        "atajos teclado tecla combinación",
        command="settings",
    ),
    Topic(
        "pen_touch",
        COMFORT,
        "Lápiz y pantalla táctil",
        "Estudia en una tableta o un Surface como en papel.",
        (
            "El lápiz hace todo lo que hace el ratón; la palma de la mano no pinta.",
            "Con un dedo mueves la página; con dos, la mueves y haces zoom.",
            "En Ajustes → Lápiz y dedo eliges si el dedo también dibuja.",
        ),
        ("La goma del lápiz, o su botón, borran.",),
        "tableta surface táctil dedo stylus presión",
        command="settings",
    ),
    Topic(
        "screen_reader",
        COMFORT,
        "Lector de pantalla (NVDA)",
        "El programa lee el texto de las páginas a NVDA, JAWS o Narrador.",
        (
            "Con el lector de pantalla en marcha, entra en el documento: te lee la página.",
            "Muévete por líneas con las flechas; al cambiar de página te dice cuál es.",
        ),
        (
            "Se activa solo con un lector de pantalla; F7 lo activa a mano.",
            "Ajustes → General → Accesibilidad tiene sus casillas.",
        ),
        "ciego accesibilidad nvda jaws narrador leer en voz cursor",
    ),
    Topic(
        "updates",
        COMFORT,
        "Versiones nuevas",
        "Actualiza el programa con un clic.",
        (
            "Cuando hay una versión nueva, sale una franja arriba con «Actualizar ahora».",
            "Se descarga, se comprueba, se instala y el programa vuelve con tus pestañas.",
        ),
        (
            "Nunca se actualiza sin que lo pidas.",
            "Menú → Ayuda → «Buscar versiones nuevas…» lo mira a mano.",
        ),
        "actualizar versión nueva",
        command="check_updates",
    ),
    Topic(
        "error_report",
        COMFORT,
        "Si algo falla",
        "Copia el informe de error para pegarlo donde quieras.",
        ("Menú → Ayuda → «Copiar informe de error» y pégalo con Ctrl+V donde quieras.",),
        ("Nunca se envía nada solo. Léelo antes: puede nombrar el documento abierto.",),
        "fallo error problema informe",
        command="copy_report",
    ),
]

# The tips shown on starting the program, with the page that explains each one.
TIPS: list[tuple[str, str]] = [
    ("Puedes convertir fotos de documentos en un PDF recto y limpio.", "photo_to_pdf"),
    ("El modo repaso tapa lo subrayado para que intentes recordarlo.", "review"),
    ("Escribe «art. 14» en la casilla de la página y te lleva a ese artículo.", "go_to_article"),
    ("Si dijiste «No guardar» con prisa, aún puedes recuperar los cambios.", "recover_discarded"),
    ("Puedes ver el tema y la ley a la vez, uno al lado del otro.", "beside"),
    ("Guarda tu firma una vez y firma contratos con un clic.", "sign_drawn"),
    ("Con «Mis datos» rellenas tu DNI y tu dirección en un formulario de una vez.", "my_data"),
    ("La Biblioteca busca en todos los temas de tu temario a la vez.", "library"),
    ("Exporta un resumen con todo lo que has subrayado, en PDF o en Word.", "summary"),
    ("Puedes añadir margen a las páginas para escribir tus apuntes.", "margins"),
    ("Mete una hoja de rayas o cuadriculada entre páginas para hacer esquemas.", "insert_sheet"),
    ("Los documentos escaneados se pueden reconocer para buscar y subrayar en ellos.", "ocr"),
    ("Guarda tus herramientas favoritas, como «rotulador amarillo fino».", "favourites"),
    ("Un enlace puede abrir otro PDF justo en el artículo que citas.", "link"),
    ("«Versiones anteriores» te deja volver a como estaba un PDF esta mañana.", "versions"),
    ("Puedes tapar un DNI de verdad antes de enviar un documento.", "redact"),
    ("Puedes firmar con tu certificado FNMT o tu DNIe, con validez legal.", "sign_certificate"),
    ("Puedes cambiar la tecla de cualquier función en Ajustes → Teclado.", "keys"),
    ("Con el modo lectura el papel se vuelve sepia, más cómodo para leer horas.", "reading_mode"),
    ("Haz clic en un subrayado para cambiarle el color sin hacerlo otra vez.", "pick_and_move"),
    ("Puedes unir varios PDF en uno, o dividir uno en partes.", "merge"),
]

TIPS_SETTING = "ayuda/trucos"  # show a tip when the program opens
_LAST_TIP = "ayuda/ultimo_truco"  # index of the last tip shown
_TIP_DAY = "ayuda/dia_truco"  # day (ISO) the last tip was shown


def _feature_topic(feature: Feature) -> Topic:
    steps, tips, keywords = _HOW.get(feature.id, ((), (), ""))
    return Topic(
        feature.id,
        feature.mode.value,
        feature.name,
        feature.description,
        steps,
        tips,
        f"{feature.keywords} {keywords}".strip(),
        feature=feature.id,
    )


TOPICS: list[Topic] = [_feature_topic(feature) for feature in FEATURES] + _EXTRA
_BY_ID = {topic.id: topic for topic in TOPICS}


def topic(topic_id: str) -> Topic | None:
    return _BY_ID.get(topic_id)


def topics_of(section: str) -> list[Topic]:
    return [item for item in TOPICS if item.section == section]


def _text_of(item: Topic) -> tuple[str, str, str]:
    """Title, the short line with its keywords, and all the rest, ready to match."""
    title = normalize_for_search(translate(item.title))
    short = normalize_for_search(f"{translate(item.summary)} {item.keywords}")
    rest = normalize_for_search(
        " ".join(translate(text) for text in (*item.steps, *item.tips, item.section))
    )
    return title, short, rest


def search_topics(query: str) -> list[Topic]:
    """The pages that have every typed word, the best first.

    Accents and capitals do not count ("firmar" finds "Firmar"; "ñ" is still
    not "n"). A word may be the start of a longer one ("escan" finds
    "escaneado").
    """
    words = normalize_for_search(query).split()
    if not words:
        return list(TOPICS)
    scored = []
    for position, item in enumerate(TOPICS):
        title, short, rest = _text_of(item)
        everything = f"{title} {short} {rest}"
        if not all(word in everything for word in words):
            continue
        if all(word in title for word in words):
            rank = 0 if title.startswith(words[0]) else 1
        elif all(word in title or word in short for word in words):
            rank = 2
        else:
            rank = 3
        scored.append((rank, position, item))
    return [item for _, _, item in sorted(scored, key=lambda entry: entry[:2])]


def tips_wanted(settings: Settings) -> bool:
    return settings.get(TIPS_SETTING, True) is not False


def tip_for_today(settings: Settings, today: datetime.date | None = None) -> tuple[str, str] | None:
    """The tip to show on opening the program, or None.

    At most one a day (opening the program five times does not give five
    tips), each time the next one of the list, so they do not repeat.
    """
    if not tips_wanted(settings):
        return None
    day = (today or datetime.date.today()).isoformat()
    if settings.get(_TIP_DAY) == day:
        return None
    return next_tip(settings, day)


def next_tip(settings: Settings, day: str | None = None) -> tuple[str, str]:
    """The tip after the last one shown (for "Otro truco")."""
    last = settings.get(_LAST_TIP, -1)
    index = (last + 1) % len(TIPS) if isinstance(last, int) else 0
    settings.set(_LAST_TIP, index)
    settings.set(_TIP_DAY, day or datetime.date.today().isoformat())
    return TIPS[index]
