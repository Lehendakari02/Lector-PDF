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

La lista de lo que hay que probar en Windows al acabar la fase está en
[`docs/pruebas-fase-0.md`](docs/pruebas-fase-0.md).

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
| 1.13 | Aviso de nuevas versiones y **actualizar con un clic** (desactivable) | Si hay versión nueva en GitHub, me avisa; pulso "Actualizar ahora", se descarga, se instala y el programa se reinicia ya actualizado, sin perder ajustes ni pestañas (necesita el repositorio público) | ⬜ |
| 1.14 | Versión 0.1 (instalador y portátil) y repositorio público | Lo instalo, o lo abro sin instalar, y funciona todo lo anterior | ⬜ |

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
    Sigue pendiente dibujar por trozos para que el zoom alto sea ligero de verdad.
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

## Fase 2A – Anotar y guardado
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.1 | Botones Guardar / Guardar como junto a Imprimir, con escritura segura (archivo temporal y sustitución) | Ctrl+S guarda en el mismo archivo; "Guardar como" crea otro; si el archivo está bloqueado, avisa y no pierdo nada | ⬜ |
| 2.2 | Resaltar, subrayar, tachar | Selecciono texto y lo marco; tras guardar se ve igual en Edge o Adobe | ⬜ |
| 2.3 | Paleta de colores completa, grosor y opacidad | Elijo cualquier color para cada herramienta | ⬜ |
| 2.4 | Deshacer / rehacer (cada cambio es una "orden", ver `CLAUDE.md` §5) | Ctrl+Z y Ctrl+Y funcionan con todo | ⬜ |
| 2.5 | **Diario de recuperación** | Apago el ordenador a la fuerza mientras subrayo, lo enciendo y no he perdido nada | ⬜ |
| 2.6 | **Preguntar al cerrar** (Guardar / No guardar / Cancelar), "Volver a como estaba al abrirlo", recuperar cambios descartados, e indicador "Guardado / Cambios sin guardar" | Subrayo, cierro y me pregunta; si le doy a "No guardar" con prisa, aún puedo recuperarlo | ⬜ |
| 2.6b | **Versiones anteriores** y avisos que salen siempre (firmado, cambios fuertes, no se puede guardar, cambiado por otro programa) | Vuelvo a como estaba el PDF esta mañana; un PDF firmado nunca se guarda solo | ⬜ |
| 2.6c | **Ajustes de guardado**: qué hacer al cerrar (preguntar / guardar siempre), guardar solo mientras trabajo (desactivado por defecto), versiones y días que se conservan | Activo "guardar solo" y ya no me pregunta al cerrar | ⬜ |
| 2.7 | Notas adhesivas y cuadros de texto | Escribo notas y texto con la fuente, tamaño y color que quiero | ⬜ |
| 2.8 | Dibujo a mano alzada, flechas, formas, borrador | Dibujo y borro sobre la página | ⬜ |
| 2.9 | Seleccionar, mover, redimensionar, copiar y borrar anotaciones | Corrijo una anotación mal puesta sin rehacerla | ⬜ |
| 2.10 | Herramientas favoritas | Guardo "rotulador amarillo fino" y lo uso con un clic | ⬜ |
| 2.11 | Lápiz y pantalla táctil | Subrayo con lápiz en una tableta sin que la mano pinte | ⬜ |
| 2.12 | Mostrar/ocultar anotaciones (también al imprimir/exportar) | Con un botón veo el documento limpio | ⬜ |
| 2.13 | Atajos de teclado para cada herramienta | Cambio de herramienta sin usar el ratón | ⬜ |
| 2.14 | Versión 0.2 | Estudio un tema completo con el programa durante una sesión real | ⬜ |

## Fase 2B – Documentos escaneados (OCR)
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.15 | Detectar páginas escaneadas y ofrecer "Reconocer texto" | Abro un temario escaneado y me lo ofrece sin molestar | ⬜ |
| 2.16 | OCR en español en segundo plano (progreso, cancelar), enderezando la imagen, guardado como capa de texto estándar | Reconozco un tema escaneado, sigo leyendo mientras tanto, y luego busco en él también en Adobe | ⬜ |
| 2.17 | Rehacer el OCR de PDFs que ya traen uno malo (todo o páginas) | Un PDF con OCR malo pasa a buscarse bien | ⬜ |
| 2.18 | Buscador y subrayado probados con texto de OCR real; búsqueda aproximada opcional | Subrayo y busco en un escaneado igual que en un PDF del BOE | ⬜ |
| 2.19 | Versión 0.3 | Estudio un tema escaneado con el programa | ⬜ |

## Fase 2C – Herramientas de estudio
Ordenadas por uso diario.

| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.20 | Panel de anotaciones filtrable por color | Veo todos mis subrayados de un color y salto a cada uno | ⬜ |
| 2.21 | Saltar a artículo, apartado o sección por su número | Escribo "art. 14" o "3.2" en cualquier documento y me lleva allí | ⬜ |
| 2.22 | Marcadores propios | Marco artículos clave y vuelvo a ellos con un clic | ⬜ |
| 2.23 | Modo repaso | Lo subrayado se tapa y lo descubro al hacer clic | ⬜ |
| 2.24 | Márgenes ampliables | Añado margen a una página y escribo en él; se ve igual en Edge y Adobe | ⬜ |
| 2.25 | Insertar hojas en blanco, de rayas o cuadriculadas | Meto una hoja cuadriculada para un esquema | ⬜ |
| 2.26 | Código de colores propio (opcional, nada predefinido) | Si quiero, pongo nombre a mis colores; si no, no aparece nada | ⬜ |
| 2.27 | Exportar resumen (formato por decidir) | Saco un documento con todo lo subrayado, ordenado por página | ⬜ |
| 2.28 | Vista de dos documentos lado a lado | Veo el tema y la ley a la vez | ⬜ |
| 2.29 | Biblioteca del temario | Elijo mi carpeta de temas, busco en todos y veo mi progreso | ⬜ |
| 2.30 | Enlaces entre documentos (ver `CLAUDE.md`) | Desde el tema 5, un clic abre la Constitución al lado en el artículo 14; si muevo el archivo, el programa lo encuentra o me deja corregirlo | ⬜ |
| 2.31 | Versión 0.4 | — | ⬜ |

## Fase 3 – Rellenar y firma manuscrita
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 3.1 | Rellenar formularios PDF | Relleno un formulario oficial y se ve bien en otros lectores | ⬜ |
| 3.2 | Escribir en PDFs sin campos | Escribo mis datos encima de un documento escaneado | ⬜ |
| 3.3 | Mis datos (nombre, DNI, dirección…) | Pongo mi DNI en un formulario con un clic | ⬜ |
| 3.4 | Sellos y marcas rápidas (✓, ✗, fecha, sellos propios) | Marco casillas de un documento sin campos | ⬜ |
| 3.5 | Crear y guardar firma e iniciales (dibujar, escribir, importar imagen sin fondo) | Tengo mi firma guardada | ⬜ |
| 3.6 | Firmar con un clic: colocar, mover, redimensionar, fecha automática | Firmo un contrato en segundos | ⬜ |
| 3.7 | Iniciales en todas las páginas | Con un clic pongo iniciales en todas las hojas | ⬜ |
| 3.8 | Versión 0.5 | — | ⬜ |

## Fase 4 – Firma con certificado digital
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 4.1 | Firmar con certificado instalado en Windows (FNMT), partiendo de la prueba 0.8 | El PDF firmado sale válido en VALIDe y en Adobe | ⬜ |
| 4.2 | Firmar con archivo .p12/.pfx | Ídem | ⬜ |
| 4.3 | Firma visible o invisible; sello de tiempo opcional; recordar preferencias | Firmar es elegir dónde y poner el PIN | ⬜ |
| 4.4 | Firmar varios documentos de una vez | Firmo 10 documentos poniendo el PIN una vez | ⬜ |
| 4.5 | Firmar con DNIe y lector de tarjetas | Firmo con el DNIe (cuando tenga lector) | ⬜ |
| 4.6 | Ver y verificar firmas existentes | Abro un PDF firmado y me dice quién lo firmó y si es válido | ⬜ |
| 4.7 | Versión 0.6 | — | ⬜ |

## Fase 5 – Organizar y convertir
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 5.1 | Reordenar, rotar, eliminar arrastrando miniaturas | Reorganizo un documento | ⬜ |
| 5.2 | Unir y dividir PDFs, extraer páginas | Uno 3 PDFs en uno | ⬜ |
| 5.3 | Insertar páginas de otro PDF o imágenes | Añado una imagen como página | ⬜ |
| 5.4 | De foto a PDF (recortar, enderezar, mejorar) | Hago una foto a un papel y queda como escaneado | ⬜ |
| 5.5 | Exportar páginas como imagen o el documento como texto | Saco una página en PNG | ⬜ |
| 5.6 | Tapar datos de verdad | Tapo mi DNI y no se puede recuperar copiando el texto | ⬜ |
| 5.7 | Comprimir, poner/quitar contraseña | El PDF ocupa menos / pide contraseña | ⬜ |
| 5.8 | Comparar dos versiones de un documento | Veo qué ha cambiado entre dos versiones de una ley | ⬜ |
| 5.9 | Versión 1.0 | — | ⬜ |

## Fase 6 – Editar el texto original
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 6.1 | Corregir texto puntual | Cambio una palabra del documento y se ve natural | ⬜ |

## Ideas para más adelante
Versión para tableta o móvil · Mac/Linux.
