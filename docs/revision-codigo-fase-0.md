# Revisión del código de la Fase 0

Fecha: 12/11/2026. Revisado: `main` (pull requests 2 a 13) más el pull request 14
(commit `fb64c0c`, aún sin fusionar). Carpetas: `app/core`, `app/ui`, `tests`,
`packaging` y `.github/workflows`.

## Resumen

**La base está bien hecha y se puede seguir construyendo encima.** Las 315 pruebas
automáticas pasan, el estilo del código está limpio, la lógica PDF está separada de
la interfaz como pide `CLAUDE.md`, y lo delicado (guardar ajustes, firmar, registro
de errores) se escribe de forma segura.

He encontrado **4 fallos que conviene arreglar pronto** (los cuatro comprobados con
una prueba real, no son suposiciones), **11 mejoras de importancia media** y unas
cuantas menores. Ninguno pierde datos ni rompe un PDF. Todos encajan en tareas que
ya están en el plan, así que no hace falta parar la Fase 1: el hilo de construcción
los irá metiendo en la tarea que toque.

Los cuatro importantes, en sencillo:

1. **El buscador no encuentra algunas palabras con "fi" o "fl"** ("oficina",
   "conflicto") en PDFs hechos con programas de maquetación, que juntan esas dos
   letras en un solo dibujo.
2. **En algunos PDF (sobre todo los hechos en Mac) "año" se encuentra buscando
   "ano" y no buscando "año".** Pasa cuando la tilde o la virgulilla van guardadas
   aparte de la letra. Rompe la regla de "la ñ no es una n".
3. **Un PDF cortado o a medio descargar se "abre" como un documento vacío**, sin
   ningún aviso, en lugar de decir que está dañado.
4. **Buscar en documentos muy largos gasta demasiada memoria** (con una ley del
   BOE, unos 0,7 MB por página; en un código de 1.000 páginas, unos 700 MB).

Lo que **no** he podido comprobar: lo que solo funciona en Windows (11 pruebas del
almacén de certificados se ejecutan en GitHub, no aquí) y la firma con un
certificado FNMT real, que sigue pendiente como ya sabías.

---

## Lista priorizada (para el hilo de construcción)

Cada punto dice dónde está, cómo se comprobó y en qué tarea del plan encaja.

### Prioridad alta

**A1. Buscador: ligaduras "ﬁ", "ﬂ", "ﬀ"… no se encuentran.** Tarea 1.4.
`app/core/search.py` lee el texto con `TEXT_PRESERVE_LIGATURES`, y
`normalize_for_search` usa NFD, que no separa U+FB00–FB06. Comprobado: un PDF con
"oﬁcina" (fuente DejaVu Serif) da 0 resultados para "oficina", "final" y
"conflicto". Arreglo: en `_simplify` (y en el modo exacto) expandir esas ligaduras a
sus letras; el "stream" ya admite que una letra de la página dé varios caracteres.
Añadir un PDF de ejemplo con ligaduras a `tests/ejemplos`.

**A2. Buscador: tildes y virgulilla "sueltas" (texto descompuesto).** Tarea 1.4.
`_simplify` y `_keep_exact` trabajan letra a letra, así que "n" + U+0303 se queda en
"n". Comprobado con "el año del camión" en NFD: "año" → 0 resultados, "ano" → 1; en
modo exacto "camión" → 0. Arreglo: al leer la página, unir cada marca combinante con
la letra anterior (NFC por parejas) antes de simplificar, conservando el mapa a las
letras de la página.

**A3. Un PDF truncado se abre con 0 páginas y sin aviso.** Tarea 1.11.
`pymupdf.open` "repara" el archivo y devuelve `page_count == 0`; ni `PdfDocument`
ni `MainWindow.open_document` lo tratan como dañado. Comprobado con la primera mitad
de `boe.pdf`: `open_document` devuelve `True`, vista vacía y el título cambia.
Arreglo: `PdfOpenError` si no hay páginas (también en el ayudante).

**A4. Memoria del ayudante al buscar.** Tarea 1.4.
`PageText` guarda por cada letra un `str`, una tupla de 4 `float` y un `int`.
Medido: `boe.pdf` 39 páginas → 27,5 MB (0,7 MB/página); `largo.pdf` 520 páginas →
156 MB. El tope es por número de páginas (`MAX_PAGE_TEXTS = 3000`), o sea hasta
unos 2 GB. Arreglo: guardar las letras como un solo `str`, las cajas en
`array('f')` y las líneas en `array('I')` (unas 10 veces menos), y poner el tope en
bytes, no en páginas.

### Prioridad media

**M1. La ventana abre el PDF con el motor ella misma y lo deja abierto.** Tareas 1.1/1.11.
`PdfDocument` (proceso de la ventana) abre el archivo y recorre todas las páginas
para leer tamaños. Dos consecuencias: un PDF que tumbe el motor al abrirse cierra el
programa entero (se pierde la ventaja del ayudante), y el archivo queda bloqueado en
Windows toda la sesión (estorbará al guardar en la Fase 2). Propuesta: que el
ayudante devuelva los tamaños junto con `opened`, o abrir-leer-cerrar.

**M2. Tres caídas del ayudante dan el documento entero por ilegible.**
`render_service.py`: `_crashes` solo se pone a cero en `open()`, y tras una caída la
vista vuelve a pedir la misma página. Una sola página mala inutiliza un temario de
500. Propuesta: recordar qué página se estaba dibujando, marcarla como fallida y no
volver a pedirla; poner el contador a cero tras varias páginas bien dibujadas.

**M3. El hilo que recibe las páginas muere en silencio si un aviso falla.**
`RenderService._read_results`: una excepción en `on_page`, `on_hits`, etc. sale del
bucle sin pasar por la gestión de caídas; el ayudante se queda bloqueado al enviar y
las páginas dejan de aparecer. Envolver cada aviso en `try/except` y apuntarlo en el
registro de errores.

**M4. Zoom muy alto: la página se vuelve a dibujar con cada movimiento.** Tarea 1.2.
Por encima de 60 millones de puntos `render_page` reduce el zoom y la vista guarda
ese zoom reducido; `_request_pages` lo compara con el pedido, nunca coinciden y
vuelve a pedirla en cada scroll (hasta 180 MB por página por la tubería, y la caché
de 400 MB se vacía sola). Pasa con A4 a partir de ~545 % en pantallas al 150 %, y
mucho antes con páginas grandes. Mientras no haya dibujo por trozos: guardar en la
caché el zoom pedido además del real.

**M5. Con archivo .p12/.pfx no se comprueba caducidad ni uso.** Tarea 4.2 (barato ahora).
La lista del almacén de Windows aparta los caducados y los que no sirven para
firmar; `load_p12_signer` no. Se puede firmar con un certificado caducado sin aviso.
Reutilizar `windows_store.describe()` sobre el certificado del archivo.

**M6. La "reescritura limpia" antes de firmar se fía solo de `get_sigflags()`.**
`signing._rewritten`: hay firmadores que no ponen `SigFlags`. Si pyHanko no pudiera
leer un PDF así, se reescribiría y la firma anterior quedaría rota en la copia, sin
aviso. Comprobar además si hay campos de firma (`/FT /Sig` con valor, o
`/ByteRange`) antes de reescribir. El original nunca se toca, por eso es media.

**M7. Firmar se hace en el hilo de la ventana.** Tarea 4.1.
`MainWindow.sign_document` llama a `sign_pdf` directamente; con documentos grandes
o mientras Windows pide el PIN, la ventana aparece como "No responde".

**M8. Falta la licencia y los avisos de terceros dentro del programa.** Tarea 1.14.
`packaging/build.py` no copia `LICENSE` a la carpeta ni hay un "Acerca de" con las
licencias (PyMuPDF AGPL, Qt LGPL, pyHanko MIT, Tesseract Apache, cryptography…).
Hay que tenerlo antes de hacer público el programa.

**M9. Las versiones de las dependencias indirectas no están fijadas.** Tareas 1.13/1.14.
`pyproject.toml` fija las 3 directas, pero `cryptography`, `asn1crypto`,
`pyhanko-certvalidator`, `shiboken6`, etc. se instalan "la última". Dos builds del
mismo código pueden salir distintos. Añadir un archivo de restricciones con todo
fijado; antes de publicar con actualización de un clic, fijar también las acciones
de GitHub por commit y la versión de Inno Setup, y publicar el SHA-256 de cada
descarga.

**M10. Capa de texto del OCR: páginas giradas y ancho de palabra.** Fase 2B.
`ocr.add_text_layer` usa las coordenadas de la página ya girada con `insert_text`,
que espera las de sin girar, y no trata el texto tumbado. Comprobado con una página
con `/Rotate 90`: la palabra reconocida en [32,425,39,471] queda escrita en
[32,461,39,462]. Además el texto invisible sale más estrecho que la palabra cuando
manda la altura (la selección no casará), y Helvetica no tiene todas las letras.
Usar `derotation_matrix`, escalar en horizontal (`morph`) y una fuente con todos los
signos.

**M11. Abrir un documento que falla a medias deja la ventana en mal estado.**
`PdfView.set_document` cierra el documento anterior y asigna el nuevo antes de
`page_sizes()`. Si esta falla: se pierde el anterior, el nuevo no se cierra (archivo
bloqueado), vista vacía con el título viejo. Leer los tamaños antes de cerrar el
anterior y cerrar el nuevo si falla.

### Prioridad baja

- **B1.** El informe de error tapa la carpeta personal, pero puede incluir nombres
  de documentos o rutas de otras unidades (por ejemplo en `SigningError`). Taparlos
  o decirlo en el aviso.
- **B2.** `Settings.save` usa siempre `ajustes.json.tmp`: dos ventanas del programa
  pueden pisarse. Se resuelve con la decisión de la tarea 1.10 (que un segundo
  doble clic abra el PDF en la ventana que ya existe).
- **B3.** Colores escritos a mano en `pdf_view.py` (marcas de búsqueda, hoja en
  blanco, `#767676`) en vez de los del tema.
- **B4.** En `ejecutable.yml`, asegurarse de que la carpeta `datos` creada al probar
  el programa no viaja dentro de la versión portátil publicada (borrarla antes de
  subir, o comprobar que no existe).
- **B5.** `_document_failed` avisa pero deja la vista vacía y el título anterior;
  volver a la pantalla de bienvenida.
- **B6.** `OcrJob` arranca un proceso por página (medio segundo cada vez) y no
  admite PDFs con contraseña. Para documentos enteros, un solo proceso. Fase 2B.
- **B7.** `show_search_hit` solo mueve el scroll vertical; con mucho zoom el
  resultado puede quedar fuera por un lado.
- **B8.** El ayudante se arranca en el hilo de la ventana al abrir el primer PDF;
  arrancarlo al iniciar el programa evita esa pequeña pausa.

### Lo que está bien y conviene mantener

- `core` no importa nada de `ui` y una prueba lo vigila; otra vigila que no se
  carguen las partes de IA de PyMuPDF.
- Escrituras seguras (archivo temporal y sustitución) en ajustes, registro de
  errores y firma.
- El ayudante de dibujo: listas de "páginas queridas" que se sustituyen, fichas
  para descartar respuestas viejas, vigilancia de su muerte también al arrancar.
- El puente con Windows para firmar libera bien lo que pide y distingue "cancelado".
- El programa empaquetado se prueba a sí mismo en GitHub (arranca, abre, firma, OCR).

### No comprobado

- Pruebas que solo corren en Windows (11, del almacén de certificados): se ejecutan
  en GitHub.
- Firma con certificado FNMT real, VALIDe y Adobe: pendiente, sin cambios.
- B4 es una sospecha por lectura del flujo, no la he visto ocurrir.
