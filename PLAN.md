# Plan de Lector-PDF

> Plan aprobado (revisado el 11/11/2026). Las instrucciones completas están en `CLAUDE.md`.
> Cada tarea va en su propio pull request con un `.exe` de prueba.

Estado: ⬜ pendiente · 🔄 en curso · ✅ hecho

Cada tarea dice **cómo comprobar que está terminada** (lo prueba el usuario en su Windows).
Al acabar cada fase se publica una versión descargable en *Releases*.

---

## Fase 0 – Cimientos
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 0.1 | Estructura del proyecto y dependencias | El código se organiza según `CLAUDE.md` |✅ |
| 0.2 | Creación automática del instalador y la versión portátil en GitHub | En cada pull request aparece un `.exe` de prueba descargable; al publicar una versión, el instalador y la portátil van a *Releases*; sé cuánto ocupan y cuánto tardan en abrir |✅ |
| 0.3 | PDFs de prueba en `tests/ejemplos/` (BOE, formulario, más de 500 páginas, escaneado, con OCR malo, con contraseña, firmado con certificado de prueba) | Existen y las pruebas automáticas los usan |✅ |
| 0.4 | Esqueleto de la interfaz: pestañas de modos (Leer, Estudiar, Rellenar y firmar, Organizar), Ctrl+1…4, buscador de funciones (Ctrl+K), modo claro/oscuro | Cambio de modo y cambian las herramientas visibles |✅ |
| 0.5 | Registro de errores local y botón "Copiar informe de error" | Provoco un error de prueba, copio el informe y lo pego |✅ |
| 0.6 | Prueba de concepto: rendimiento (PDF de 500 páginas, renderizado en segundo plano, pantallas al 125/150 %) | Hago scroll por todo el documento sin tirones y el texto se ve nítido | ✅ |
| 0.7 | Prueba de concepto: buscador (sin tildes, palabras partidas con guion, la ñ no es n) | "articulo" encuentra "Artícu-lo" partido; "año" no encuentra "ano" | ✅ |
| 0.8 | Prueba de concepto: firma con certificado del almacén de Windows (FNMT) con pyHanko | Firmo un PDF con mi certificado instalado y Adobe/VALIDe lo dan por válido; si no sale, tengo explicadas las alternativas | 🔄 construido; falta tu prueba con el certificado real |
| 0.9 | Prueba de concepto: OCR con Tesseract incluido en el `.exe` | Reconozco una página escaneada en español sin instalar nada aparte; sé cuánto crece el instalador | ✅ |

Lo que queda por probar en Windows (de las fases 0 a 4 y de las mejoras) está
en [`docs/pruebas-pendientes.md`](docs/pruebas-pendientes.md).

**Medidas de la tarea 0.2** (programa casi vacío, 11/11/2026; crecerá con las funciones):
instalador 42 MB; versión portátil 59 MB en `.zip`. La portátil es una carpeta en `.zip`
y no un único `.exe`: la carpeta abre en menos de 1 segundo y el `.exe` único tarda
2,7 segundos cada vez, porque se descomprime en cada arranque.

**Resultado de la tarea 0.6** (rendimiento, 11/11/2026):
- Una página de texto se dibuja en 1 a 6 milésimas de segundo; una escaneada, en 30 a 150.
  Leer el tamaño de las 520 páginas del PDF largo cuesta 10 milésimas: abrir es inmediato.
- Hallazgo importante: mientras el motor PDF dibuja una página, el resto del programa
  se queda parado, aunque se dibuje "en segundo plano" de la forma habitual (un hilo).
  Con páginas escaneadas, la ventana daba tirones de 80 milésimas o más. Solución: las
  páginas se dibujan en un **proceso ayudante** aparte. Así la ventana no para nunca
  (parones medidos: unas 10 milésimas) y, si un PDF dañado tumba el motor, solo cae el
  ayudante, que se reinicia solo.
- Nitidez al 125 % y 150 %: cada punto de la página cae en un punto exacto de la
  pantalla, sin estirar la imagen. Lo comprueba una prueba automática punto por punto.
- Solo se dibujan las páginas a la vista y las vecinas; se guardan hasta 400 MB de
  páginas ya dibujadas y se olvidan las más lejanas.
- Queda para la Fase 1: dibujar por trozos con zoom muy alto (ahora una página nunca
  pasa de 60 millones de puntos y a partir de ahí se estira), y que el ayudante se
  entere de los cambios cuando haya anotaciones (Fase 2).

**Resultado de la tarea 0.7** (buscador, 11/11/2026):
- Funciona lo prometido: "articulo" encuentra "Artículo" y también "Artícu-lo" partido
  entre dos líneas; "camion" encuentra "CAMIÓN"; "año" no encuentra "ano" ni al revés.
  Las frases que siguen en la línea siguiente se encuentran, también en el BOE real.
- Cómo: el texto de cada página se convierte en una tira simplificada (sin tildes ni
  mayúsculas, con los saltos de línea como espacios y las palabras partidas unidas) y
  se recuerda de qué letra de la página sale cada carácter, para poder marcarlo.
- Un guion al final de línea solo une si sigue una minúscula. Si la palabra lleva guion
  de verdad ("físico-químico" partido justo ahí), se encuentra escrita con y sin guion.
- Rapidez: las 520 páginas del PDF largo, en 1 segundo la primera vez y al instante
  las siguientes. Se busca en el proceso ayudante y dibujar páginas tiene prioridad,
  así que buscar no frena el scroll. Los resultados van saliendo según se encuentran.
- Ya hay panel de búsqueda (Ctrl+F): lista con la frase alrededor, marcas en la página,
  Intro y Mayús+Intro, "Palabra completa" y "Coincidencia exacta". Como mucho 5.000
  resultados por búsqueda.
- Queda para la tarea 1.4: frases que saltan de una página a la siguiente, resaltar en
  negrita la palabra en la lista, y probar con columnas y tablas. La búsqueda
  aproximada para fallos de OCR (1/l, 0/O) es de la Fase 2B.

**Resultado de la tarea 0.8** (firma con certificado, 11/11/2026):
- El puente con Windows está hecho: el programa pide a Windows la lista de certificados
  instalados y le pide que firme; la clave nunca sale de Windows y la contraseña o el
  PIN los pide Windows en su propia ventana.
- Comprobado en las máquinas Windows de GitHub con certificados de prueba instalados en
  el almacén: clave RSA guardada a la manera moderna, RSA a la manera antigua (como
  muchos certificados FNMT instalados hace años) y clave de curva elíptica. Las tres
  firman y la firma se valida.
- La firma es PAdES (el estándar europeo), invisible, e incluye las autoridades que
  avalan el certificado cuando Windows las conoce. Se guarda siempre como copia nueva.
- **Lo que solo puede comprobar el usuario:** que funciona con su certificado FNMT real
  y que VALIDe y Adobe Reader dan la firma por válida. Está en la lista de pruebas.
- Hallazgo: los PDF del BOE tienen un detalle que pyHanko no sabe leer. Solución: si un
  documento no se deja preparar y no tiene firmas, se reescribe limpio antes de firmar.
  Si ya tuviera firmas, no se toca y se avisa.
- **Alternativas si el certificado instalado no funcionara** (plan B): 1) firmar con el
  archivo `.p12`/`.pfx` exportado, que ya funciona y está en la misma ventana; 2) apoyarse
  en AutoFirma (programa del Gobierno) para la firma, dejando el resto al Lector-PDF.
- Queda para la Fase 4: firma visible, sello de tiempo, DNIe con lector, firmar varios
  documentos, guardar sobre el mismo archivo y PDFs con contraseña.
- Aviso para la Fase 2 (guardado): mientras un PDF está abierto, Windows no deja
  sustituir el archivo. Para "guardar en el mismo archivo" habrá que soltarlo un momento.

**Resultado de la tarea 0.9** (reconocer texto, 11/11/2026):
- Funciona sin instalar nada aparte. El motor Tesseract ya viene dentro de PyMuPDF, así
  que no hace falta incluir otro programa: solo el archivo del idioma español (2,3 MB,
  versión "rápida" de Tesseract, licencia Apache 2.0), en `app/recursos/tessdata`.
- **El instalador crece 1 MB** (de 51,7 a 52,7 MB) por el reconocimiento de texto. (La firma de la
  tarea 0.8 lo había subido de 42 a 52 MB.)
- Calidad con el escaneado de prueba (torcido, gris y con ruido): lee bien más del 90 %
  de las palabras, con tildes y eñes. Tarda 1 segundo por página.
- Comprobada la cadena completa: página escaneada → texto reconocido → texto invisible
  encima de la página (PDF estándar; la página se ve igual) → el buscador de la tarea
  0.7 encuentra "articulo" y "camion" y los marca en su sitio.
- Se reconoce a la resolución del propio escaneado: agrandarlo empeoraba el resultado.
- Como dibujar páginas, reconocer va en un proceso aparte para no parar la ventana.
- Queda para la Fase 2B: guardar la capa de texto en el PDF, hacerlo con todo el
  documento con progreso y cancelar, enderezar y limpiar la imagen, rehacer un OCR malo
  y decidir si compensa la versión "mejor" del idioma (unos 13 MB, más lenta) viendo
  temarios escaneados de verdad.

**Aspecto del programa** (12/11/2026, a petición tuya: "se ve muy soso"):
- Diseño propio: color añil con un toque amarillo de rotulador, logotipo (una hoja con
  una línea subrayada), iconos dibujados para el programa (sin librerías de iconos),
  modos como pestañas redondeadas, herramientas con icono y nombre, agrupadas.
- Pantalla de bienvenida con botón "Abrir un PDF"; también se abre arrastrando un PDF
  a la ventana y con Ctrl+O. Menú Archivo.
- Panel de búsqueda y buscador de funciones rediseñados; la palabra encontrada sale
  marcada en la lista. Páginas con sombra. Claro y oscuro con el contraste comprobado.
- El programa y el instalador tienen ya su icono.
- "Formas y flechas" pasa a llamarse "Formas" para que quepan todas las herramientas.

**Primera prueba tuya en Windows** (12/11/2026) y lo que se ha corregido:
- La firma funciona, pero se firmó con un certificado que Windows crea para el
  ordenador (su nombre es un código), y por eso Adobe avisaba de "problemas". Ahora
  esos certificados se apartan y solo se puede firmar con los de personas.
  **Pendiente:** repetir la prueba con el certificado FNMT y validarlo en VALIDe.
- El buscador de funciones se cierra también con un clic fuera.
- El documento se abre a un tamaño cómodo (como mucho 125 %) y no ampliado a todo
  el ancho. Nuevo control de tamaño abajo a la derecha (barra, − y +, y el % con
  un menú) y nueva función "Ver página entera".
- En la búsqueda, flecha abajo y flecha arriba pasan al resultado siguiente y al
  anterior. (Izquierda y derecha no: mueven el cursor por la palabra escrita.)
- Las funciones que aún no están hechas se ven más apagadas y lo dicen al pasar
  el ratón (por ejemplo "Rotar", que llegará en la Fase 5).
- Escaneado girado y de mala calidad: el reconocimiento falla porque la hoja está
  tumbada. Girándola antes mejora mucho, pero no llega a ser bueno. Girar y
  enderezar solo es parte de la Fase 2B; con escaneados así de malos no se puede
  prometer un resultado perfecto.
- Apuntado para la Fase 3: firma manuscrita guardada y sellos, fáciles de usar, y
  proponer el nombre "-firmado" al guardar un documento firmado.

## Fase 1 – Lector
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 1.1 | Abrir un PDF y verlo con scroll continuo | Abro un tema del BOE y paso páginas con la rueda sin tirones | ✅ |
| 1.2 | Zoom, ajustar a ancho/página, rotar, pantalla completa | Ctrl+rueda hace zoom; los botones ajustan la vista | ✅ |
| 1.3 | Panel lateral: miniaturas e índice | Clic en una miniatura o en un apartado del índice me lleva allí | ✅ |
| 1.4 | Buscador sin tildes ni mayúsculas, con palabras partidas por guion | Busco "articulo" y encuentra "Artículo", también si está partido entre líneas | ✅ |
| 1.5 | Lista de resultados con contexto, resaltado y siguiente/anterior | Veo todos los resultados con su frase y salto entre ellos con Intro | ✅ |
| 1.6 | Seleccionar y copiar texto | Copio un artículo y lo pego en otro programa | ✅ |
| 1.7 | Pestañas (varios PDFs a la vez) | Tengo 3 temas abiertos y cambio entre ellos | ✅ |
| 1.8 | Reabrir la sesión anterior, recordar página, archivos recientes | Cierro y reabro: vuelven mis pestañas, cada una en su página | ✅ |
| 1.9 | Modo oscuro, modo lectura (sepia), tamaño de interfaz | Cambio de modo y se ve bien | ✅ |
| 1.10 | Abrir con doble clic / "Abrir con" / arrastrar / programa predeterminado | Doble clic en un PDF lo abre en Lector-PDF | ✅ |
| 1.11 | PDFs con contraseña o dañados | Pide la contraseña; un PDF roto da un aviso y no cierra el programa | ✅ |
| 1.12 | Imprimir | Imprimo unas páginas concretas | ✅ |
| 1.13 | Aviso de nuevas versiones y **actualizar con un clic** (desactivable) | Si hay versión nueva en GitHub, me avisa; pulso "Actualizar ahora", se descarga, se instala y el programa se reinicia ya actualizado, sin perder ajustes ni pestañas (necesita el repositorio público) | ✅ |
| 1.14 | Versión 0.1 (instalador y portátil) y repositorio público | Lo instalo, o lo abro sin instalar, y funciona todo lo anterior | ✅ |
| 1.15 | Arreglos de la revisión del código de la Fase 1 | Abro tres PDFs a la vez y acaban en una sola ventana; busco con comillas y guiones del teclado; el zoom con el panel táctil va suave | ✅ |

Notas de la Fase 1:
- 1.1 quedó hecha con las pruebas de la Fase 0 (scroll continuo, páginas dibujadas
  en un proceso ayudante, abrir desde el menú, el botón o arrastrando).
- 1.2: "Girar vista" (Ctrl+R) gira las páginas solo en pantalla, sin tocar el
  archivo; girar páginas de verdad es de Organizar (Fase 5). Pantalla completa con
  F11 (Esc para salir). En la barra de abajo, "Página [12] de 39": se escribe un
  número y con Intro se va allí (Ctrl+G).
- 1.3: panel a la izquierda con dos pestañas, Miniaturas e Índice (botones de Leer
  o F4). Viene cerrado; el programa recuerda si lo dejaste abierto y en qué pestaña.
  Las miniaturas se dibujan solo para las páginas a la vista, después de las páginas
  que se están leyendo, así que no frenan la lectura ni con 500 páginas. El índice
  marca el apartado en el que estás. Si el PDF no trae índice, lo dice.
  De paso: al cambiar el ancho de la ventana (o abrir un panel) con la vista
  ajustada, el documento se queda en la página que se estaba leyendo (antes saltaba).
- 1.4 y 1.5: el buscador ya estaba hecho en la Fase 0; aquí se completa con lo que
  encontró la revisión y con las frases que pasan de página:
  - Letras unidas ("ﬁ", "ﬂ"): "oficina" se encuentra aunque el PDF la escriba con
    una sola pieza para "fi" (A1).
  - Tildes y "ñ" escritas en dos piezas (letra + acento): "año" sigue sin ser "ano" (A2).
  - Una frase que acaba en una página y sigue en la siguiente se encuentra, saltándose
    el pie y la cabecera que hay en medio (se reconocen porque se repiten a la misma
    altura en las dos páginas). En la lista sale como "Pág. 7-8" y se marca en las dos.
    Límite: hasta 6 líneas a cada lado del salto de página.
  - El texto de las páginas ocupa unas 7 veces menos memoria (A4) y el tope ya es
    por memoria (96 MB), no por número de páginas.
  - Si el resultado queda fuera por un lado (con mucho zoom), la vista se mueve
    también en horizontal (B7).
  - M4: con mucho zoom ya no se piden una y otra vez páginas que no caben en memoria.
    Sigue pendiente dibujar por trozos para que el zoom alto sea ligero de verdad
    (tarea P.3).
  - B3: los colores que quedan escritos en la vista son los del papel (blanco en
    claro y en oscuro), ahora con nombre; no dependen del aspecto.
- 1.6: se selecciona arrastrando el ratón sobre el texto (doble clic: una palabra;
  Mayús+clic: hasta ahí; Ctrl+A: todo; Esc o un clic: quitar). Se copia con Ctrl+C,
  con el botón Copiar, con el menú Editar o con el botón derecho. Lo copiado sale
  como texto seguido: las líneas de un párrafo se unen y las palabras partidas con
  guion vuelven a estar enteras, para pegarlo limpio en Word o en unos apuntes.
  La selección puede abarcar varias páginas (arrastrando más allá del borde, el
  documento avanza). En una página escaneada avisa de que no hay texto y propone
  "Reconocer texto".
- 1.7: cada PDF se abre en su pestaña, con su propio zoom, página, búsqueda y panel
  lateral. Se cierran con su X, con Ctrl+W o con un clic de la rueda; Ctrl+Tab pasa
  de una a otra; se pueden reordenar arrastrando. Abrir un PDF que ya está abierto
  lleva a su pestaña. Arrastrar varios PDFs a la ventana abre varias pestañas.
  Cada pestaña tiene su propio proceso ayudante: un PDF problemático no afecta a
  los demás. A cambio, cada pestaña abierta gasta algo de memoria aunque no se
  mire; si con muchas pestañas pesa, se podrán "dormir" las que no se usan.
  - M1: la ventana ya no deja el PDF abierto; lo lee y lo suelta. Queda apuntado
    para la Fase 2 que el ayudante sí lo tiene abierto y habrá que soltarlo al guardar.
  - B8: al arrancar el programa se prepara ya el ayudante del siguiente documento,
    así abrir un PDF no espera a que arranque.
- 1.8: al abrir el programa vuelven las pestañas de la última vez, cada una en su
  página y con la que estaba delante. Cualquier documento, al volver a abrirlo,
  aparece en la página y en el modo de trabajo en que se dejó. "Archivo → Abrir
  recientes" guarda los 12 últimos (con "Vaciar esta lista") y los 5 últimos salen
  también en la pantalla de bienvenida. Si un documento ya no está, se salta y se
  avisa abajo. Todo esto se guarda solo en el ordenador, en el archivo de ajustes.
  Volver a las pestañas se podrá desactivar en la ventana de Ajustes (tarea 1.9).
- 1.9: el **papel de las páginas** se elige aparte del tema claro u oscuro: blanco
  (como es el documento), sepia (tono cálido) o noche (papel oscuro y letra clara).
  Solo cambia lo que se ve en pantalla, nunca el PDF ni lo que se imprime. El botón
  "Modo lectura" del modo Leer pone y quita el sepia. "Ver → Tema" y "Ver → Papel
  de las páginas" lo cambian también. Nueva ventana **Archivo → Ajustes** (Ctrl+,)
  con tema, papel, tamaño de la interfaz (100, 110, 125, 150 o 175 %) y "Volver a
  las pestañas de la última vez". Todo se aplica al momento menos el tamaño, que
  necesita reiniciar: la ventana lo dice y ofrece "Reiniciar ahora" (vuelven las
  pestañas). El reinicio (`app/core/restart.py`) servirá también para la
  actualización con un clic (1.13).
  - En el papel "noche" los colores se invierten (el azul del BOE se ve anaranjado).
    Cuando haya subrayados de colores (Fase 2) habrá que cuidar que el amarillo
    siga viéndose amarillo.
  - Las pruebas de la interfaz tardaban cada vez más porque las ventanas de cada
    prueba no se destruían; ahora sí, y vuelven a tardar la mitad.
- 1.10: **una sola ventana**. Decidido por Julen el 13/11/2026: si el programa ya
  está abierto, un segundo PDF (doble clic, "Abrir con", arrastrado al icono) entra
  como pestaña nueva en esa ventana, que pasa al frente. La copia nueva le pasa el
  archivo a la que ya está abierta y termina; se hablan por un canal privado del
  propio ordenador y del propio usuario, nada pasa por la red
  (`app/core/single_instance.py`). Resuelve B2 de la revisión.
  - El instalador ofrece el programa a Windows para los PDF (sale en "Abrir con" y
    en la lista de programas predeterminados), solo para el usuario y sin permisos
    de administrador. Windows no deja que un programa se ponga él mismo como
    predeterminado: en Ajustes hay un botón "Usar Lector-PDF para abrir los PDF…"
    que abre la ventana de Windows donde se elige. En la versión portátil ese botón
    apunta el programa en Windows solo si se pulsa, y "Quitar de «Abrir con»" lo
    deshace.
  - La creación automática del programa comprueba ya, con el programa de verdad,
    que un segundo arranque se une a la ventana abierta, y limpia la carpeta
    `datos` de las pruebas antes de publicar (B4).
- 1.11: un PDF **con contraseña** la pide en una ventana propia (con "Mostrar la
  contraseña"); si no es correcta lo dice y deja probar otra vez. La contraseña no
  se guarda nunca: al volver las pestañas de la última vez, se pide de nuevo. Un PDF
  **dañado o a medio descargar** da un aviso claro y no abre pestaña (antes un
  archivo cortado se abría vacío, A3). Si solo está dañada **una página**, esa hoja
  lo dice y el resto del documento se lee con normalidad (antes, tres fallos daban
  el documento entero por perdido, M2). Si un documento ya abierto deja de poder
  mostrarse, se cierra su pestaña y se avisa (B5). Un fallo de la ventana al recibir
  una página ya no deja las demás sin dibujar; se apunta en el registro de errores
  (M3). M11 quedó resuelto con el cambio de la 1.7.
  - Pendiente para sus fases: reconocer texto (2B) y firmar (4) en PDFs con
    contraseña siguen sin poder hacerse; lo dicen con un aviso.
- 1.12: **Imprimir** (botón del modo Leer, Archivo → Imprimir, Ctrl+P) con una
  ventana propia y sencilla: impresora, páginas (todas, la que se está viendo o
  las que se escriban, como "1-5, 8, 12-"), copias, tamaño (ajustar al papel o
  tamaño real), dos caras y blanco y negro. Dice cuántas páginas saldrán y explica
  qué está mal si las páginas escritas no tienen sentido. Recuerda la impresora y
  la forma de imprimir; las páginas y las copias no. Cada hoja sale de pie o
  tumbada según su página. Se imprime en segundo plano, con progreso y "Cancelar",
  y se puede seguir leyendo. Una página dañada se salta y se avisa al final de
  cuáles faltan. Se imprime el documento tal cual: ni el giro de la vista ni el
  papel sepia o noche salen en el papel.
  - Usa la parte de impresión que ya trae Qt (QtPrintSupport); no añade ninguna
    dependencia. Las pruebas imprimen de verdad a un archivo PDF y lo comprueban;
    la creación del programa también lo comprueba con el programa empaquetado.
  - No comprobado con una impresora real (queda para la sesión de pruebas).
  - Para la Fase 2: al imprimir, opción de sacar o no las anotaciones.
- Revisión del código de la Fase 0 (`docs/revision-codigo-fase-0.md`): sus puntos
  se arreglan dentro de la tarea a la que pertenecen:
  - 1.4 buscador: A1, A2, A4, B7 (hechos).
  - 1.7 pestañas: M1, B8 (hechos).
  - 1.11 dañados: A3, M2, M3, M11, B5 (hechos).
  - B1 hecho en la 1.11: el aviso de error dice que el informe puede nombrar el
    documento abierto, para leerlo antes de enviarlo (M4 y B3 también hechos).
  - 1.14 versión 0.1: M8 (licencias incluidas), M9 (versiones fijadas). B2 y B4
    hechos en la 1.10.
  - Una decisión se consulta cuando llegue su tarea: en la 1.14, una ventana
    "Acerca de" con la licencia y los avisos de terceros (M8).
  - Fase 2B: M10, B6. Fase 4: M5, M6, M7.
- 1.13: **aviso de versiones nuevas y actualizar con un clic.** A los pocos segundos
  de abrir, el programa pregunta a GitHub cuál es la última versión publicada (no
  envía ningún dato). Si hay una más nueva sale una franja discreta encima de las
  pestañas: "Actualizar ahora", "Ver novedades", "Ahora no" (lo recuerda la próxima
  vez) y "Omitir esta versión" (no vuelve a avisar de esa). "Actualizar ahora"
  descarga con progreso y Cancelar, comprueba que la descarga es exactamente la
  publicada (huella SHA-256; si no coincide o no se puede comprobar, no se instala),
  cierra el programa, instala y lo abre de nuevo con sus pestañas. En la versión
  instalada lo hace el instalador en silencio; en la portátil, la versión nueva
  sustituye la carpeta conservando `datos` y, si algo falla, vuelve a poner la que
  había. "Ayuda → Buscar versiones nuevas…" lo consulta a mano. En Ajustes,
  "Avisarme cuando haya una versión nueva" (activado por defecto).
  - **No funcionará hasta que el repositorio sea público y exista una versión
    publicada (1.14).** Mientras tanto no dice nada. La prueba real con dos
    versiones publicadas queda para la sesión final de pruebas.
  - Las pruebas automáticas usan un GitHub simulado; además, en cada compilación se
    comprueba con el programa real que la portátil se sustituye a sí misma y
    conserva los ajustes (`packaging/check_update.py`).
  - En la portátil, durante los segundos que dura el cambio no hay ventana a la
    vista. Si se echa en falta, se puede añadir un aviso pequeño.
  - "Antes guarda lo pendiente": hoy no hay nada que guardar. En la Fase 2 la
    actualización pasa por la misma pregunta de cierre (Guardar / No guardar /
    Cancelar); si se cancela, no se instala (ya está previsto en el código).
  - Publicar una versión añade ahora el archivo `SHA256SUMS.txt` con las huellas.
- 1.14: **versión 0.1.0 publicada el 13/11/2026** y repositorio público. El código
  pasa a decir 0.1.1, que se publicará solo para probar de verdad la actualización
  con un clic desde la 0.1.0. **Probado por Julen el 13/11/2026 con la versión
  instalada: funcionó como debía.** Falta probarlo con la portátil.
  - **Acerca de** (Ayuda → Acerca de Lector-PDF): versión, que es software libre,
    enlace al código y lista en lenguaje llano de las piezas que usa con su
    licencia. La carpeta `licencias` del programa lleva el texto de todas (M8); la
    compilación las recoge sola y comprueba que están.
  - **Versiones fijadas** (M9): `packaging/versiones-fijadas.txt` fija todo lo que
    se instala para probar y compilar, también lo que traen las dependencias. Las
    acciones de GitHub van fijadas por commit. La versión de Inno Setup queda
    apuntada en el resumen de cada compilación (se usa la del servidor de GitHub).
  - El contador "Dibujo de página" y "Provocar un error de prueba" solo salen en
    las versiones de prueba, no en la publicada.
  - **Pasos que solo puede dar Julen:** hacer público el repositorio (Settings →
    General → Danger Zone → Change visibility) y crear la *Release* `v0.1.0`
    (Releases → Draft a new release → etiqueta `v0.1.0` → Publish). GitHub adjunta
    solo el instalador, la portátil y `SHA256SUMS.txt`.
  - Después de publicar: pedir la firma de código gratuita a SignPath (quita el
    aviso de Windows al instalar) y probar la actualización de verdad con una 0.1.1.
- **Arreglos tras las pruebas de Julen (13/11/2026):**
  - Ir a una página mayor que el total lleva a la última (antes Intro no hacía nada).
  - Buscar una frase copiada del documento que pasa de una página a la siguiente
    funciona aunque lleve en medio el pie y la cabecera de página, y aunque sea
    larga. Una palabra pegada con el guion de fin de línea ("artícu- lo") se
    encuentra junta. Los títulos que caen a la misma altura en dos páginas seguidas
    ("Artículo 21", "Artículo 27") ya no se confunden con cabeceras.
  - PDF con contraseña abierto con doble clic: primero viene la ventana al frente
    y luego pregunta; si se abre varias veces el mismo archivo, pregunta una sola vez.
  - Nuevo **"Tamaño inicial"** (botón del modo Leer, menú del % y Ctrl+0): vuelve al
    tamaño con el que se abrió el documento.
  - Prueba nueva con 16 PDFs rotos de formas distintas (cortados, con trozos
    cambiados, quitados o metidos): la ventana aguanta todos.
- **Barras de arriba más compactas (13/11/2026, decidido por Julen):** el documento
  es el protagonista, como en Edge.
  - Los menús (Archivo, Ver, Ayuda…) ya no ocupan una fila: están en el botón
    **Menú** de la esquina (Alt+M). Todos los atajos siguen funcionando igual.
  - El **buscador de palabras** está siempre a la vista arriba, junto al buscador
    de funciones (Ctrl+K), que ahora ocupa menos. Escribir ahí abre el panel de
    resultados; Intro, Mayús+Intro y las flechas pasan de uno a otro; Esc lo cierra.
  - Filas más bajas: en una pantalla de portátil (1366×768) las barras ocupaban
    237 puntos de alto y ahora 179. Con **"solo iconos"** (Ajustes → Barra de
    herramientas), 170; el nombre de cada botón sale al pasar el ratón.
  - Letra pequeña: la fila de modos mide 34 puntos de alto, algo menos que los 40
    recomendados para el dedo; los botones de herramientas siguen en 40 o más. Se
    revisará con una pantalla táctil de verdad en la tarea 2.11.
- **1.15, arreglos de la revisión del código de la Fase 1 (13/11/2026).** La lista
  completa está en `revision-codigo-fase-1.md` (archivos del proyecto). Hecho:
  - **Varios PDFs abiertos a la vez acaban en una sola ventana.** Antes, si se
    abrían tres de golpe, podían quedar dos ventanas, cada una guardando sus
    pestañas por su cuenta. Ahora el programa decide quién es la copia principal
    nada más arrancar, antes de crear la ventana; las demás le pasan sus archivos
    (insisten hasta 3 segundos) y terminan. Hay una prueba que lanza tres copias
    de verdad a la vez. De paso: alguien que se conecta y cuelga ya no deja a la
    copia principal sin escuchar.
  - **Buscador con comillas, apóstrofos y guiones tipográficos.** Los documentos
    traen “ ” « » ’ – — y el teclado escribe " ' -: ahora se encuentran igual
    ("d'hondt" encuentra «d’Hondt», "coste-beneficio" encuentra «coste–beneficio»).
    Con "Coincidencia exacta" se siguen distinguiendo.
  - **Zoom con Ctrl + rueda o pellizco del panel táctil:** sigue la cantidad
    movida (antes cada aviso pequeño era un paso entero y el zoom se disparaba) y
    deja quieto lo que hay bajo el puntero. Falta verlo en un portátil real.
  - **No se avisa de una versión nueva hasta que tiene su archivo** (instalador o
    portátil, según el caso) **y su huella.** GitHub tarda unos minutos en
    adjuntarlos después de publicar.
  - **Queda para la Fase 2** (cada cosa en la tarea que le toca):
    - guardar la página por la que se va también mientras se lee, no solo al
      cerrar; no perder pestañas si el programa se cierra mientras las restaura,
      ni olvidar las de un USB sin enchufar; si `ajustes.json` no se puede leer
      una vez, no pisarlo (**todo hecho el 14/11/2026**, ver notas de la Fase 2A);
    - tarea nueva de memoria: "dormir" las pestañas que llevan rato sin verse y un
      tope común de memoria (15 o 20 temas abiertos pasan de 1 GB): tarea P.2;
    - **decidido el 23/11/2026:** que NVDA lea el texto del documento (hoy lee
      menús y botones, no las páginas) es la tarea P.5;
    - detalles menores B1 a B9 de la revisión.

## Fase 2A – Anotar y guardado
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.1 | Botones Guardar / Guardar como junto a Imprimir, con escritura segura (archivo temporal y sustitución) | Ctrl+S guarda en el mismo archivo; "Guardar como" crea otro; si el archivo está bloqueado, avisa y no pierdo nada | ✅ |
| 2.2 | Resaltar, subrayar, tachar | Selecciono texto y lo marco; tras guardar se ve igual en Edge o Adobe | ✅ |
| 2.3 | Paleta de colores completa, grosor y opacidad | Elijo cualquier color para cada herramienta | ✅ (el grosor llega con el dibujo, 2.8) |
| 2.4 | Deshacer / rehacer (cada cambio es una "orden", ver `CLAUDE.md` §5) | Ctrl+Z y Ctrl+Y funcionan con todo | ✅ |
| 2.5 | **Diario de recuperación** | Apago el ordenador a la fuerza mientras subrayo, lo enciendo y no he perdido nada | ✅ |
| 2.6 | **Preguntar al cerrar** (Guardar / No guardar / Cancelar), "Volver a como estaba al abrirlo", recuperar cambios descartados, e indicador "Guardado / Cambios sin guardar" | Subrayo, cierro y me pregunta; si le doy a "No guardar" con prisa, aún puedo recuperarlo | ✅ |
| 2.6b | **Versiones anteriores** y avisos que salen siempre (firmado, cambios fuertes, no se puede guardar, cambiado por otro programa) | Vuelvo a como estaba el PDF esta mañana; un PDF firmado nunca se guarda solo | ✅ (el aviso de cambios fuertes llega con cada herramienta que borra páginas, tapa datos o cambia el texto) |
| 2.6c | **Ajustes de guardado**: qué hacer al cerrar (preguntar / guardar siempre), guardar solo mientras trabajo (desactivado por defecto), versiones y días que se conservan | Activo "guardar solo" y ya no me pregunta al cerrar | ✅ |
| 2.7 | Notas adhesivas y cuadros de texto | Escribo notas y texto con la fuente, tamaño y color que quiero | ✅ (tres tipos de letra; mover y cambiar de tamaño llega con la 2.9) |
| 2.8 | Dibujo a mano alzada, flechas, formas, borrador | Dibujo y borro sobre la página | ✅ (con ratón; lápiz y dedo llegan con la 2.11) |
| 2.9 | Seleccionar, mover, redimensionar, copiar y borrar anotaciones | Corrijo una anotación mal puesta sin rehacerla | ✅ (solo las hechas con este programa) |
| 2.10 | Herramientas favoritas | Guardo "rotulador amarillo fino" y lo uso con un clic | ✅ |
| 2.11 | Lápiz y pantalla táctil | Subrayo con lápiz en una tableta sin que la mano pinte | ✅ (hecho sin tableta: falta la prueba con un lápiz y una pantalla táctil de verdad) |
| 2.12 | Mostrar/ocultar anotaciones (también al imprimir/exportar) | Con un botón veo el documento limpio | ✅ (exportar llegará con la Fase 5) |
| 2.13 | Atajos de teclado para cada herramienta | Cambio de herramienta sin usar el ratón | ✅ |
| 2.13a | Escribir texto directamente sobre la página (tras la prueba del 15/11) | Hago clic y escribo ahí mismo; elijo tamaño, negrita, color y ancho sin salir del texto | ✅ |
| 2.13b | Símbolos y flechas dentro del texto | Pongo →, ⇒, ✓, • … mientras escribo, sin buscarlos fuera | ✅ |
| 2.13c | Más formas y más cómodas | Hago un esquema con flechas, llaves y recuadros con texto sin volver a coger la herramienta cada vez | ✅ (texto dentro de un recuadro: con el texto encima, por ahora) |
| 2.13d | Hoja en blanco, de rayas o cuadriculada (adelantada de la 2C) | Añado una hoja entre páginas y hago en ella un esquema | ✅ |
| 2.13e | Borrar anotaciones de otros programas | Quito un subrayado hecho con Edge, y Deshacer lo devuelve igual | ✅ |
| 2.14 | Versión 0.2 | Estudio un tema completo con el programa durante una sesión real | 🔶 Release v0.2.0 publicada (16/11/2026); falta usarla en una sesión real |


Notas de la Fase 2A:
- **2.1, Guardar y Guardar como (13/11/2026).**
  - Botones **Guardar** y **Guardar como** junto a Imprimir (modo Leer), en el menú
    Archivo y con Ctrl+S y Ctrl+Mayús+S desde cualquier modo. Guardar está apagado
    mientras no haya nada pendiente. Todavía no hay nada que cambie el documento
    (eso llega con la 2.2), así que de momento solo se puede usar "Guardar como".
  - **Escritura segura** (`app/core/saving.py`): el documento entero se escribe en
    un archivo temporal al lado (`.nombre.pdf.guardando`), se comprueba que es un
    PDF completo con las mismas páginas y solo entonces ocupa el sitio del
    original, de un golpe. Hay una prueba que mata el programa en seis momentos
    distintos mientras guarda: el archivo siempre queda entero.
  - **Si no se puede guardar** (otro programa lo tiene abierto, la nube lo está
    sincronizando, solo lectura, disco lleno) lo reintenta unos instantes, avisa
    con el motivo y ofrece "Guardar como". No se pierde nada: los cambios siguen
    en el documento abierto y el archivo del disco es el de antes, entero.
  - **Guardar como** sigue trabajando en el archivo nuevo (como Word): la pestaña
    cambia de nombre y el archivo original queda como estaba. No deja guardar
    encima de un archivo abierto en otra pestaña.
  - Un PDF con contraseña la conserva al guardarlo.
  - Cómo funciona por dentro: guarda el proceso ayudante, que es quien tiene el
    documento abierto con sus cambios. Para guardar encima de su propio archivo
    tiene que soltarlo un momento (Windows no deja sustituir un archivo en uso).
  - Decisión pequeña a revisar en la 2.2: los botones están solo en el modo Leer,
    junto a Imprimir, como pedía el plan. Cuando se pueda subrayar (modo Estudiar)
    habrá que verlos también allí.
  - Pendiente de sus tareas: preguntar al cerrar e indicador de estado (2.6),
    versiones anteriores y avisos de PDF firmado (2.6b), y que los cambios
    sobrevivan a una caída del ayudante (2.5, diario).
- **2.2 y 2.4, resaltar, subrayar, tachar, deshacer y rehacer (14/11/2026).**
  - En el modo Estudiar: **Resaltar** (amarillo), **Subrayar** y **Tachar** (rojo).
    Dos formas de usarlos: con texto ya seleccionado, el botón lo marca; sin nada
    seleccionado, el rotulador se queda "en la mano" (botón pulsado) y todo lo que
    se seleccione queda marcado, hasta pulsar Esc o el botón otra vez. Con el
    rotulador en la mano, doble clic marca una palabra. También con clic derecho.
  - Se ve al momento en la página y en la miniatura. **El PDF no cambia hasta
    Guardar.** El botón Guardar está ahora también al principio de las barras de
    Estudiar, Rellenar y Organizar.
  - **Deshacer y rehacer** (Ctrl+Z, Ctrl+Y o Ctrl+Mayús+Z, botones y menú Editar),
    sin límite, por documento. En el buscador, Ctrl+Z sigue deshaciendo lo escrito.
  - Lo guardado son anotaciones PDF normales. Comprobado abriendo el resultado con
    el motor de PDF de Chrome y Edge: se ve igual (`capturas/subrayar-en-chrome.png`).
    Falta verlo en Adobe Reader (prueba de Julen).
  - Las marcas caen en su sitio también en páginas guardadas giradas (90, 180 y
    270 grados), que es lo habitual en escaneados.
  - **Diseño interno** (`app/core/commands.py`, `CLAUDE.md` §5.8): cada cambio es
    una "orden" con sus datos, que sabe aplicarse, deshacerse y escribirse como
    texto. El ayudante, que tiene el documento abierto, las ejecuta. Deshacer,
    rehacer y (tarea 2.5) el diario salen de esa misma pieza. **Toda herramienta
    nueva que cambie el documento tiene que ser una orden.**
  - Si el ayudante se cae, el nuevo recibe otra vez las órdenes sin guardar: las
    marcas no se pierden mientras el programa siga abierto. Que sobrevivan a un
    apagón es la tarea 2.5.
  - Todavía no: elegir color (2.3), quitar una marca suelta pinchando en ella o
    cambiarla (2.9; de momento, con Deshacer).
- **2.6, primera parte: preguntar al cerrar e indicador de guardado (14/11/2026).**
  - Al cerrar una pestaña con cambios sin guardar pregunta **Guardar / No guardar /
    Cancelar**. Al cerrar el programa, una sola ventana con la lista de los
    documentos pendientes y **Guardar todos**. Cerrar la pregunta con la X o con
    Esc es "Cancelar".
  - "Guardar" guarda y, cuando ha terminado bien, cierra. Si alguno no se puede
    guardar (archivo ocupado, solo lectura…) sale el aviso de siempre y nada se
    cierra: no se pierde nada.
  - **Indicador siempre a la vista**, abajo a la derecha: "Guardado", "Guardando…"
    o "Cambios sin guardar". Además, la pestaña con cambios pendientes lleva un
    punto (●) junto al nombre.
  - "Actualizar ahora" pasa por la misma pregunta: si se elige Guardar, guarda,
    cierra e instala; si se cancela, no se instala nada.
  - Recuperar lo que se cerró con "No guardar" llegó con el diario (2.5), y
    "Volver a como estaba al abrirlo" después (ver más abajo).
- **2.3, colores y opacidad (14/11/2026).**
  - Resaltar, Subrayar y Tachar llevan una **flecha al lado** que abre su color:
    paleta rápida de 10 colores (seis de rotulador y cuatro de bolígrafo), **"Más
    colores…"** para elegir cualquiera, los últimos colores propios usados (hasta
    5, comunes a las tres herramientas) y la **opacidad** (del 10 al 100 %).
  - Elegir un color lo usa al momento, como coger un rotulador del estuche: con
    texto seleccionado lo marca; sin nada seleccionado, el rotulador queda en la
    mano con ese color.
  - Cada herramienta recuerda su color y su opacidad, también al cerrar el
    programa. El botón enseña el color en una franja bajo el dibujo. Las marcas
    ya hechas no cambian al elegir otro color.
  - Los colores no significan nada ni traen nombres de uso ("importante",
    "repasar"…): eso es la tarea 2.26 y es opcional.
  - Comprobado en el motor de PDF de Chrome y Edge, también con opacidad
    (`capturas/colores-en-chrome.png`). Falta verlo en Adobe Reader.
  - **Grosor:** no se ha hecho aquí a propósito. Un subrayado o tachado estándar
    de PDF no guarda grosor (cada lector lo dibuja al suyo), así que ofrecerlo
    sería prometer algo que Adobe o Edge no respetarían. El grosor tiene sentido
    con el dibujo a mano y las formas (2.8) y se hará allí.
- **2.5, diario de recuperación (14/11/2026).**
  - **Cada cambio se apunta al instante** en un archivo pequeño aparte del PDF
    (carpeta `diario`, junto a los ajustes; en la portátil, dentro de `datos`).
    Uno por documento con cambios sin guardar. El PDF no se toca.
  - **Tras un apagón, un cuelgue o un cierre a la fuerza**, al abrir el programa
    vuelven las pestañas y pregunta: "Estos documentos tenían cambios sin
    guardar" con **Recuperar** / **Ahora no**. Recuperar los devuelve como
    cambios sin guardar (se pueden deshacer); el PDF solo cambia al pulsar Guardar.
  - **"No guardar" ya no pierde nada:** los cambios se apartan 7 días y se
    recuperan en **Archivo → Recuperar cambios descartados**. Lo mismo si se dice
    "Ahora no" tras un apagón. La pregunta de cerrar lo explica.
  - Al guardar bien, el diario de ese documento se vacía. Si guardar falla, se
    queda. Con "Guardar como", el diario sigue al archivo nuevo.
  - Lo deshecho no se recupera (deshacer y rehacer también se apuntan).
  - **Escritura segura:** cada cambio es una línea añadida y enviada al disco en
    el momento. Si la luz se va a mitad de una línea, esa línea se ignora y las
    demás valen. Hay una prueba que mata el programa en seis momentos mientras
    apunta sin parar: no se pierde ningún cambio ya apuntado.
  - Si el programa muere justo después de sustituir el PDF pero antes de vaciar
    el diario, recuperar no duplica las marcas (cada una lleva su nombre).
  - **La página por la que se va** se recuerda a los 2 segundos de cambiarla, no
    solo al cerrar: tras un apagón el documento vuelve donde estaba (era el punto
    M1 de la revisión de la Fase 1).
  - Diseño: el diario escribe las mismas "órdenes" que usa deshacer
    (`app/core/journal.py` sobre `commands.to_dict`). No hay un sistema aparte.
  - Queda para la 2.6c (ajustes): elegir cuántos días se conservan los cambios
    descartados (hoy, 7).
  - No probado con un apagón de verdad en Windows (prueba de Julen): solo
    simulado matando el programa.
- **2.6, final: "Volver a como estaba al abrirlo" (14/11/2026).**
  - **Archivo → Volver a como estaba al abrirlo** quita de una vez todos los
    cambios hechos desde que se abrió el documento, también los que ya se
    hubieran guardado en esta sesión (el PDF no cambia hasta pulsar Guardar).
  - No pregunta, porque no se pierde nada: **Rehacer** (Ctrl+Y) los devuelve uno
    a uno. Apagado mientras no haya cambios.
- **Dos arreglos pendientes de la revisión de la Fase 1 (14/11/2026).**
  - **Pestañas (M2):** mientras vuelven las pestañas de la última vez no se
    apunta nada, así que cerrar el programa a la fuerza en ese rato (por ejemplo
    con la ventana de contraseña a la vista) ya no olvida las demás. Y la pestaña
    de un archivo que hoy no está (USB sin enchufar, carpeta de red o de la nube
    aún no lista) se guarda hasta 30 días y vuelve sola cuando el archivo vuelve.
    Cancelar la contraseña al arrancar sí olvida esa pestaña (decisión: quien
    cancela no quiere abrirlo).
  - **Ajustes (M4):** si `ajustes.json` existe pero no se puede leer (un
    antivirus o la sincronización lo tienen cogido), se reintenta y **nunca se
    escribe encima sin haberlo leído**; lo que se cambie mientras tanto se añade
    cuando por fin se lee. Si está dañado se aparta como `ajustes.dañado.json` y
    se usa la última copia buena (`ajustes.copia.json`, que se renueva en cada
    arranque que lo lee bien). Si los ajustes no se pueden guardar (disco lleno,
    USB protegido) se avisa una vez abajo, no en silencio.
  - De paso: las pruebas automáticas de la interfaz tardaban cada vez más
    (ventanas de prueba que no se destruían y se iban acumulando). Ahora cada
    prueba limpia lo que deja; la tanda de interfaz pasa de 7 minutos y medio a
    menos de 3.
- **2.6b, primera parte: versiones anteriores (14/11/2026).**
  - **La primera vez que se guarda un PDF en cada sesión** se conserva antes una
    copia de cómo estaba (carpeta `versiones`, junto a los ajustes; en la
    portátil, dentro de `datos`). También si con "Guardar como" se va a pisar un
    archivo que ya existía.
  - **Archivo → Versiones anteriores:** lista con fecha y tamaño. **Ver** abre
    esa versión en otra pestaña sin cambiar nada (no cuenta como archivo
    reciente ni vuelve como pestaña). **Restaurar** deja el documento como
    estaba; antes guarda lo de ahora como una versión más, así que restaurar
    también se puede deshacer. Los cambios sin guardar que hubiera van al
    diario (recuperables 7 días).
  - Límites por defecto: 10 versiones por documento y 1 GB entre todas; se
    borran las más antiguas. La versión recién hecha nunca se borra por falta de
    sitio. Elegir estos límites será un ajuste (2.6c).
  - Si no se puede conservar la versión (disco lleno), se guarda igualmente y se
    avisa: lo importante es no perder los cambios.
  - Dos versiones idénticas seguidas no se guardan dos veces.
- **2.6b, final: avisos que salen siempre al guardar (14/11/2026).**
  - Antes de guardar en el mismo archivo el programa mira tres cosas: si el
    PDF está firmado con certificado, si otro programa ha cambiado el archivo
    desde que se abrió (o desde nuestro último guardado) y si está en una
    carpeta temporal (adjunto de correo). Si pasa alguna, pregunta: **Guardar
    como…** (lo recomendado), **Guardar aquí de todos modos** o **Cancelar**.
  - Sale también al cerrar eligiendo "Guardar"; si se cancela, no se cierra.
  - "Guardar aquí de todos modos" vale para el resto de la sesión en ese
    documento (no pregunta en cada guardado), salvo que otro programa vuelva a
    cambiar el archivo: entonces pregunta otra vez.
  - Tras "Guardar como" de un PDF firmado, la copia es el archivo de trabajo y
    ya no avisa: el original firmado queda intacto.
  - Lo que deja el otro programa no se pierde: queda en Versiones anteriores.
  - Cuando llegue "guardar solo" (2.6c), un documento con alguno de estos
    avisos nunca se guardará solo.
  - Pendiente a propósito: el aviso de "cambios fuertes"
    (borrar páginas, tapar datos, cambiar el texto) se hará con cada una de
    esas herramientas (Fases 5 y 6). El archivo de solo lectura ya ofrecía
    "Guardar como" desde la 2.1.
- **2.6c: ajustes de guardado (14/11/2026).**
  - La ventana de Ajustes tiene ahora dos pestañas, "General" y "Guardado",
    para que quepa en pantallas pequeñas.
  - **Al cerrar con cambios:** *Preguntar* (por defecto), *Guardar siempre* o
    *No guardar nunca sin que lo pida*. Con "No guardar nunca" cierra sin tocar
    el PDF y los cambios quedan en "Recuperar cambios descartados".
  - **Guardar solo mientras trabajo:** desactivado por defecto. Activado,
    guarda tras un rato sin cambios (10 s, 30 s, 1, 2 o 5 minutos; por defecto
    30 s) y al cambiar de pestaña. Cada cambio vuelve a empezar la cuenta, así
    que nunca guarda mientras se edita, ni mientras hay una pregunta abierta.
  - Con "guardar solo" activado, al cerrar también guarda sin preguntar (la
    otra opción queda apagada mientras tanto).
  - **Nunca se guarda solo** un PDF firmado, uno que otro programa ha cambiado
    o uno en carpeta temporal: lo dice abajo y espera a que el usuario pulse
    Guardar, que es cuando sale el aviso. "Guardar siempre" al cerrar también
    pasa por ese aviso.
  - Si un guardado automático falla (archivo bloqueado…), la ventana que lo
    explica sale una sola vez; luego lo reintenta tras el siguiente cambio y
    solo lo dice abajo. Los cambios siguen en el diario.
  - **Versiones anteriores:** cuántas por documento (3, 5, 10, 20 o 50) y
    cuánto pueden ocupar entre todas (250 MB a 5 GB). Bajar el límite no borra
    nada en el momento: se aplica en el siguiente guardado.
  - **Cambios descartados:** 1, 3, 7, 14 o 30 días.
  - Un valor raro en el archivo de ajustes cuenta como el valor por defecto.
- **2.7: notas adhesivas y cuadros de texto (15/11/2026).**
  - En el modo Estudiar, los botones **Nota** y **Cuadro de texto** se quedan
    "en la mano" como los rotuladores: un clic en la página abre un panel
    pequeño para escribir. Guardar (o Ctrl+Intro, o un clic fuera) lo pone en
    la página; Esc lo descarta.
  - Un clic en una nota la abre para leerla, cambiarla o borrarla. Un texto
    se abre con doble clic (o con un clic si se lleva la herramienta). El botón
    derecho ofrece Editar y Borrar. Al pasar el ratón por una nota se lee.
  - La flecha de cada botón elige el color; la del texto, además, el tipo de
    letra y el tamaño. Se recuerdan para la próxima vez.
  - Son anotaciones PDF estándar (nota = "Text", texto = "FreeText").
    Comprobado que se ven igual en el motor de Chrome/Edge; en Adobe Reader,
    pendiente de la prueba manual.
  - **Tipos de letra: solo tres** (sin remates, con remates y máquina de
    escribir), porque son los que cualquier lector de PDF trae y así el texto
    se ve igual en todas partes. Otras fuentes exigirían guardar el texto como
    dibujo (ver la "letra pequeña" de `CLAUDE.md`); queda para más adelante si
    se echa de menos.
  - Se escribe en un panel, no directamente sobre la página. Es más sencillo y
    seguro; escribir sobre la propia página sería una mejora posterior.
  - Todo son "órdenes": deshacer, rehacer, diario de recuperación y versiones
    funcionan igual que con los subrayados.
  - Las notas hechas con otros programas se pueden leer, no cambiar ni borrar
    (llevan datos que este programa perdería). Se revisará en la 2.9.
  - Mover una nota o un texto ya puesto y cambiarle el tamaño llega con la 2.9.
  - El cuadro de texto nunca se sale de la página: si una línea no cabe, se
    parte por los espacios.
- **2.8: dibujo a mano, flechas, formas y borrador (15/11/2026).**
  - **Dibujar:** con el botón en la mano, se dibuja sobre la página con el
    ratón pulsado. El trazo se ve mientras se hace y no parpadea al soltarlo.
    Cada trazo es un paso de Deshacer. Un trazo no se sale de su página.
  - **Formas:** flecha, línea, recuadro y óvalo. Se elige cuál en la flecha del
    botón (empieza en "Flecha") y se pone arrastrando. Una forma diminuta (un
    clic sin querer) no se pone.
  - **Color, grosor y opacidad** de dibujo y de formas, cada uno el suyo, en la
    flecha de su botón: grosor Fino, Normal, Grueso o Muy grueso (1, 2, 4 y
    8 puntos). Se recuerdan. Con esto queda hecho el grosor aplazado en la 2.3.
  - **Borrador:** quita **entero** lo que toca (un trazo, una forma, un
    subrayado, una nota o un texto), con un clic o pasando por encima de
    varios. No borra trocitos de un trazo: en un PDF estándar eso obligaría a
    partirlo en pedazos, y con Deshacer se recupera cualquier cosa borrada.
    En un recuadro o un óvalo hay que tocar el borde, no el hueco, para no
    borrar sin querer lo que rodea.
  - El borrador solo quita lo hecho con este programa; lo dibujado con otros
    se respeta, como las notas (se revisará en la 2.9). De un subrayado que
    ocupa dos páginas quita la parte de la página que se toca.
  - Son anotaciones PDF estándar ("Ink", "Line", "Square" y "Circle").
    Comprobado que se ven igual en el motor de Chrome/Edge
    (`capturas/dibujo-en-chrome.png`); en Adobe Reader, pendiente de la prueba
    manual.
  - Con el dibujo, las formas o el borrador en la mano no se selecciona texto.
    Esc suelta la herramienta (y, a medio trazo, descarta ese trazo).
  - Pendiente para la 2.11: presión del lápiz, palma de la mano y dedos. Para
    la 2.9: mover o cambiar de tamaño un dibujo ya hecho.
- **2.9: elegir, mover, cambiar de tamaño, copiar y borrar (15/11/2026).**
  - **Elegir:** sin ninguna herramienta en la mano, un clic sobre una nota, un
    texto, un dibujo o una forma lo elige: sale un marco de puntos con
    tiradores en las esquinas. Un clic fuera (o Esc) lo suelta.
  - **Mover:** arrastrándolo, o con las flechas del teclado (un punto cada
    vez; diez con Mayús). Nunca se sale de su página.
  - **Cambiar de tamaño:** arrastrando un tirador. En una línea o una flecha,
    los tiradores son sus dos extremos. Un dibujo a mano se estira con su
    marco. Un texto cambia el tamaño de su letra. Una nota es un icono de
    tamaño fijo: se mueve, no se agranda.
  - **Borrar:** Supr (o Retroceso), o "Editar → Borrar anotación".
  - **Copiar, pegar y duplicar:** Ctrl+C, Ctrl+V y Ctrl+D. Pegar pone la copia
    donde está el ratón, o un poco más abajo del original; también vale en
    otro documento. Con nada elegido, Ctrl+C sigue copiando el texto
    seleccionado.
  - El botón derecho ofrece Copiar, Duplicar, Borrar y "Pegar aquí".
  - **Subrayados, resaltados y tachados:** un clic los elige y Supr los borra,
    pero no se mueven ni se copian, porque van con sus palabras. Arrastrar
    sobre ellos sigue seleccionando texto.
  - **Notas:** un clic sigue abriéndola; arrastrarla la mueve.
  - Cada movimiento es un paso de Deshacer y se apunta en el diario.
  - **Anotaciones de otros programas** (revisado, como se dijo en la 2.7):
    siguen sin poder moverse ni borrarse. Para deshacer bien un borrado hay
    que poder reconstruir la anotación exacta, y las de otros programas llevan
    datos que este no conoce. Se podría añadir un "borrar anotación ajena"
    más limitado si se echa de menos; queda apuntado como idea.
  - Pendiente: cambiar el color de una anotación ya puesta (ahora: borrar y
    volver a poner) y elegir varias a la vez.
- **2.10: herramientas favoritas (15/11/2026).**
  - En la flecha de cada herramienta (resaltar, subrayar, tachar, nota, texto,
    dibujar y formas) hay **"Guardar en favoritas"**: guarda esa herramienta
    tal como está en ese momento (color y, según la herramienta, opacidad,
    grosor, forma o letra).
  - Las favoritas salen en una **barra fina debajo de las herramientas**, solo
    en el modo Estudiar y solo cuando hay alguna (si no, no ocupa sitio). Un
    clic pone la herramienta así y la deja en la mano; con texto seleccionado,
    un rotulador favorito lo marca directamente.
  - Cada favorita lleva el nombre de lo que es ("Dibujar · rojo · grueso").
    Con el botón derecho se le puede **cambiar el nombre**, **moverla** a
    izquierda o derecha y **quitarla**.
  - La que se lleva en la mano se ve pulsada. La misma combinación no se
    guarda dos veces. Caben 12, para que siga siendo una barra rápida.
  - Se guardan en los ajustes del programa (no en el PDF) y valen para todos
    los documentos.
  - No trae ninguna favorita de fábrica: cada persona guarda las suyas.
- **2.11: lápiz y pantalla táctil (15/11/2026).**
  - **Aviso importante:** se ha hecho y probado sin tableta, fabricando a mano
    las señales que mandan un lápiz y unos dedos. Falta probarlo con un lápiz
    y una pantalla táctil de verdad (lista de pruebas a mano); es probable que
    ahí salgan ajustes finos.
  - **El lápiz hace todo lo que hace el ratón** (dibujar, formas, subrayar,
    notas, elegir y mover).
  - **Presión:** con la herramienta Dibujar, el trazo sale más grueso donde se
    aprieta más (entre un tercio y algo más de vez y media del grosor
    elegido; apretando a medias, el grosor elegido). Se ve así ya mientras se
    dibuja. Un lápiz que no nota la presión dibuja trazos normales.
  - **Cómo se guarda:** sigue siendo un trazo estándar ("Ink") con su grosor
    normal, y además lleva dibujado su aspecto con el grosor variable, que es
    lo que enseñan los demás lectores. Comprobado en el motor de Chrome/Edge;
    en Adobe Reader, pendiente de la prueba manual. La presión de cada punto
    se guarda también dentro de la anotación, para que al moverlo, cambiarlo
    de tamaño, copiarlo o deshacer un borrado vuelva idéntico.
  - **Borrar con el lápiz:** la goma del otro extremo, o el botón del lápiz
    apretado, borran sin cambiar de herramienta.
  - **Dedos:** un dedo mueve la página (y sigue deslizándose un poco si se
    empuja rápido); dos dedos la mueven y la amplían o reducen. Un toque es un
    clic. Dejar el dedo quieto medio segundo hace de ratón: arrastrar
    selecciona texto o mueve lo elegido, y levantarlo sin mover abre el menú
    del botón derecho.
  - **Dedo con una herramienta en la mano** (Ajustes → Lápiz y dedo):
    - *Automático* (de fábrica): el dedo usa la herramienta mientras no se
      haya usado nunca un lápiz en el programa. Desde la primera vez que se usa
      un lápiz, el dedo solo mueve la página.
    - *Dibuja y marca, como el lápiz*, o *Solo mueve la página*.
    - Si mientras un dedo dibuja se apoya un segundo dedo, ese trazo se
      descarta y los dos dedos mueven y amplían.
  - **La palma no pinta:** mientras el lápiz toca o está cerca de la pantalla,
    y durante 0,7 segundos después, lo que toque la pantalla se ignora hasta
    que se levante. Si un dedo estaba dibujando y llega el lápiz, manda el
    lápiz.
  - **Ajustes nuevos** (pestaña "Lápiz y dedo"): "Trazo más grueso al apretar
    más el lápiz" (activado) y qué hace el dedo.
  - Dos toques seguidos con el dedo o el lápiz son un doble clic (seleccionan
    la palabra, abren un texto).
  - Sin hacer: inclinación del lápiz. La fila de modos sigue midiendo 34
    puntos de alto (lo recomendado para el dedo son 40): se decide al probarla
    con el dedo.
- **2.12: mostrar y ocultar anotaciones (15/11/2026).**
  - Botón **"Ocultar anotaciones"** en el modo Estudiar (y en el menú Ver y en
    el buscador de funciones): enseña el documento limpio, sin subrayados,
    notas ni dibujos. El mismo botón los devuelve. **No se borra nada:**
    siguen en el documento y se guardan igual.
  - Se ocultan todas las anotaciones, también las hechas con otros programas.
    **Lo que es del propio documento se sigue viendo:** su texto, sus imágenes
    y los campos de formulario con lo que tengan escrito (y el dibujo de una
    firma).
  - Mientras están ocultas no se pueden elegir ni borrar (lo que no se ve no
    se toca). Si se anota algo nuevo, o se deshace o rehace un cambio, vuelven
    a verse solas, para no trabajar a ciegas.
  - Va por documento: ocultar en una pestaña no oculta en las demás. No se
    recuerda al cerrar: un documento siempre se abre con todo a la vista, para
    que nadie crea que ha perdido sus apuntes.
  - **Imprimir:** la ventana de imprimir tiene la casilla "Con las anotaciones
    (subrayados, notas y dibujos)". Viene marcada o no según cómo se esté
    viendo el documento, y se puede cambiar ahí mismo.
  - Las miniaturas del panel lateral siguen enseñando las anotaciones.
  - Pendiente: lo mismo al **exportar** páginas como imagen, cuando exista la
    exportación (Fase 5).
- **2.13: una tecla para cada herramienta (15/11/2026).**
  - Con el documento delante, una sola tecla coge cada herramienta: **R**
    resaltar, **S** subrayar, **T** tachar, **N** nota, **X** cuadro de texto
    (la T ya es de tachar), **D** dibujar, **F** formas, **B** borrador y
    **O** ocultar o mostrar las anotaciones. Es la inicial del nombre siempre
    que estaba libre.
  - Hacen lo mismo que su botón: con texto seleccionado, R, S y T lo marcan
    directamente; la misma tecla otra vez suelta la herramienta, igual que Esc.
  - Los **números 1 a 9** cogen las herramientas favoritas, en el orden de su
    barra.
  - Si se pulsan desde otro modo, se pasa a Estudiar para que se vea qué
    herramienta se lleva en la mano.
  - Solo valen cuando el teclado está en el documento: en el buscador o
    escribiendo una nota, una letra sigue siendo una letra.
  - La tecla de cada herramienta se dice en la ayuda que sale al dejar el ratón
    sobre su botón ("tecla R"), para no tener que aprenderse una lista.
  - **Ajuste nuevo** (Ajustes → General → Teclado): "Una tecla para cada
    herramienta", activado. Quien pulse teclas sin querer puede quitarlo.
  - Las teclas son fijas; elegir cada uno las suyas es la tarea P.4
    (decidido el 23/11/2026).
- **2.13a: escribir texto directamente sobre la página (15/11/2026).**
  Viene de la prueba de Julen: el cuadro de texto se escribía en un panel
  aparte, "como una nota", y no dejaba ajustar bien dónde, de qué tamaño ni
  con qué forma queda. Cambia la decisión de la 2.7 (escribir en un panel).
  - Con la herramienta de texto, un clic pone el cursor **en la propia
    página**: lo que se escribe se ve en su sitio, con su letra, su tamaño y su
    color, encima de lo que haya. La primera línea queda a la altura del clic.
  - **Intro** es otra línea. **Ctrl+Intro**, el botón "Hecho" o un clic fuera
    dejan el texto. **Esc** lo deja todo como estaba.
  - Un clic en otro sitio deja el texto y **empieza el siguiente ahí**: se
    anota a lo largo de la página sin volver a coger la herramienta.
  - **Siempre se puede volver a uno anterior:** con la herramienta en la mano,
    un clic sobre un texto ya puesto lo abre para seguir escribiendo o
    cambiarle el aspecto (sin la herramienta, doble clic o Intro).
  - Encima del texto hay una **barra pequeña**: letra más pequeña y más grande
    (A−, A+), **negrita** (N, o Ctrl+B), cuatro colores para escribir (negro,
    azul, rojo, verde) y, si el texto ya existía, "Borrar". El resto de colores
    y el tipo de letra siguen en la flecha del botón de la barra de arriba, y
    también cambian el texto que se está escribiendo.
  - Lo que se elige se recuerda: el siguiente texto sale igual, también otro
    día.
  - **Ancho a mano:** arrastrando el borde derecho del marco, el texto se
    estrecha o se ensancha y sus líneas se cortan solas. Doble clic en ese
    borde: vuelve al ancho de lo escrito. Sin tocarlo, el texto es tan ancho
    como su línea más larga y nunca se sale de la página.
  - Con un texto ya puesto y elegido (sin herramienta), además de las cuatro
    esquinas (que cambian el tamaño de la letra) hay **dos tiradores a los
    lados** que cambian el ancho sin tocar la letra. Doble clic, o Intro,
    vuelve a abrirlo para escribir.
  - **Negrita en PDF estándar:** se usa la variante negrita de las tres letras
    básicas (Helvetica, Times, Courier), que todos los lectores traen.
  - Dentro del PDF el texto se guarda tal como se escribió (sin los cortes de
    línea), y el ancho elegido y la negrita en dos datos propios del cuadro,
    para poder seguir cambiándolo después. Otros lectores lo ven igual.
  - Con la página girada (Ver → Girar) se sigue escribiendo en el panel de
    antes: es raro y así no hay que escribir de lado.
  - Las notas adhesivas no cambian: se escriben en su panel.
  - Sin probar en Adobe Reader ni con pantalla táctil real.
- **2.13b: flechas y símbolos dentro del texto (16/11/2026).**
  - En la barra del texto hay un botón **"→ ✓"** con 77 símbolos en grupos:
    flechas, marcas (✓ ✗ ★ ☐ ☑), puntos y figuras, números en círculo,
    matemáticas y letras griegas. Un clic lo escribe donde está el cursor.
  - **Tecleando sale la flecha:** `->` o `-->` da →, `<-` da ←, `<->` da ↔,
    `=>` da ⇒ y `<=>` da ⇔. Ctrl+Z justo después lo deja como se tecleó.
    **Ajuste nuevo** (Ajustes → General → Teclado), activado: "Al escribir
    un texto, -> se convierte en flecha".
  - **Dependencia nueva, aprobada por Julen el 15/11:** una letra libre. Las
    letras que todo lector de PDF trae (Helvetica, Times, Courier) no tienen
    flechas ni marcas. El programa lleva un archivo pequeño (10 KB) solo con
    esos símbolos, sacado de DejaVu Sans (licencia libre Bitstream Vera, con
    otro nombre como pide la licencia; aviso y licencia en "Acerca de"). La
    primera vez que se usa un símbolo en un documento, esa letra se guarda
    dentro del PDF (una sola vez), y así se ve en cualquier lector.
  - Se descartó dejar que el motor PDF eligiera la letra por su cuenta: metía
    varias letras enteras (casi 1 MB por documento), cambiaba el aspecto del
    texto con remates y perdía la negrita.
  - Las letras normales siguen con su letra de siempre; solo los símbolos
    usan la nueva. Dentro del PDF el texto es texto de verdad, con sus
    símbolos (otro lector lo puede copiar).
  - `packaging/make_symbol_font.py` rehace el archivo de la letra (solo hace
    falta si se añaden símbolos; usa fontTools, que el programa no lleva).
  - Las pruebas automáticas del programa empaquetado comprueban que la letra
    va dentro (`--check-symbols`).
  - De paso: Ctrl+Z dentro de un texto deshace lo tecleado (antes podía hacer
    falta pulsarlo dos veces).
  - Comprobado con el motor de Chrome. Sin probar en Adobe Reader.
- **2.13c: más formas y más cómodas (16/11/2026).**
  - **Formas nuevas** en el menú de Formas, cada una con su dibujito: flecha
    doble, flecha en codo (va en horizontal y luego baja o sube), triángulo,
    rombo y **llave** (arrastrando hacia la derecha sale "{", hacia la
    izquierda "}"; si es más ancha que alta, sale tumbada).
  - **Relleno claro** (casilla en el menú): recuadros, óvalos, triángulos y
    rombos se rellenan de un tono claro de su color, mezclado como un
    rotulador, así que el texto de debajo se sigue leyendo.
  - **Línea discontinua** (casilla en el menú), para cualquier forma.
  - **Mayús** mientras se suelta: líneas y flechas rectas (de 45 en 45
    grados), recuadros cuadrados y óvalos redondos.
  - **La forma recién dibujada queda elegida**, con sus tiradores, sin soltar
    la herramienta: se ajusta en el momento arrastrando un tirador, se mueve
    arrastrándola o se quita con Supr. Un arrastre en otro sitio empieza la
    siguiente.
  - Relleno y discontinua se recuerdan y van en las favoritas.
  - Todo es anotación PDF estándar (Line, PolyLine, Polygon, Square, Circle).
    Los polígonos guardan además qué forma son y entre qué dos puntos se
    dibujaron, para poder moverlos y cambiarlos de tamaño igual.
  - No hechas todavía: las marcas ✓ y ✗ como forma (ya se escriben como
    símbolo en el texto, en el tamaño y color que se quiera) y escribir texto
    dentro de un recuadro (de momento, texto encima del recuadro). Se
    retoman si se echan de menos.
  - Comprobado con el motor de Chrome. Sin probar en Adobe Reader.
- **2.13d: hoja en blanco, de rayas o cuadriculada (16/11/2026).**
  - Botón **Insertar hoja** (modo Estudiar): pone una hoja justo después de
    la página que se está leyendo, del mismo tamaño que ella, y la muestra.
    La flecha del botón ofrece **En blanco**, **De rayas** (renglones cada
    8 mm, como un cuaderno) y **Cuadriculada** (cuadros de 5 mm). Se recuerda
    la última elegida; por defecto, en blanco.
  - Las rayas y la cuadrícula son parte de la hoja (no anotaciones), en un
    azul claro que no estorba. Es una página PDF normal: cualquier lector la
    ve, y encima se puede escribir, dibujar y hacer formas como en cualquier
    otra.
  - Deshacer la quita y Rehacer la vuelve a poner; el diario la recupera tras
    un apagón. Miniaturas, número de páginas, búsqueda e índice siguen a las
    páginas movidas; las páginas ya dibujadas no parpadean.
  - Pendiente para la Fase 5 (Organizar): borrar o mover páginas sueltas.
    Una hoja añadida se quita, por ahora, con Deshacer.
  - Comprobado con el motor de Chrome. Sin probar en Adobe Reader.
- **2.13e: borrar anotaciones de otros programas (16/11/2026).**
  - Decidido por Julen: **solo borrar, con Deshacer**. Lo que otro programa
    puso (Edge, Adobe…) se puede elegir y quitar como lo propio: clic y
    Supr, el borrador, el botón derecho ("Borrar la anotación") o el botón
    Borrar de su nota. No se mueve, ni se cambia, ni se copia.
  - Vale para subrayados, resaltados, tachados, dibujos, líneas, recuadros,
    óvalos, notas, cuadros de texto, sellos, polígonos, ondulados e
    intercalados.
  - **Nunca se tocan** los campos de formulario, las firmas, los enlaces ni
    las zonas marcadas para tapar: no se ofrecen.
  - Una nota se va con su ventanita y con las respuestas que tenga.
  - Deshacer devuelve el mismo objeto, sin cambiar nada de él: se quita de
    la lista de anotaciones de la página y el objeto queda dentro del
    archivo. Sigue funcionando después de guardar.
  - Comprobado con anotaciones hechas por PyMuPDF imitando a otros
    programas. Sin probar con un PDF anotado de verdad en Edge o Adobe.

## Fase 2B – Documentos escaneados (OCR)
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.15 | Detectar páginas escaneadas y ofrecer "Reconocer texto" | Abro un temario escaneado y me lo ofrece sin molestar | ✅ |
| 2.16 | OCR en español en segundo plano (progreso, cancelar), enderezando la imagen, guardado como capa de texto estándar | Reconozco un tema escaneado, sigo leyendo mientras tanto, y luego busco en él también en Adobe | ✅ |
| 2.17 | Rehacer el OCR de PDFs que ya traen uno malo (todo o páginas) | Un PDF con OCR malo pasa a buscarse bien | ✅ |
| 2.18 | Buscador y subrayado probados con texto de OCR real; búsqueda aproximada opcional | Subrayo y busco en un escaneado igual que en un PDF del BOE | ✅ |
| 2.19 | Versión 0.3 | Estudio un tema escaneado con el programa | 🔶 Release v0.3.0 publicada (16/11/2026); falta usarla con un tema escaneado |
| 2.19a | Textos tras la prueba del 16/11: moverlos después de ponerlos, A+ a la izquierda y A− a la derecha, sin fondo blanco al cambiarlos | Encajo un texto entre líneas del temario, lo muevo a su sitio y no tapa nada | ✅ |
| 2.19b | Elegir cualquier cosa con un clic (también con una herramienta en la mano) y borrarla con Supr | Hago clic en un subrayado, un dibujo o un texto y Supr lo borra | ✅ |
| 2.19c | Cambiar el color de lo ya puesto (subrayados, dibujos, formas, textos, notas) | Cambio un resaltado amarillo a verde sin borrarlo y hacerlo otra vez | ✅ |
| 2.19d | Arreglos de la revisión de la Fase 2: páginas giradas, texto a medio escribir, "Cambios sin guardar" tras guardar, lo borrado sigue en el archivo | Subrayo bien en una página guardada de lado y no pierdo un texto a medio escribir al cerrar | ✅ |
| 2.19e | Resto de la revisión de la Fase 2: Deshacer lo de otros programas tras guardar, recuperar texto reconocido, OCR a salvo de un apagón, letras de otros idiomas y menores | Quito una nota de Adobe, se guarda sola y Deshacer la devuelve; tras un apagón a mitad del OCR no empieza de cero | ✅ |

Notas de la Fase 2B:
- **2.15: detectar escaneados y ofrecer "Reconocer texto" (16/11/2026).**
  - Al abrir un documento, el ayudante mira todas sus páginas cuando no tiene
    nada que dibujar (de 10 en 10, sin frenar el desplazamiento). Una página es
    "escaneada" si casi no tiene texto y una imagen cubre al menos la mitad.
  - Si hay alguna, sale una franja encima del documento, sin interrumpir:
    "Este documento está escaneado…" (o "N de las M páginas…"), con
    **Reconocer texto**, **Ahora no** (vuelve a salir al abrirlo otra vez) y
    **No preguntar más en este documento** (se recuerda).
  - Ajuste: "Ofrecer reconocer el texto al abrir un documento escaneado"
    (activado por defecto).
  - Por ahora el botón reconoce la página que se está viendo (lo de la Fase 0).
    El documento entero, en segundo plano y guardado en el PDF, es la 2.16.
- **2.16: reconocer el documento entero (16/11/2026).**
  - "Reconocer texto" (en la franja o en el modo Estudiar) lee todas las páginas
    escaneadas, una tras otra, en un proceso aparte. Se sigue leyendo y
    desplazándose con normalidad: dibujar las páginas va siempre primero.
  - La franja muestra "Reconociendo el texto: página X de N" con una barra y
    **Cancelar**. Cancelar conserva las páginas ya leídas.
  - Antes de leer cada página se endereza: se mide la inclinación de las líneas
    (hasta 10°) y se gira la imagen; una página del revés o de lado se pone
    derecha (se reconoce porque al leerla no salen palabras comunes del español).
    "Limpiar" la imagen se queda en pasarla a gris: Tesseract ya separa la
    letra del fondo por su cuenta y con eso lee bien el ejemplo con ruido.
  - Lo leído se escribe como texto invisible estándar encima de cada palabra
    (la página se ve igual), con Helvetica y las letras de Windows, que tienen
    todas las del español; una letra que no esté sale como "?". Las palabras
    van rectas, no inclinadas como el escaneo: algunos lectores parten las
    líneas inclinadas incluso a mitad de palabra.
  - Todo se escribe al final como un solo cambio: Deshacer lo quita entero, se
    guarda en el PDF al guardar y va al diario (no se pierde con un apagón).
  - Si mientras tanto se mete o se quita una hoja, el texto sigue yendo a su página.
  - Arregla los fallos M10 (capa de texto mal en páginas giradas, palabras
    estrechas, letras que faltaban) y B6 (un proceso por página, sin contraseña)
    de la revisión de la Fase 0: ahora un solo proceso, y las imágenes las da el
    ayudante, así que funciona con contraseña y con cambios sin guardar.
  - Comprobado aquí con PyMuPDF y con Poppler (el motor de otros lectores): las
    palabras se encuentran en su sitio. **Sin probar en Adobe ni en Edge.**
  - Velocidad medida aquí: unos 2 segundos por página escaneada a 150 ppp.
- **2.17: volver a reconocer el texto (16/11/2026).**
  - El ayudante distingue también las páginas escaneadas que ya tienen texto
    (una imagen con texto invisible encima, de este programa o de otro).
  - "Volver a reconocer texto" está en la flecha de **Reconocer texto** (modo
    Estudiar) y en el buscador de funciones. Pregunta qué páginas: todas las
    escaneadas, la que se está leyendo o las que se escriban ("3-5, 8"). Solo
    se aceptan páginas escaneadas: el texto propio de un documento no se toca.
  - Si el documento no tiene páginas sin texto pero sí escaneadas con texto,
    **Reconocer texto** hace directamente esa pregunta.
  - Antes de escribir el texto nuevo se quita todo el texto invisible de esas
    páginas, el bueno y el malo. El texto visible y las imágenes no se tocan;
    solo se perdería un texto visible que esté justo debajo de una palabra
    invisible, cosa rara en un escaneo.
  - Deshacer devuelve exactamente el texto de antes (la página guarda una nota
    de cómo estaba). Funciona también después de guardar y si se reconoce dos
    veces seguidas.
  - No avisa solo de que un OCR es malo: medirlo bien sin un diccionario no es
    fiable. Se pide con el botón cuando la búsqueda falla.
- **2.18: buscar y subrayar en escaneados (16/11/2026).**
  - Pruebas automáticas con texto de OCR real (reconocido por el programa a
    partir de páginas escaneadas): tildes, la ñ que no es una n, frases que
    saltan de línea, palabra completa, y el resaltado cae sobre la palabra de
    la imagen.
  - Casilla nueva en el buscador: **Aproximada, para escaneados**. Trata como
    iguales las letras que el OCR suele confundir (1, l, | y !; 0 y o; rn y m;
    cl y d; 5 y s; 8 y b), no distingue la ñ y no tiene en cuenta los espacios
    (un OCR malo los pone y los quita). Con ella se apagan "Palabra completa" y
    "Coincidencia exacta". Por defecto está apagada.
  - Cuando una búsqueda no encuentra nada en un documento escaneado, el
    buscador sugiere probar la búsqueda aproximada.

- **2.19a–c: arreglos tras la prueba de Julen (16/11/2026).** Antes de la
  Fase 2C, como se hizo con la 2.13a–e.
  - 2.19a: el texto abierto lleva un asa a su izquierda (cuatro flechas) para
    moverlo; con la herramienta Texto en la mano, arrastrar un texto ya puesto
    lo mueve y un clic lo abre. En la barra, A+ va a la izquierda y A− a la
    derecha. Al cambiar un texto ya puesto, la página se dibuja sin él (el
    PDF no cambia) y el marco queda transparente: no tapa el temario. En el
    PDF guardado un texto nunca ha tenido fondo.
  - 2.19b: con el bolígrafo o las formas en la mano, un toque (sin arrastrar)
    sobre algo ya dibujado o escrito lo elige en vez de dibujar un punto; se
    puede arrastrar y Supr lo borra. Un trazo sigue dibujando, y un toque en
    un sitio vacío hace lo de siempre. Con un rotulador (resaltar, subrayar,
    tachar) en la mano, un clic sobre una marca la elige; arrastrar sigue
    marcando texto. Antes solo se podía elegir con las manos vacías.
  - 2.19c: sobre lo elegido sale una barra pequeña con los diez colores
    rápidos, "Más…" (cualquier color) y "Borrar". Un color cambia el de un
    resaltado, subrayado, tachado, dibujo, forma, nota o texto sin moverlo;
    Deshacer devuelve el de antes. Lo de otros programas solo ofrece Borrar.
    La barra se aparta mientras se arrastra y vuelve al soltar.
  - 2.19d: arreglos de la revisión de la Fase 2
    (`revision-codigo-fase-2.md`, A1, A2, M1 y M2). Las letras de una página
    guardada de lado (`/Rotate`) se leen ya en la página tal como se ve, así
    que seleccionar, buscar y subrayar caen en su sitio (comprobado contra los
    píxeles de la página, a 0, 90, 180 y 270 grados y con la página
    recortada). Guardar, Guardar como, cerrar la pestaña o el programa e
    imprimir guardan antes el texto o la nota que se está escribiendo.
    Guardar cuenta también el cambio que aún iba de camino. Al guardar se
    deja fuera lo que ya nada usa, así que lo borrado desaparece de verdad
    del archivo. Por eso, lo de otros programas borrado y luego guardado ya
    no se puede deshacer: el aviso lo dice y remite a Versiones anteriores.
    Pendiente de decidir con Julen: apuntar en el diario, cada pocos
    segundos, el texto a medio escribir (por un apagón mientras se escribe).
    Decidido el 22/11/2026 (sí, cada 3 segundos): tarea 2.26b.
  - 2.19e: el resto de la revisión de la Fase 2 (M3, M4, B1 a B6 de
    `revision-codigo-fase-2.md`), hecho en el hilo de la revisión (22/11/2026):
    - **Lo de otros programas se puede deshacer también después de guardar**
      (preocupación de Julen: con "Guardar solo mientras trabajo" se guardaba
      sin querer y ya no había vuelta). Al quitar una anotación de otro
      programa, la orden se lleva una copia de sus objetos (la anotación, su
      ventana, las respuestas y su aspecto; `Foreign.prepared`, que hace el
      ayudante justo antes de quitarla). Deshacer la vuelve a escribir con sus
      mismos números. Si es enorme (más de 4 MB o 64 objetos, por ejemplo un
      adjunto grande), no se copia: entonces nunca se guarda sola y, al
      guardar a mano, sale siempre el aviso "No se podrá deshacer".
    - Recuperar tras un apagón el texto reconocido que ya estaba guardado no
      da error: cada página apunta qué texto lleva (`/LectorPDFOCRId`) y
      aplicarlo otra vez no hace nada.
    - **Reconocer texto a salvo de un apagón:** cada página leída se guarda
      aparte al momento (carpeta `reconocido`, junto al diario; nunca en el
      PDF), por la huella de su imagen. Si se va la luz a mitad, al volver a
      pulsar "Reconocer texto" las páginas ya leídas no se leen otra vez. Al
      terminar bien se borran; lo que quede de una vez que no terminó, a los
      7 días.
    - Si el ayudante se cae con un cambio de camino, la ventana lo da por no
      hecho (antes podía quedarse pintado sin estar en el documento).
    - La copia de "Versiones anteriores" la hace el ayudante, no la ventana:
      un PDF enorme ya no la deja parada al guardar. Mirar si un PDF está
      firmado ya no recorre todas las páginas (en uno de 3.000, al instante).
    - Restaurar una versión deja la pestaña en su sitio (antes iba al final).
    - Textos con símbolos y letras de otros idiomas («Łódź», «Ştefan»,
      «Ελλάδα»): esas letras van con la fuente de los símbolos, que ahora
      las lleva (28 KB). Antes salían como «?».
    - Diario: quitar lo hecho y deshecho se hace de una pasada (con OCR de
      cientos de páginas, recuperar no se queda pensando).
    - B5 (pruebas circulares con páginas giradas) ya lo resolvió la 2.19d.

## Fase 2C – Herramientas de estudio
Ordenadas por uso diario.

| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.20 | Panel de anotaciones filtrable por color | Veo todos mis subrayados de un color y salto a cada uno | ✅ |
| 2.21 | Saltar a artículo, apartado o sección por su número | Escribo "art. 14" o "3.2" en cualquier documento y me lleva allí | ✅ |
| 2.22 | Marcadores propios | Marco artículos clave y vuelvo a ellos con un clic | ✅ |
| 2.23 | Modo repaso | Lo subrayado se tapa y lo descubro al hacer clic | ✅ |
| 2.24 | Márgenes ampliables | Añado margen a una página y escribo en él; se ve igual en Edge y Adobe | ✅ |
| 2.25 | Insertar hojas en blanco, de rayas o cuadriculadas | Meto una hoja cuadriculada para un esquema | ✅ (hecha en la 2.13d) |
| 2.26 | Código de colores propio (opcional, nada predefinido) | Si quiero, pongo nombre a mis colores; si no, no aparece nada | ✅ |
| 2.26b | Lo que se está escribiendo, a salvo de un apagón (decidido por Julen el 22/11) | Corto la luz a mitad de una nota y al volver la recupero | ✅ |
| 2.27 | Exportar resumen (PDF o Word) | Saco un documento con todo lo subrayado, ordenado por página | ✅ |
| 2.28 | Vista de dos documentos lado a lado | Veo el tema y la ley a la vez | ✅ |
| 2.29 | Biblioteca del temario | Elijo mi carpeta de temas, busco en todos y veo mi progreso | ✅ |
| 2.30 | Enlaces entre documentos (ver `CLAUDE.md`) | Desde el tema 5, un clic abre la Constitución al lado en el artículo 14; si muevo el archivo, el programa lo encuentra o me deja corregirlo | ✅ |
| 2.31b | Arreglos de la revisión del código de la Fase 2C (todos los hallazgos) | Un enlace de otro programa a un archivo movido se corrige sin romperse | ✅ |
| 2.31 | Versión 0.4 | — | ✅ Release v0.4.0 publicada (22/11/2026) |

Notas de la Fase 2C:
- **2.20: panel de anotaciones (22/11/2026).**
  - Tercera pestaña del panel lateral (F4): **Anotaciones**, junto a
    Miniaturas e Índice. También con Ctrl+K → "Anotaciones" (modo Estudiar).
  - Lista todo lo puesto en el documento, en orden de lectura (página y de
    arriba abajo): resaltados, subrayados y tachados con las palabras que
    marcan, notas y textos con lo que dicen, dibujos y formas. También lo
    hecho con otros programas.
  - Arriba, un botón por cada color usado y "Todos"; debajo, qué ver: todo,
    subrayados y resaltados, notas y textos, o dibujos y formas.
  - Un clic lleva a su sitio y lo deja elegido, con su barra de color y
    Borrar. La lista se actualiza sola tras cada cambio.
  - El panel lateral es un poco más ancho (320 en vez de 222) para que quepan
    las tres pestañas; se puede estrechar arrastrando su borde.
  - Lo lee el ayudante de una vez (`core/annotation_list.py`); en un PDF de
    cientos de páginas solo se abren las que tienen anotaciones.
- **2.21: saltar a un artículo o apartado (22/11/2026).**
  - Se escribe en la casilla de la página (abajo, Ctrl+G) o con "Ir a
    artículo" (modo Estudiar, Ctrl+K). Un número solo sigue siendo una página.
  - Entiende "art. 14", "artículo 14 bis", "artículo único", "3.2" o
    "apartado 3", y "capítulo II" (o "2", o "segundo"), "título preliminar",
    "sección 1.ª", "disposición adicional primera" (o "DA 1"), "anexo",
    "tema 5", "libro", "parte"…
  - Busca el título al principio de una línea, que es donde están: "Artículo
    14." en el BOE, "3.2. Los derechos" en un temario. No se queda en el
    índice (líneas con puntos o con el número de página al final) ni en una
    frase que lo cita ("según el artículo 14"), salvo que no haya otra cosa.
  - Pone el título arriba de la pantalla. Escribir lo mismo otra vez lleva al
    siguiente con ese número (otra ley dentro del mismo documento) y, tras el
    último, vuelve al primero. Si no está, lo dice abajo.
  - Lo busca el ayudante, página a página, sin parar el dibujo
    (`core/places.py`). Necesita el texto del documento: en un escaneado,
    primero "Reconocer texto".
- **2.22: marcadores propios (22/11/2026).**
  - **Ctrl+M**, o el botón **Marcador** del modo Estudiar, guarda el sitio
    que se está leyendo (la parte de arriba de la pantalla). Se llama como el
    primer título que se ve ("Artículo 14.", "3.2 Los derechos…") o, si no
    hay ninguno, "Página N".
  - Salen los primeros en el **Índice** (F4), dentro de "Mis marcadores"; un
    clic vuelve al sitio exacto. Clic derecho (o F2 y Supr): cambiar nombre o
    quitar. Deshacer funciona como con todo.
  - Se guardan en el PDF como marcadores estándar, colgando de un apartado
    "Mis marcadores" al principio del índice del documento, que no se toca.
    Adobe y Edge los enseñan en su lista de marcadores. Una clave propia en
    cada uno (que los demás lectores no usan) permite cambiarlos después.
  - Se ordenan por su sitio en el documento, no por cuándo se pusieron.
- **2.23: modo repaso (22/11/2026).**
  - Botón **Modo repaso** del modo Estudiar (o Ctrl+K → "repaso"): todo lo
    resaltado y subrayado queda tapado con un bloque de su color. Un clic en
    un trozo lo destapa; otro clic lo vuelve a tapar. Esc o el mismo botón
    terminan, y al volver a empezar está todo tapado otra vez.
  - Lo tachado, las notas, los textos y los dibujos no se tapan.
  - No cambia nada del documento ni hace falta guardar: los bloques solo se
    pintan en la pantalla. Ocultar las anotaciones termina el repaso.
  - Posible mejora si Julen la echa en falta: repasar solo un color.
- **2.24: márgenes para apuntes (22/11/2026).**
  - Botón **Añadir margen** del modo Estudiar (o Ctrl+K → "margen"): dónde
    (a la derecha, a la izquierda, a los dos lados o abajo), cuánto
    (estrecho 3 cm, normal 5 cm o ancho 8 cm) y en qué páginas (la que se
    lee o todas). Recuerda la última elección; la primera vez, 5 cm a la
    derecha de esta página.
  - La página crece (se agrandan sus cajas estándar /MediaBox y /CropBox):
    el contenido no se mueve y el espacio nuevo queda en blanco. Notas,
    subrayados y enlaces siguen sobre su texto. En una página guardada de
    lado, "derecha" es la derecha tal como se ve.
  - Deshacer lo quita. Una página no puede pasar de 14 400 puntos (5 m), el
    máximo que aceptan los lectores.
  - Pendiente de comprobar en Edge y Adobe (prueba manual).
- **2.26: nombres propios para los colores (22/11/2026).**
  - No viene nada con nombre. Clic derecho sobre cualquier color (en el menú
    de colores de una herramienta, en la barra de lo elegido o en el panel de
    anotaciones) → **Ponerle nombre a este color…** ("Definiciones",
    "Plazos"…) o **Quitarle el nombre**.
  - El nombre sale al pasar el ratón ("Definiciones (amarillo)"), lo lee el
    lector de pantalla y aparece en cada fila del panel de anotaciones
    ("Pág. 3 · Resaltado · Definiciones").
  - Los nombres son de este ordenador (en los ajustes), valen para todos los
    documentos y no se guardan en el PDF: el PDF sigue siendo estándar.
- **2.26b: lo que se está escribiendo, a salvo de un apagón (22/11/2026).**
  - Mientras hay una nota o un texto abierto, cada 3 segundos se apunta en el
    diario cómo quedaría si se guardara ahora (solo si ha cambiado). Va en un
    archivo aparte del diario que se sustituye entero: nunca toca el PDF.
  - Tras un apagón, al abrir el programa se ofrece junto con el resto de
    cambios; recuperado, la nota o el texto aparecen puestos.
  - Al guardar la nota o cancelarla, ese apunte desaparece. Con "No guardar"
    se aparta con los demás cambios descartados.
- **2.27: exportar resumen (22/11/2026).**
  - Botón **Exportar resumen** del modo Estudiar (o Ctrl+K → "resumen"). Se
    elige dónde guardarlo y si es PDF o Word (.docx); recuerda el último
    formato. Propone "<tema> - resumen" junto al documento.
  - Dentro, página a página: lo resaltado (con su color de fondo), subrayado
    (subrayado y en su color) o tachado, las notas y los textos, cada uno con
    su tipo y el nombre propio de su color si lo tiene. Los dibujos no tienen
    palabras y no salen. Va todo el texto, sin cortar.
  - Incluye lo que se estaba escribiendo. No cambia el PDF. Al terminar se
    abre: el PDF en una pestaña, el Word con el programa del ordenador.
  - El .docx se escribe sin ninguna librería añadida; se ha comprobado que
    LibreOffice lo abre. Pendiente de abrirlo en Word (prueba manual).
- **2.28: dos documentos lado a lado (22/11/2026).**
  - Botón **Ver al lado** del modo Estudiar (o Ctrl+K → "lado", o clic
    derecho en una pestaña → "Ver al lado"). Con dos documentos abiertos pone
    el otro a la derecha; con más, pregunta cuál; con uno solo, pide abrir
    el segundo. La ventana se parte en dos mitades iguales (se puede mover la
    raya) y cada documento se ajusta a su mitad.
  - Cada documento sigue con su pestaña. Las herramientas, la barra de página
    y el zoom trabajan sobre la mitad en la que se hace clic; la de la derecha
    lo indica con su título en color ("Al lado: …").
  - La X de esa barra (o volver a pulsar el botón) deja de verlo al lado, sin
    cerrarlo. Cerrar uno de los dos vuelve a uno solo.
  - No se recuerda al cerrar el programa (las pestañas sí vuelven).
- **2.29: biblioteca del temario (22/11/2026).**
  - Botón **Biblioteca** del modo Estudiar (o Ctrl+K → "biblioteca"). La
    primera vez pide la carpeta del temario; se recuerda. Lista todos los PDF
    de la carpeta y sus subcarpetas, en orden natural ("Tema 2" antes que
    "Tema 10"). Doble clic abre el tema.
  - Progreso de cada tema: **leído** (hasta qué página se ha llegado, en %),
    **subrayados** (cuántos tiene guardados en el archivo) y **repasado**
    (cuándo se usó el modo repaso por última vez, o "Todavía no").
  - **Buscar en todos los temas** a la vez, con las reglas del buscador
    (tildes, ñ, palabras partidas…) y la opción "Palabra completa". Se ve el
    avance y se puede parar; doble clic en un resultado abre el tema en esa
    página con la búsqueda marcada.
  - Todo se lee en un proceso aparte, así que el programa no se queda
    parado. Como mucho 200 resultados por tema y 2000 temas por carpeta.
- **2.30: enlaces entre documentos (22/11/2026).**
  - **Crear:** selecciona unas palabras → clic derecho **"Enlazar a…"** (o el
    botón del modo Estudiar, o Ctrl+K → "enlazar"). También desde una nota
    (clic derecho → "Enlazar a otro documento…"). Se elige el documento entre
    los abiertos, los de la biblioteca u "Otro archivo…", y si se sabe, dónde
    ("art. 14", "3.2", o un número de página). El otro documento se abre al
    lado en ese sitio; se afina a mano y se pulsa **"Enlazar aquí"**.
  - Se guarda como enlace PDF estándar a otro archivo (GoToR) con la **ruta
    relativa** (p. ej. `../Leyes/Constitución.pdf`), la página y la altura.
    Las palabras enlazadas llevan una línea de puntos azul; al pasar el ratón
    dice a qué documento y página lleva. Se deshace con Ctrl+Z como todo.
  - **Abrir:** un clic en el enlace abre el otro documento **al lado**, en el
    sitio. Los enlaces a otros PDF hechos con otros programas también se abren.
  - **Archivo movido:** si no está donde dice el enlace, se busca por su
    nombre entre los abiertos y en la biblioteca; si aparece uno solo, se
    abre y se corrigen todos los enlaces a él (se puede deshacer). Si no,
    aviso **"Documento no encontrado"** con "¿Dónde está ahora?…" para
    elegirlo y corregir todos los enlaces de una vez.
  - Limitación: si el documento se guarda con "Guardar como" en otra carpeta,
    la ruta relativa ya no vale; al pulsar el enlace se busca como un archivo
    movido.

- **2.31b: arreglos de la revisión del código de la Fase 2C (22/11/2026).**
  Revisión completa en los archivos del proyecto (`revision-codigo-fase-2c.md`).
  - **A1:** corregir los enlaces a un archivo movido rompía los enlaces hechos
    con otros programas cuando su acción es un objeto aparte (pasaban a ir a
    «fitz: replace me!», y Deshacer no lo arreglaba). Ahora se cambia el
    archivo donde esté. Cada enlace corregido lleva una marca con el nombre
    del cambio (`/LectorPDFMended…`), y Deshacer solo vuelve atrás esos: los
    que ya iban al archivo nuevo se quedan como estaban.
  - **M1:** un margen en una página cuyas cajas (/MediaBox, /CropBox) vienen
    del árbol de páginas no se veía: ahora se leen de ahí.
  - **M2:** la altura de un enlace (/XYZ) se cuenta desde la parte de arriba
    de la página según sus cajas, no desde su alto: con un margen abajo, Adobe
    llevaba al sitio equivocado. En páginas guardadas de lado, solo la página.
  - **M3:** buscar los temas de la carpeta de la biblioteca mira como mucho
    50 000 archivos y carpetas (las más cercanas primero): una carpeta elegida
    por error (el disco entero) ya no deja el programa parado.
  - **B1:** la biblioteca actualiza cada tema sin recorrer la lista entera
    (con 2000 temas se notaba). **B2:** un tema que rompe el proceso que los
    lee se marca "No se puede abrir" y se sigue con los demás.
  - **B3:** el borrador del diario solo se escribe cuando cambia lo escrito
    (antes, cada 3 segundos aunque no cambiara). **B4:** una línea con solo
    "3.2" es un título, no una línea del índice. **B5:** el resumen puede
    sustituir a uno anterior abierto en una pestaña (se cierra y se vuelve a
    abrir); si esa pestaña tiene cambios sin guardar, no lo pisa.

## Fase 3 – Rellenar y firma manuscrita
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 3.1 | Rellenar formularios PDF | Relleno un formulario oficial y se ve bien en otros lectores | ✅ |
| 3.2 | Escribir en PDFs sin campos | Escribo mis datos encima de un documento escaneado | ✅ |
| 3.3 | Mis datos (nombre, DNI, dirección…) | Pongo mi DNI en un formulario con un clic | ✅ |
| 3.4 | Sellos y marcas rápidas (✓, ✗, fecha, sellos propios) | Marco casillas de un documento sin campos | ✅ |
| 3.5 | Crear y guardar firma e iniciales (dibujar, escribir, importar imagen sin fondo) | Tengo mi firma guardada | ✅ |
| 3.6 | Firmar con un clic: colocar, mover, redimensionar, fecha automática | Firmo un contrato en segundos | ✅ |
| 3.7 | Iniciales en todas las páginas | Con un clic pongo iniciales en todas las hojas | ✅ |
| 3.8 | Versión 0.5 | — | ✅ Release v0.5.0 publicada (22/11/2026) |
| 3.8b | Arreglos de la revisión del código de la Fase 3 (todos los hallazgos) | Lo escrito en una casilla se guarda al pulsar Guardar; «Mis datos» pone cada dato en su campo | ✅ |

Notas de la Fase 3:
- **3.1: rellenar formularios PDF (22/11/2026).**
  - Al abrir un formulario lo dice en la barra de abajo. Los campos se ven con
    un tono azul claro para saber dónde rellenar (`PdfView.highlight_fields`).
  - **Clic en un campo de texto:** se escribe encima, con letras de su tamaño.
    Intro lo guarda; **Tab** lo guarda y pasa al siguiente (Mayús+Tab, al
    anterior); Esc lo deja como estaba; un clic fuera también lo guarda. En
    los de varias líneas, Intro es salto de línea y Ctrl+Intro termina.
  - **Casillas** y **opciones redondas:** un clic las marca o desmarca.
    **Desplegables y listas:** un clic muestra las opciones ("Dejar en
    blanco" para vaciar un desplegable). Los desplegables que admiten texto
    propio se escriben, con sugerencias.
  - Solo con el teclado: **Rellenar campos** (modo Rellenar y firmar, o
    Ctrl+K) lleva al primer campo; Tab recorre todos y Espacio marca o
    despliega.
  - Los campos de solo lectura no se cambian (lo dice al pulsarlos).
  - Cada campo rellenado es una orden (`core/forms.py`, `FillField`): se
    deshace, va al diario y lo que se está escribiendo entra en el borrador
    del diario cada pocos segundos. Se guarda como formulario PDF estándar y
    el aspecto del campo se dibuja de nuevo, así que Adobe y Edge lo ven.
  - Fuera por ahora: campos de firma (Fase 4), botones, cálculos y
    JavaScript de los formularios.
- **3.2: escribir en PDFs sin campos (22/11/2026).**
  - El botón **Escribir** del modo Rellenar y firmar coge la misma herramienta
    de texto del modo Estudiar (se escribe sobre la página, en el sitio del
    clic, con su letra, tamaño y color, y se mueve después). Sirve igual en
    escaneados y en cualquier PDF sin campos. Se guarda como texto PDF estándar.
  - No hacía falta otra herramienta: tener dos "escribir" distintos
    confundiría. Si al probarlo con documentos reales falta algo (por ejemplo,
    que el texto se ajuste solo a la línea), se añade.
- **3.3: Mis datos (22/11/2026).**
  - Botón **Mis datos** (modo Rellenar y firmar). La primera vez pide los
    datos: nombre, apellidos, DNI/NIE, fecha de nacimiento, dirección, código
    postal, localidad, provincia, teléfono y correo. Se guardan solo en los
    ajustes de este ordenador (`mis_datos`); nunca se envían. Se cambian con
    "Editar mis datos…" (en ese menú o con Ctrl+K).
  - El botón abre un menú: **"Rellenar el formulario con mis datos (N
    campos)"** pone cada dato en los campos vacíos que lo piden, reconocidos
    por su nombre ("D.N.I.", "N.I.F./N.I.E.", "Domicilio", "C.P.", "Nombre y
    apellidos"…; `core/my_data.py`). Es un solo cambio: Ctrl+Z lo quita todo.
    En los desplegables elige la opción que coincide ("bizkaia" → "Bizkaia").
  - Cada dato del menú se puede poner suelto: en un PDF sin campos, se elige
    y se hace clic donde va (queda como texto). Con clic derecho en un campo,
    "Poner mis datos" ofrece cualquiera.
  - Los campos que ya tienen algo no se tocan.
- **3.4: Sellos y marcas rápidas (22/11/2026).**
  - Botón **Sellos** (modo Rellenar y firmar, también con Ctrl+K). Abre un
    menú: ✓ Marca, ✗ Cruz, ● Punto, Fecha de hoy, «Recibido» y los sellos
    propios. Se elige uno y se hace clic donde va; sigue en la mano para
    marcar más casillas, hasta Esc o volver a pulsar el botón.
  - Las marcas son trazos dibujados (tinta PDF estándar), no letras: se ven
    igual en cualquier lector, tenga las fuentes que tenga. La fecha
    (dd/mm/aaaa, en negro) y los sellos (rojo, negrita) son texto PDF estándar.
    Todo se mueve, borra y deshace como cualquier dibujo o texto.
  - "Nuevo sello…" guarda un sello con las palabras que se quiera (hasta 12,
    en los ajustes `sellos/propios`); "Quitar un sello" lo olvida.
    "Tamaño" elige entre cuatro (12 puntos por defecto, el de una casilla) y
    se recuerda.
- **3.5: Crear y guardar la firma y las iniciales (22/11/2026).**
  - El botón **Firmar** la primera vez abre "Mi firma"; desde entonces da un
    menú para cambiarla, crear o cambiar las iniciales y quitarlas (en la 3.6
    se añade ponerla en el documento). También "Mi firma e iniciales" con
    Ctrl+K.
  - Tres formas, en pestañas: **Dibujar** (ratón, dedo o lápiz; con lápiz el
    trazo es más grueso donde se aprieta), **Escribir** (el nombre de Mis
    datos con una letra manuscrita de las que trae Windows: Segoe Script, Ink
    Free, Lucida Handwriting…; las iniciales salen solas, "A. E. G.") y
    **Desde una imagen** (una foto o un escaneado de la firma en papel).
    Tinta negra o azul.
  - De la foto se quita el papel: el tono más común de la parte clara se
    vuelve transparente y la tinta conserva su color, con bordes suaves. Todo
    se recorta a la tinta (`core/my_signature.py`, sin dependencias nuevas).
  - Se guarda como imagen PNG con fondo transparente en la carpeta de datos
    del programa (`firma/firma.png`, `firma/iniciales.png`), solo en este
    ordenador. Quitarla pregunta antes; lo ya firmado no cambia.
- **3.6: Firmar con un clic (22/11/2026).**
  - **Firmar** → "Poner mi firma" (o "Poner mis iniciales") y un clic donde
    va. La primera vez, después de crear la firma, ya queda en la mano. Sale a
    140 puntos de ancho (las iniciales, 48), centrada en el clic y siempre
    dentro de la página. Esc o el botón otra vez la dejan sin ponerla.
  - Se mueve y se cambia de tamaño como cualquier dibujo (sin deformarse: el
    tamaño crece por igual a lo ancho y a lo alto), se copia, se borra y se
    deshace. En el panel de anotaciones sale como "Firma".
  - **Fecha automática**: debajo de la firma se escribe la fecha de hoy
    (dd/mm/aaaa), en el mismo cambio (Ctrl+Z quita las dos). Se puede quitar
    en el menú de Firmar ("Poner la fecha de hoy debajo de la firma"); se
    recuerda (`firma/fecha`). Las iniciales van sin fecha. La fecha es un
    texto normal: se mueve aparte.
  - Se guarda como anotación de imagen estándar (sello con imagen y fondo
    transparente; `core/pictures.py`), que ven todos los lectores. En páginas
    giradas la imagen se gira por dentro para que se vea derecha.
  - **Al guardar lo recién firmado** (Ctrl+S) pregunta una vez: "Guardar como
    «contrato-firmado.pdf»" (lo propuesto) o "Guardar en el mismo". Si el
    nombre ya acaba en "-firmado" no pregunta. El guardado automático (si se
    activó) no pregunta; el original queda en "Versiones anteriores".
  - Limitación: como toda anotación, se oculta con "Ocultar anotaciones" (y
    al imprimir sin anotaciones).
- **3.7: Iniciales en todas las páginas (22/11/2026).**
  - **Firmar → "Poner mis iniciales en todas las páginas"** (o Ctrl+K,
    "Iniciales en todas las páginas"). Si aún no hay iniciales, primero se
    crean. Un clic en la página donde van y se ponen en el mismo sitio de
    todas.
  - "El mismo sitio" es a la misma distancia de los bordes más cercanos: unas
    iniciales en la esquina de abajo a la derecha quedan en esa esquina
    también en una página apaisada o de otro tamaño. Nunca se salen de la
    página.
  - Es un solo cambio: Ctrl+Z las quita de todas. Cada una se puede mover o
    borrar después por separado.
- **3.8b: arreglos de la revisión del código de la Fase 3 (22/11/2026).**
  Revisión completa en los archivos del proyecto (`revision-codigo-fase-3.md`).
  - **A1:** lo que se está escribiendo en una casilla del formulario cuenta al
    guardar, cerrar, imprimir o actualizar (`finish_writing` también cierra la
    casilla). Antes, Ctrl+S decía "No hay cambios" y cerrar lo perdía.
  - **A2:** «Mis datos» aparta primero los campos de otra persona o de otra
    cosa (representante, empresa, padre, madre, cónyuge…, "lugar/provincia/país
    de nacimiento", "tipo de…") y deja "solicitante, interesado, titular…" para
    el final: "DNI del solicitante" es el DNI. "Primer apellido" y "Segundo
    apellido" se reparten los apellidos (con "de la", "del"… unidos al que
    sigue); "Apellidos y nombre" se escribe "García López, Ana".
  - **A3:** casillas con un mismo nombre y un valor cada una (Sí / No) son una
    sola respuesta: se marca solo la elegida y el valor se escribe como nombre
    PDF (`/No`), como las opciones redondas.
  - **M1:** en los desplegables con código y nombre (`[(28) (Madrid)]`) se ve y
    se elige el nombre; se escribe el código (lo que pide el estándar) y la
    casilla se dibuja con el nombre.
  - **M2:** al abrir un documento, el ayudante lee los campos de todas las
    páginas de una vez (`RenderService.want_fields`, solo páginas con
    anotaciones): «Mis datos», Tab y "Rellenar campos" llegan a todo el
    formulario, no solo a las páginas vistas.
  - **M3:** la propuesta de guardar como "-firmado" sale en cualquier
    guardado pedido (también "Guardar" al cerrar, "Guardar todos" y "Al cerrar:
    Guardar siempre"), no solo con Ctrl+S. Si se cancela la ventana de elegir
    archivo, se vuelve a preguntar. Deshacer la firma quita la pregunta
    (`signed_by_hand` mira si queda alguna firma puesta sin deshacer).
  - **M4:** una foto del móvil se gira según su nota EXIF antes de quitarle el
    fondo (`upright_picture`); antes salía de lado.
  - **B1:** iniciales en todas las páginas es una orden `AddPictures` que
    guarda la imagen una vez (antes, una vez por página: 2 MB en el diario con
    100 páginas). **B2:** si la fecha no cabe bajo la firma, va encima.
    **B3:** un sello se coloca entero dentro de la página. **B4:** los campos
    de contraseña enseñan puntos. **B5:** los campos ocultos no se leen ni se
    tiñen. **B6:** una lista con varias opciones elegidas no se cambia (PyMuPDF
    solo sabe escribir una): lo explica en lugar de perder las otras.
  - **B7 (forma de trabajar):** GitHub añade «Co-authored-by: Claude» al
    fusionar con *squash* cuando los commits de la rama los firma "Claude"; el
    robot "Sin firmas" no lo ve. Regla nueva en CLAUDE.md, sección 8.

## Fase 4 – Firma con certificado digital
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 4.1 | Firmar con certificado instalado en Windows (FNMT), partiendo de la prueba 0.8 | El PDF firmado sale válido en VALIDe y en Adobe | 🔶 hecho; falta tu prueba con el certificado FNMT real en VALIDe y Adobe |
| 4.2 | Firmar con archivo .p12/.pfx | Ídem | 🔶 hecho; falta tu prueba con tu copia .pfx del certificado FNMT |
| 4.3 | Firma visible o invisible; sello de tiempo opcional; recordar preferencias | Firmar es elegir dónde y poner el PIN | 🔶 hecho (PR 88); falta tu prueba en Adobe, Edge y VALIDe |
| 4.4 | Firmar varios documentos de una vez | Firmo 10 documentos poniendo el PIN una vez | 🔶 hecho (PR 89); falta tu prueba con el certificado FNMT (¿pide el PIN una vez?) |
| 4.5 | Firmar con DNIe y lector de tarjetas | Firmo con el DNIe (cuando tenga lector) | 🔶 hecho (PR 90); falta tu prueba con el DNIe y un lector |
| 4.6 | Ver y verificar firmas existentes | Abro un PDF firmado y me dice quién lo firmó y si es válido | 🔶 hecho (PR 91); falta tu prueba con PDFs firmados de verdad |
| 4.7 | Versión 0.6 | — | ✅ Release v0.6.0 publicada (23/11/2026) |
| 4.8 | Arreglos de la revisión del código de la Fase 4 | Todo lo de la revisión arreglado y probado | 🔶 hecho (pull request de la rama `claude/project-thread-bdtogg`); falta tu prueba (`docs/pruebas-pendientes.md`) |

Notas de la Fase 4:
- **4.1: Firmar con el certificado instalado en Windows (22/11/2026).**
  - Parte de la prueba 0.8 (el puente con Windows: la clave nunca sale de
    Windows y el PIN o la contraseña los pide Windows en su ventana).
  - **Se firma lo que se ve:** si el documento tiene cambios sin guardar,
    pregunta "Guardar y firmar" y firma después de guardar.
  - **Dónde va:** propone una copia «nombre-firmado.pdf», que se abre en una
    pestaña nueva. Si el documento ya es un «-firmado» (por ejemplo, después
    de firmarlo a mano), se firma en su sitio: la pestaña suelta el archivo un
    momento, se guarda cómo estaba en "Versiones anteriores" y vuelve a abrirse
    en la misma página. Si otro programa lo tiene abierto, no se toca y se avisa.
  - El certificado usado la última vez sale elegido la próxima
    (`firma/certificado`, solo la huella del certificado; nunca el PIN).
  - El aviso final dice quién firma ("firmado por …").
  - Comprobado aquí con certificados de prueba. **Falta la prueba de Julen con
    el certificado FNMT real** y la validación en VALIDe y Adobe.
- **4.2: Firmar con un archivo .p12 o .pfx (22/11/2026).**
  - Ya funcionaba desde la prueba 0.8 ("Usar un archivo .p12 o .pfx…" en la
    misma ventana). Ahora el programa recuerda **dónde está** el archivo
    (`firma/archivo`) y la próxima vez ofrece un botón «Usar «mio.pfx»»: solo
    hay que poner la contraseña, que nunca se guarda.
  - Un certificado caducado (o que aún no vale) o que no sirve para firmar se
    rechaza al abrirlo, con una explicación, en vez de hacer una firma que
    VALIDe daría por mala.
- **4.3: Firma visible o invisible y sello de tiempo (22/11/2026).**
  - **Por defecto, visible:** al pulsar "Firmar con certificado", un recuadro
    azul discontinuo sigue al ratón y un clic dice dónde va (Esc cancela).
    Luego, el certificado y el PIN. El recuadro (6 × 2 cm) lleva la firma
    manuscrita guardada a la izquierda, si la hay, y "Firmado digitalmente
    por", el nombre del certificado y la fecha. Es el aspecto estándar del
    campo de firma (se ve igual en otros lectores) y sale derecho en páginas
    giradas.
  - **Ajustes → Firma** (pestaña nueva): visible o invisible, firma manuscrita
    en el recuadro sí/no, sello de tiempo sí/no y su servidor.
  - **Sello de tiempo: apagado por defecto**, para que nada salga del
    ordenador sin pedirlo (principio 1). Solo se envía una huella del
    documento. Servidor por defecto: DigiCert (gratuito, Adobe confía en él);
    se puede cambiar por otro, por ejemplo uno español cualificado. Sin
    conexión, avisa y ofrece firmar sin sello.
  - Sin dependencias nuevas: el sello se pide con la biblioteca estándar de
    Python.
- **4.4: Firmar varios documentos de una vez (23/11/2026).**
  - "Archivo → Firmar varios documentos…" (y Ctrl+K "firmar varios"): una
    lista de documentos (añadir del ordenador o los que están abiertos), y
    dónde va la firma: visible en una esquina de la primera o la última
    página (por defecto, abajo a la derecha de la última), o invisible. Se
    recuerda lo elegido.
  - El certificado se elige **una vez**. Con un certificado de Windows la
    clave se abre una sola vez para todo el lote, así Windows o la tarjeta
    pueden pedir el PIN una sola vez (depende de cómo esté protegido el
    certificado: con algunos, Windows lo pide en cada firma). Con un archivo
    .pfx, la contraseña se pone una vez.
  - Cada documento se guarda como «nombre-firmado.pdf» en su carpeta; si ese
    nombre ya existe, «nombre-firmado (2).pdf». Los originales no se tocan.
  - Si uno no se puede firmar (contraseña, dañado), se dice al final y los
    demás siguen. "Parar" o cancelar el PIN para el lote. Si falla el sello de
    tiempo, pregunta una vez si seguir sin él.
  - Los documentos abiertos con cambios sin guardar se firman como están
    guardados, y la ventana lo avisa.
- **4.5: Firmar con el DNIe y otras tarjetas (23/11/2026).**
  - **Sin dependencias nuevas:** en Windows, con el controlador del DNIe
    instalado (Windows Update lo suele poner solo; si no, el de
    dnielectronico.es), los certificados de la tarjeta aparecen en el almacén
    de Windows al meterla en el lector, y Windows pide el PIN en su ventana.
    Así se usa el mismo camino de la 4.1, en vez de PKCS#11 (que habría
    necesitado otra biblioteca y el módulo del DNIe aparte).
  - El DNIe trae dos certificados: «(FIRMA)» y «(AUTENTICACIÓN)». Se elige
    solo el de FIRMA; el otro sale apagado con la explicación "es el de
    identificarse". Los dos llevan la marca "DNIe".
  - Botón **Actualizar** en la ventana del certificado, para volver a mirar
    después de meter la tarjeta. Si no hay ninguno, la ventana lo sugiere.
  - Plan B si el DNIe no aparece en Windows: PKCS#11 con pyHanko (se
    decidiría entonces, porque añade una dependencia).
- **4.6: Ver y comprobar las firmas de un PDF (23/11/2026).**
  - Al abrir un PDF firmado, la barra de abajo lo dice. "Rellenar y firmar →
    Comprobar firmas" muestra cada firma en palabras sencillas: ✔ "Firma
    válida", ⚠ "Firma correcta, pero no se reconoce quién emitió el
    certificado" o ✖ "Firma rota" / "Se ha cambiado después". Debajo: quién
    firmó, quién emitió el certificado, la fecha (y si lleva sello de tiempo)
    y qué se añadió después (otras firmas, campos rellenados, notas). Las
    firmas visibles tienen "Ir a la firma".
  - **Sin internet** (principio 1): se comprueba que lo firmado no ha
    cambiado y que el certificado viene de una autoridad en la que confía
    Windows (la FNMT y la del DNIe lo están). No se mira si el certificado
    se ha anulado; la ventana lo dice y remite a VALIDe para la comprobación
    oficial.

- **4.8: Revisión del código de la Fase 4 (23/11/2026).** Informe completo en
  la carpeta del proyecto (`revision-codigo-fase-4.md`). Arreglado:
  - **Un problema con la clave para el lote** (PIN equivocado, tarjeta fuera,
    tarjeta bloqueada): antes seguía con los demás documentos pidiendo el PIN
    otra vez, y el DNIe se bloquea tras tres PIN mal. Los avisos lo dicen en
    palabras (`windows_store.WrongPin`, `CardBlocked`, `NoCard`).
  - **PDF con permisos y con contraseña:** se firman con la contraseña con la
    que se abrieron (ninguna si solo tienen permisos) y siguen protegidos. Si
    el autor no permite rellenar ni firmar, no se firma (`NotAllowed`), como
    en Adobe. Al firmar varios, los abiertos usan su contraseña.
  - **Limitación conocida:** los PDF con contraseña de apertura protegidos por
    PyMuPDF (y otros programas que guardan la protección dentro del final del
    archivo) no se firman: el resultado no lo podría leer PyMuPDF. Resuelto en
    la tarea 5.7 para lo que escribe este programa: lo que protege o guarda
    con contraseña se puede firmar después (`protection.protection_apart`).
  - Firma visible bien colocada en páginas giradas y recortadas; un campo de
    texto «Firma1» ya no impide firmar; la ventana del PIN va sobre la ventana
    principal; mientras se firman varios, la ventana principal espera; no se
    firma encima de otra pestaña con cambios; Comprobar firmas acepta
    certificados con solo "firma digital" y usa las autoridades intermedias
    de Windows; la cadena de un .p12 se completa con las de Windows; Intro
    coloca la firma visible sin ratón; reloj de espera al firmar.
  - **Dos ideas aprobadas por Julen (23/11/2026), hechas en la misma tarea:**
    - **Firmar dentro del hueco de firma** que trae el documento («Firma del
      trabajador»…), como Adobe: al pulsar Firmar con certificado el hueco se
      resalta y un clic dentro firma en él, con su tamaño (Intro: en el hueco).
      Un clic fuera hace una firma nueva. No se crea un segundo campo.
      (`signing.empty_signature_fields`, `Visible.field`.)
    - **Guardar un PDF firmado añadiendo los cambios al final**, como Adobe:
      notas, subrayados, dibujos, sellos y campos rellenados ya no rompen las
      firmas, y no se avisa. Se sigue avisando (y entonces sí la rompen) con
      márgenes, hojas añadidas, texto reconocido y marcadores, también si se
      deshacen antes de guardar. Un PDF firmado nunca se guarda solo.
      Comprobar firmas distingue "se añadieron notas" de "cambiado" mirando
      las páginas (pyHanko es demasiado estricto con lo que escribe MuPDF).
      Lo borrado después de firmar sigue dentro del archivo, en la parte
      firmada (así funciona la firma; Adobe hace lo mismo). Un archivo
      reparado al abrirlo se reescribe entero. (`saving.keeps_signatures`,
      `PdfView.breaks_signatures`, `signature_check._looked_at_by_hand`.)

## Pruebas con Adobe (23/11/2026)
Julen quiere desinstalar Adobe Reader: antes se hacen de una vez todas las
pruebas que necesitan Adobe, con PDF de muestra creados con el propio código
del programa (anotaciones, formulario, enlace a otro PDF, hueco de firma,
PDF protegido). Resultados y fallos se apuntan aquí.
- **Arreglado:** un trazo hecho con presión del lápiz y sin transparencia
  guardaba en su aspecto la orden «/H gs» sin el estado gráfico «H» al que
  se refiere (MuPDF avisa «cannot find ExtGState resource 'H'»; Adobe puede
  marcarlo como error de la página). Ahora solo se nombra si existe
  (`drawing._draw_pressed`). Los PDF ya guardados se siguen viendo bien en
  este programa y en Edge.
- **Resultado (23/11/2026, hecho por Claude en el ordenador de Julen con la
  0.7.0):** todo bien. Firma FNMT válida en Adobe; firma en el hueco de un
  contrato (con clic y con Intro) sin campo nuevo; subrayar y guardar un PDF
  firmado no pregunta y la firma sigue válida («cambios permitidos»); un margen
  en un PDF firmado avisa; el PDF protegido firmado sigue sin dejar imprimir;
  firma invisible con sello de tiempo; firmar varios (3 de 3, sin pedir PIN,
  abajo a la derecha de la última página); anotaciones, colores, trazo con
  presión, formas, sellos, firma manuscrita, margen, hoja de rayas, marcador,
  capa de OCR y enlace a otro PDF se ven igual en Adobe; una nota hecha en
  Adobe se borra en el programa; el formulario relleno se ve y se edita en
  Adobe; texto griego y ruso (también en negrita) igual en Adobe; un PDF
  abierto a la vez en Adobe avisa al guardar y no se pierde nada.
- **También probado en el programa:** saltar a página y a artículo
  (`art. 14`, `disposición transitoria quinta`, `art. 900` dice que no está),
  buscar sin tildes con la vista girada, la ñ no es n, copiar texto,
  pestañas, modo lectura, Ctrl+K, imprimir (la ventana y sus avisos),
  «Buscar versiones nuevas», índice y miniaturas, marcador con Ctrl+M, modo
  repaso, ver al lado, exportar resumen, versiones anteriores, enlace que abre
  la ley al lado, zoom al 600 % nítido, cursor de lectura (F7), lista de
  teclas, y al cerrar y abrir vuelven las pestañas.
- **Detalles pequeños vistos, arreglados (23/11/2026, Julen dijo que sí):**
  - al deshacer todo hasta como estaba guardado ya vuelve a poner «Guardado»
    y al cerrar no pregunta (`PdfView` cuenta los pasos desde lo guardado);
  - el recuadro de la firma visible tiene fondo blanco y se lee bien aunque
    caiga sobre texto (`signing.appearance`);
  - el programa recuerda el tamaño y el sitio de la ventana, también si
    estaba maximizada (ajuste `ventana`).
- **Barra de herramientas que se desliza (23/11/2026, pedido por Julen):**
  cuando las herramientas de un modo no caben, ya no se esconden tras una
  flechita que abre una segunda fila: siguen en una sola fila que se desliza
  hacia los lados, con una flecha clara a cada lado (mantenerla pulsada sigue
  deslizando), la rueda del ratón y el dedo. Con Tab, la herramienta a la que
  se llega se pone a la vista (`app/ui/tool_strip.py`).
- **Documentos de pruebas:** las listas de las fases 0 a 4 y de las mejoras
  se juntan en `docs/pruebas-pendientes.md`, solo con lo que falta. La de la
  Fase 5 sigue aparte.
- **Sin probar (necesitan a Julen o algo que no hay):** lápiz y pantalla
  táctil, NVDA, DNIe y lector de tarjetas, poner PIN o contraseñas (.pfx, PDF
  con contraseña), cerrar a la fuerza con el Administrador de tareas, Edge,
  exportar a Word, imprimir en papel, casillas Sí/No en Adobe (no había
  formulario con ellas), crear Mis datos o la firma manuscrita (son datos de
  Julen) y biblioteca del temario.

## Mejoras pendientes de fases anteriores (antes de la Fase 5)
Decididas por Julen el 23/11/2026: se hacen todas, una tarea por pull request,
antes de empezar la Fase 5. Cada una se fija en cómo lo hacen los programas
conocidos (Adobe Reader, Edge, Chrome, Foxit, Word), copia lo bueno, mejora lo
malo y trae sus ajustes con valores por defecto que sirven sin tocar nada.

| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| P.1 | Letras de cualquier idioma europeo en los cuadros de texto (griego antiguo, cirílico, vietnamita, subíndices como H₂O), también en negrita, con la fuente metida en el PDF | Escribo «Ἀθῆναι, Москва, H₂O» en la página, guardo y se ve igual en Edge y Adobe | 🔶 hecho; falta tu prueba en Edge y Adobe |
| P.2 | "Dormir" las pestañas que llevan rato sin verse, como Edge, con un tope de memoria; ajuste para apagarlo | Con 20 temas abiertos el programa gasta mucho menos; al volver a una pestaña dormida aparece en su página en un momento | 🔶 hecho; falta tu prueba con muchos temas abiertos |
| P.3 | Zoom alto dibujado por trozos (solo lo que se ve), como Adobe y los mapas | Al 800 % una letra pequeña se ve nítida, sin esperas ni gastar cientos de MB | 🔶 hecho; falta tu prueba en tu Windows |
| P.4 | Elegir la tecla de cada herramienta y función, como los controles de un videojuego | En Ajustes → Teclado cambio la tecla de Subrayar, me avisa si choca con otra y "Restablecer" vuelve a las de siempre | 🔶 hecho; falta tu prueba |
| P.5 | El lector de pantalla (NVDA) lee el texto de las páginas, como en Adobe, Edge y Chrome | Con NVDA, entro en el documento y me lee la página; me muevo por líneas con las flechas | 🔶 hecho; falta tu prueba |

Lo que queda por probar en Windows está en
[`docs/pruebas-pendientes.md`](docs/pruebas-pendientes.md).

**Versión 0.7.0 (23/11/2026, decidido por Julen):** reúne los arreglos de la
revisión de la Fase 4 (tarea 4.8: firmar en el hueco, anotar un PDF firmado sin
romper la firma), las mejoras P.1–P.5 y el arreglo de los trazos con presión,
para probarlo todo en su ordenador antes de la Fase 5. Falta que Julen cree la
Release v0.7.0. (La Fase 5 será la 0.8.)

Notas de las mejoras:
- **P.1: Letras de cualquier idioma europeo en los cuadros de texto (23/11/2026).**
  - Antes ya iban el griego moderno, el polaco o el rumano. Faltaban el griego
    antiguo («Ἀθῆναι»), el cirílico («Москва»), el vietnamita, el armenio, el
    georgiano y signos como H₂O, x², ½, ₽ o №; y mezclar algunos daba «?».
  - Cómo lo hace Adobe: mete en el PDF la parte de la fuente que hace falta.
    Aquí, igual: la fuente de los símbolos (sacada de DejaVu Sans, libre) lleva
    ahora todas esas letras y tiene **negrita** (antes un texto en negrita con
    estas letras salía en normal). Ocupa unos 95 KB dentro de cada PDF que la
    usa (antes 20 KB); los PDF sin estas letras no cambian.
  - Un acento escrito aparte (algunos teclados y textos copiados traen «e» +
    «´») se une a su letra, así se encuentra en las fuentes y se busca bien.
  - Lo que no lleva: hebreo y árabe (se escriben de derecha a izquierda y unen
    sus letras) ni chino, japonés o coreano (miles de signos). Un texto con
    ellos se escribe como sabe el motor: se ve en este programa y en los que
    tengan esa fuente. Antes, junto a una flecha, salían como «?»; ya no. Si
    lleva una flecha, el PDF crece bastante (el motor mete la fuente entera).
  - Los PDF escritos con la fuente anterior siguen igual: sus textos guardan
    la suya y los nuevos llevan la nueva.
- **P.2: Dormir las pestañas que no se miran (23/11/2026).**
  - Como Edge: una pestaña que lleva un rato sin mirarse (15 minutos por
    defecto) para su proceso ayudante, que es lo que más memoria gasta (unos
    60 MB cada uno, más las páginas dibujadas). La pestaña sigue ahí, con su
    página, su zoom, su búsqueda, deshacer y los cambios sin guardar. Al
    volver a ella se despierta sola: enseña al momento las páginas que tenía
    en pantalla y en un instante las dibuja de nuevo.
  - Además, al pasar a otra pestaña la que se deja olvida enseguida las
    páginas dibujadas que no estaba enseñando (hasta 400 MB cada una). Así el
    tope de memoria de las páginas vale para lo que se ve, no para cada
    pestaña abierta.
  - Nunca se duerme la pestaña que se ve (ni las dos de la vista lado a lado),
    ni una que está guardando, buscando, imprimiendo o reconociendo texto.
  - Por dentro es lo mismo que cuando el ayudante se cae y se reinicia (lo que
    ya estaba probado): el nuevo abre el documento y repite los cambios sin
    guardar, sin avisar de nada.
  - **Ajustes → General → Memoria:** "Dormir las pestañas que no miro tras"
    5, 15 (por defecto), 30 minutos, 1 o 2 horas; se puede apagar. Edge deja
    2 horas por defecto, pero en un navegador cada pestaña es más ligera; aquí
    15 temas abiertos pasaban de 1 GB.
- **P.3: Zoom alto dibujado por trozos (23/11/2026).**
  - Antes, con mucho zoom se dibujaba la página entera a ese tamaño aunque se
    viera un trocito: una página A4 al 800 % eran unos 170 MB y tardaba.
  - Ahora, como Adobe Reader o un mapa: cuando la página pasaría de unos 12
    millones de puntos (un A4 a partir del 300-400 %), se dibuja entera solo
    en ligero (4 millones de puntos, se ve un poco borrosa) y encima, nítidos,
    solo los trozos de 1024 × 1024 puntos que se ven y uno más alrededor. Al
    moverse, solo se piden los trozos nuevos.
  - Los trozos guardados tienen su propio tope (160 MB); se olvidan primero los
    de otro zoom y los más lejos de lo que se ve.
  - Al subrayar o escribir con mucho zoom, el trozo viejo sigue en pantalla
    hasta que llega el nuevo: no parpadea.
  - Comprobado punto por punto: cada trozo es igual que la misma zona de la
    página dibujada entera (sin costuras ni desplazamientos), también con la
    vista girada y en páginas giradas.
- **P.4: Elegir la tecla de cada función (23/11/2026).**
  - Pestaña nueva **Ajustes → Teclado**, como los controles de un videojuego
    o el teclado de Visual Studio Code: la lista de **todas** las funciones
    (herramientas, Archivo, Editar, Ver, Ayuda y cada botón de cada modo),
    agrupadas, con su tecla y **otra tecla**. Doble clic (o "Cambiar
    tecla…") y se pulsa la nueva. Un buscador encuentra por nombre o por tecla
    ("subrayar", "ctrl+s"). Lo cambiado sale en cursiva; "Restablecer" vuelve
    a la de siempre de una función y "Restablecer todas", a todas.
  - Lo que mejora sobre otros: Adobe no deja cambiar teclas; Foxit sí, pero
    deja poner la misma tecla en dos funciones y entonces no va ninguna. Aquí,
    al pulsar una tecla, la ventana dice al momento si está libre o de quién
    es; si se pone, se le quita a la otra y lo dice ("Se ha quitado de
    «Resaltar»"). Nunca quedan dos funciones con la misma tecla.
  - Las teclas sin Ctrl ni Alt (una letra, un número) valen solo con el
    documento delante, como las de las herramientas: en el buscador una letra
    sigue siendo una letra. Las combinaciones (Ctrl+…, Alt+…, F1…F12) valen en
    toda la ventana. Las de moverse por el documento (flechas, Espacio, Av Pág,
    Inicio, Fin, Esc, Intro, Tab) no se pueden dar.
  - Funciones con tecla nueva por defecto: **Acercar Ctrl++** (también Ctrl+=)
    y **Alejar Ctrl+-**, como en Adobe y los navegadores; antes no tenían.
  - Se guarda solo lo que se cambia (`teclas` en los ajustes), así una versión
    nueva puede traer teclas nuevas sin pisar las de cada uno.
  - La casilla "Una tecla para cada herramienta" pasa a esta pestaña como
    "Teclas sueltas en el documento" (el mismo ajuste), junto con la de las
    flechas al escribir.
- **P.5: El lector de pantalla lee las páginas: el cursor de lectura (23/11/2026).**
  - Un lector de pantalla no puede leer el dibujo de una página: necesita las
    palabras. Adobe, Edge y Chrome se las dan como un texto. Aquí lo hace el
    **cursor de lectura** (`app/ui/page_reader.py`): un texto invisible sobre
    la página con el texto de esa página en orden de lectura (las líneas de
    un párrafo unidas, las palabras partidas con guion enteras, como al
    copiar; `app/core/reading.py`). NVDA lo lee como cualquier texto de
    Windows: línea a línea con las flechas, palabra a palabra con Ctrl,
    "leer todo" (NVDA+flecha abajo)…; al cambiar de página dice «Página 2 de
    39».
  - Es también el **"caret browsing" de Edge, Chrome y Firefox (F7)**, útil
    sin lector de pantalla: con las flechas se mueve una barra roja fina por
    el texto, con Mayús se selecciona (y la selección sale en la página, así
    que **R** la resalta, **S** la subraya, Ctrl+C la copia). Pasar de la
    última línea lleva a la página siguiente; Av Pág y Re Pág cambian de
    página. Un clic lo pone donde se pulsa. La página se desplaza sola a lo
    que se lee.
  - **Se activa solo cuando hay un lector de pantalla** (NVDA, JAWS,
    Narrador), también si se abre con el programa ya en marcha, y se
    recuerda si se activa con F7 (en Edge hay que activarlo a mano cada vez
    que se quiere; Adobe solo lo hace con lector de pantalla). Ajustes →
    General → Accesibilidad tiene las dos casillas; F7 se puede cambiar en
    Ajustes → Teclado (`reading_cursor`). Desactivarlo con F7 mientras hay un
    lector de pantalla también quita que vuelva solo.
  - Páginas escaneadas sin texto: dice «La página 3 no tiene texto: es una
    imagen» y propone Reconocer texto. Tras reconocerlo, se lee.
  - Por qué así y no "a mano": la pieza de Qt para dar texto a un lector de
    pantalla no está completa en PySide6 (faltan las partes que leen por
    palabras y líneas). Un texto de Qt de verdad, invisible, las trae todas
    hechas y probadas.

## Fase 5 – Organizar y convertir
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 5.1 | Reordenar, rotar, eliminar arrastrando miniaturas | Reorganizo un documento | ✅ |
| 5.2 | Unir y dividir PDFs, extraer páginas | Uno 3 PDFs en uno | ✅ |
| 5.3 | Insertar páginas de otro PDF o imágenes | Añado una imagen como página | ✅ |
| 5.4 | De foto a PDF (recortar, enderezar, mejorar) | Hago una foto a un papel y queda como escaneado | ✅ |
| 5.5 | Exportar páginas como imagen o el documento como texto | Saco una página en PNG | ✅ |
| 5.6 | Tapar datos de verdad | Tapo mi DNI y no se puede recuperar copiando el texto | ✅ |
| 5.7 | Comprimir, poner/quitar contraseña | El PDF ocupa menos / pide contraseña | ✅ |
| 5.8 | Comparar dos versiones de un documento | Veo qué ha cambiado entre dos versiones de una ley | ⬜ |
| 5.8b | Ayuda dentro del programa (F1), pedida por Julen el 24/11 | Busco «foto» en la ayuda, leo cómo se hace y «Hazlo ahora» me lleva a la función | ✅ |
| 5.9 | Versión 1.0 | — | ⬜ |

Notas de la Fase 5:
- **5.1 Ordenar, girar y eliminar páginas.** En las miniaturas (panel lateral):
  arrastrar una página o varias (Ctrl o Mayús para coger varias) a otro sitio;
  Alt+flechas las mueven desde el teclado; Supr las elimina; clic derecho:
  girar a la derecha / izquierda / 180°, mover al principio o al final,
  eliminar. En el modo Organizar, «Ordenar páginas» abre las miniaturas,
  «Rotar» gira las páginas cogidas (o la que se lee; la flecha ofrece las otras
  direcciones y «todas las páginas») y «Eliminar páginas» las quita.
  - Eliminar siempre pregunta (como Adobe) y nunca deja el documento sin
    páginas. Deshacer las recupera incluso después de guardar: la orden guarda
    antes una copia de las páginas, con lo escrito en ellas, sus campos (con su
    nombre), los enlaces a ellas y las entradas del índice que las señalaban.
  - Las tres órdenes (`core/page_orders.py`) dicen con `layout` dónde queda
    cada página; la vista mueve con ellas los dibujos ya hechos (sin parpadeo) y
    las miniaturas, la búsqueda y el OCR siguen los números nuevos
    (`pages_renumbered`). Girar, mover y eliminar invalidan las firmas con
    certificado (avisa al guardar).
- **5.2 Unir, dividir y extraer** (`core/combine.py`, `ui/organize_dialogs.py`).
  Siempre crean documentos nuevos; los originales no se tocan y nada queda a
  medias (se escribe aparte y luego se pone en su sitio).
  - **Unir**: lista con los documentos (añadir, los abiertos, subir/bajar,
    arrastrar). Cada uno queda como apartado del índice, con su propio índice
    dentro. Pide la contraseña de los protegidos. El resultado se abre.
  - **Dividir**: cada N páginas, por páginas («1-3, 4-10, 11-») o por los
    apartados principales del índice (si el índice tiene un solo título arriba,
    como una ley, los de dentro). Cada parte conserva su trozo del índice.
    Nombres «nombre - parte 1.pdf» o «nombre - 01 Título I.pdf»; nunca pisa
    archivos (añade « (2)»).
  - **Extraer páginas**: las elegidas en las miniaturas (clic derecho) o desde
    Ctrl+K, a un documento nuevo que se abre.
  - Con cambios sin guardar: «Guardar y seguir» (usan el archivo guardado).
- **5.3 Insertar páginas** (`page_orders.InsertPages`). Modo Organizar →
  «Insertar páginas» (o clic derecho en una miniatura → «Insertar páginas
  después…»): se eligen PDF e imágenes (varios a la vez) y dónde van (después
  de la página que se lee, al principio, al final o tras la página N). Cada
  imagen es una hoja A4 (tumbada si la foto es apaisada) con la foto entera.
  Pide la contraseña de los PDF protegidos. Deshacer las quita; invalidan las
  firmas con certificado (avisa al guardar).
- **5.4 De foto a PDF** (`core/photo_scan.py`, `ui/photo_scan_dialog.py`).
  Modo Organizar → «De foto a PDF» (o Ctrl+K «escanear»): se eligen fotos y
  cada una será una página de un PDF nuevo, que se abre (y, como cualquier
  escaneado, ofrece reconocer el texto).
  - **Encontrar la hoja**: la mancha clara más grande de la foto; sus
    esquinas, las puntas de la mancha. Si no sale (hoja clara en mesa clara),
    se pregunta al buscador de documentos de MuPDF, y si tampoco, la foto
    entera. Las esquinas se arrastran (ratón, dedo, lápiz) o se mueven con el
    teclado (Tab elige la esquina, flechas, Mayús más deprisa); nunca dejan
    que la hoja se doble.
  - **Enderezar**: MuPDF estira las cuatro esquinas a un rectángulo
    (`fz_warp_pixmap`). Si la forma se parece a un A4 (12 %), sale A4 exacto:
    vista de lado, una hoja parece más corta. Girar a izquierda/derecha. La
    foto se lee girada como dijo el móvil (EXIF).
  - **Aspecto** (se recuerda): *Documento* (recomendado: papel blanco sin
    sombras, letras oscuras, colores conservados), *Gris*, *Blanco y negro*
    (pequeño, como una fotocopia) y *Foto sin retocar*. Para quitar sombras se
    mide la luz del papel en una copia pequeña (lo más claro de cada zona,
    así no cuentan las letras) y se divide la foto entre ella; la división la
    hace MuPDF dibujando con el modo de mezcla «sobreexponer color», así que
    no hace falta ninguna librería de imagen nueva y tarda décimas.
  - Páginas de 595 puntos de ancho (A4); JPEG para color y gris, PNG para
    blanco y negro. Se escribe aparte y luego se pone en su sitio.
- **5.5 Exportar** (`core/export.py`, `ExportDialog` en
  `ui/organize_dialogs.py`). Modo Organizar → «Exportar»: las páginas como
  imagen (PNG nítida o JPG pequeña; 96, 150 o 300 ppp; con o sin las
  anotaciones) o el texto en un .txt (UTF-8, palabras partidas con guion
  unidas, «— Página N —» delante de cada página). Páginas: la que se lee, las
  elegidas en las miniaturas, todas o «1-3, 7». Una imagen se guarda donde se
  diga; varias, en una carpeta, «nombre - página 03.png». Nunca pisa archivos.
  Usa el archivo guardado (con cambios, «Guardar y seguir»). Avisa de las
  páginas sin texto (escaneadas sin reconocer). Recuerda lo elegido.
- **5.6 Tapar datos de verdad** (`core/redaction.py`). Modo Organizar →
  «Tapar datos»: se arrastra un recuadro sobre lo que se quiere tapar (queda
  en la mano para el siguiente; Esc lo deja). La flecha ofrece «Tapar el
  texto seleccionado» y «Buscar y tapar en todo el documento…» (un DNI, una
  cuenta: todas las veces que aparece, de una vez). Con texto seleccionado,
  el botón lo tapa directamente.
  - Se borra de verdad (redacción de MuPDF): las letras debajo (también las
    invisibles del OCR), la parte de las imágenes (pintada de negro), las
    líneas y formas cubiertas, y las notas, enlaces y campos que tocan la
    caja (pueden decir lo mismo). Queda una caja negra.
  - Deshacer lo recupera mientras el documento esté abierto: antes de tapar
    se guarda una copia de esas páginas (como al eliminar páginas).
  - La primera vez en cada documento explica qué hace y propone «Guardar
    como» para conservar el original (se puede quitar el aviso).
  - Un documento con algo tapado se escribe siempre entero, nunca «añadiendo
    al final» como uno firmado: la versión del principio seguiría teniendo
    lo tapado. La firma con certificado deja de valer (avisa al guardar).
  - Las «Versiones anteriores» del programa (en este ordenador) guardan cómo
    estaba antes de guardar, para poder volver.
- **5.7 Comprimir y contraseña** (`core/compress.py`, `core/protection.py`,
  `core/file_work.py`). Las dos crean una **copia** junto al documento («nombre
  (comprimido).pdf», «(con contraseña)», «(sin contraseña)»); el documento no
  cambia. Con cambios sin guardar, primero pregunta «Guardar y seguir». Se
  escriben en un proceso aparte, con «Cancelar», sin bloquear la ventana.
  - **Comprimir:** *Normal* (se escribe ordenado: fuera lo que no se usa, lo
    repetido una vez, todo empaquetado; se ve exactamente igual) o *Fuerte*
    (además, fotos y páginas escaneadas en color o gris de más de 200 ppp
    quedan a 150 ppp en JPEG, solo si ocupa menos; los escaneados en blanco y
    negro no se tocan, porque las letras se emborronarían). Dice el tamaño de
    antes y después; si apenas reduce (menos del 3 %), no crea la copia y lo
    dice. Recuerda el nivel elegido. Mantiene la contraseña si la tiene.
  - **Contraseña:** sin contraseña, pide la nueva dos veces (mínimo 4
    caracteres, «Mostrar lo que escribo»), avisa de que si se olvida nadie
    puede abrir la copia. Con contraseña: «Quitar la contraseña» o «Cambiarla
    por otra». AES-256, la del estándar que abren Adobe y los navegadores;
    quien la sabe puede hacer de todo (imprimir, copiar, rellenar, firmar).
    Un PDF que su autor protegió con permisos (se abre pero no deja imprimir o
    copiar) no se cambia: lo explica, como Adobe sin la contraseña de autor.
  - **Se puede firmar después:** PyMuPDF escribe la protección dentro del
    final del archivo y la librería de firma la necesita como objeto aparte.
    Al proteger, comprimir o guardar un PDF con contraseña se añade al final
    una pequeña parte con la misma protección como objeto
    (`protection_apart`): así lo protegido aquí se firma con certificado.
  - En un documento firmado, las dos avisan de que en la copia las firmas ya
    no valen.
- **Para seguir (24/11):** 5.1 a 5.7 terminadas. Falta 5.8 (Comparar dos
  versiones: texto añadido, quitado o cambiado, p. ej. una ley modificada) y
  5.9 (Versión 1.0). Desde ahora, una tarea por hilo (lo pidió Julen para
  gastar menos). Reglas que siguen valiendo: cada orden nueva que cambie
  páginas va en `_breaks_signatures` (`ui/pdf_view.py`); nunca
  `Document.select` (usar `page_orders._rearrange`); lo que escribe un PDF
  con contraseña pasa por `protection.protection_apart` para poder firmarse.
- **Arreglo pedido por Julen (23/11):** con un marcador o con «Texto» en la
  mano, un clic en tu propio texto lo coge (como en PowerPoint) y arrastrándolo
  se mueve; un segundo clic, doble clic o Intro lo abre para escribir.
- **Arreglos del tema 8 de Julen (23/11):**
  - Seleccionar cogía varias filas: la fuente Cambria de ese documento (hecho
    con Word) dice que sus letras miden unas cinco líneas. Las letras de una
    fuente con medidas absurdas se toman de la altura de su tamaño, como hace
    Adobe (`search.read_page_text`, `TALL_FONT`).
  - «Reconocer texto» no hacía nada: la última página es solo un logotipo
    grande (55 % de la hoja) y se tomaba por escaneada. Ahora una página es
    escaneada si la imagen cubre al menos el 75 % (`ocr.BIG_PICTURE`). Y si al
    reconocer no aparece ninguna letra, lo dice («No hay letras que
    reconocer…») en lugar de dar por reconocida la página.
  - Regla para el resto de la fase: cada orden nueva que cambie páginas se
    añade a `_breaks_signatures` (`ui/pdf_view.py`) y define `layout`.

- **5.8b Ayuda dentro del programa** (`ui/help_topics.py`, `ui/help_window.py`).
  Pedida y aprobada por Julen el 24/11/2026: «ni yo me acuerdo de todo lo que
  tiene», y de un programa propio no hay vídeos ni foros en internet. Se fija en
  la ayuda de Word y Adobe (buscar por lo que quieres hacer) y en los «consejos»
  de VS Code y Edge, sin internet.
  - **Ayuda (F1, botón «?» arriba a la derecha, Menú → Ayuda → Manual de
    ayuda…):** a la izquierda, «¿Qué quieres hacer?» y la lista de páginas por
    modo (Leer, Estudiar, Rellenar y firmar, Organizar), más «Guardar y no
    perder nada» y «Comodidad y ajustes». A la derecha, la página: en qué modo
    está, su tecla de ahora (cambia si se cambia en Ajustes → Teclado), «Cómo se
    hace» paso a paso y «Bueno saber». **«Hazlo ahora»** lleva a la función. No
    bloquea la ventana: se puede leer mientras se prueba.
  - Busca con las reglas del buscador (sin tildes ni mayúsculas, la ñ no es una
    n) en el título, la descripción, los pasos y palabras de la calle
    («juntar», «escanear», «apagón», «fosforito»).
  - **En Ctrl+K:** F1 sobre una función abre su página («F1 cómo se usa» en la
    línea de abajo). Si no encuentra ninguna función, «Buscarlo en la ayuda».
  - **Truco del día:** al abrir, una franja «¿Sabías que…?» (21 trucos, uno al
    día como mucho, sin repetir) con «Ver cómo se hace», «Otro truco», «No
    enseñar más trucos» y «Cerrar». Ajuste en General → Al abrir el programa
    (activado).
  - Hay una página por cada función (64) y 15 más para lo que no tiene botón
    (recuperar tras un apagón, versiones anteriores, pestañas, teclas, lápiz,
    lector de pantalla…). **Regla para lo que venga:** cada función nueva lleva
    su página en `help_topics.py`; una prueba falla si una función que ya
    funciona no tiene pasos. Las que aún no existen (Comparar, hasta la 5.8) dicen «Todavía no
    está disponible».
  - La tecla F1 se puede cambiar en Ajustes → Teclado («Manual de ayuda»).

## Fase 6 – Editar el texto original
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 6.1 | Corregir texto puntual | Cambio una palabra del documento y se ve natural | ⬜ |

## Ideas para más adelante
Versión para tableta o móvil · Mac/Linux.

- **Botón "Traducir" (idea de Julen, 16/11/2026).** Para PDFs en otros idiomas.
  Se piensa al final de todo el plan, no antes. Choca con dos principios: un
  traductor en línea saca el texto del ordenador ("Todo en local") y un modelo
  de traducción local es inteligencia artificial ("Sin IA"). Habría que decidir
  si se acepta alguna excepción.
