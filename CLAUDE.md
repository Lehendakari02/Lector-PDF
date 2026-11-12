# Instrucciones del proyecto: Lector-PDF

> Versión 0.6 (12/11/2026). Todas las decisiones principales están tomadas.
> Cambios de la 0.6: actualización con un clic ("Actualizar ahora" y se reinicia).
> Cambios de la 0.5: guardado y recuperación redefinidos, OCR como fase fija,
> pruebas de concepto en la Fase 0 y decisiones de la revisión del plan.

## 1. Qué es y para quién
Aplicación de escritorio gratuita y de código abierto para leer, estudiar, rellenar,
editar y firmar PDFs. Pensada para una persona normal, con sus propios documentos:
- **Estudiar** sobre PDFs (por ejemplo, temarios de oposición y textos del BOE):
  subrayar, anotar y repasar en el ordenador en lugar de con papel y boli.
  **Es la prioridad principal y debe ser lo mejor del programa.**
- **Rellenar** formularios y documentos.
- **Firmar** contratos y documentos laborales, de empresas y de la administración, con
  firma manuscrita y con **certificado digital con validez legal** (FNMT, DNIe).
- **Organizar** páginas: unir, dividir, reordenar, rotar, eliminar.

Es un lector de PDF que resuelve problemas, no un ecosistema: nada de cuentas,
tarjetas de estudio, estadísticas, inteligencia artificial ni servicios en línea.
Sin ánimo de lucro: se podrá compartir con familia, amigos o publicarse.

## 2. Principios (no negociables)
1. **Todo en local.** Ningún documento sale del ordenador. Sin cuentas, sin nube, sin
   telemetría. Solo dos excepciones, ambas desactivables: el sello de tiempo de la
   firma con certificado y la comprobación (y descarga, si se pide) de nuevas
   versiones en GitHub.
   Para informar de fallos hay un registro de errores local y un botón "Copiar
   informe de error" que el usuario pega donde quiera; nunca se envía nada solo.
2. **Sin muros de pago ni marcas de agua.**
3. **PDF estándar siempre.** Todo lo que se guarda (subrayados, notas, formularios,
   firmas, márgenes, hojas añadidas) usa el estándar PDF y se ve igual en Adobe Reader,
   navegadores y otros visores. Nunca un formato que solo entienda este programa.
4. **Guardar es sencillo y seguro:**
   - **Guardar** (Ctrl+S): guarda los cambios en el mismo archivo.
   - **Guardar como** (Ctrl+Mayús+S): crea una copia nueva.
   - El programa también guarda solo (ver sección 5), pero siempre se puede volver a
     una versión anterior, y pregunta antes de guardar cuando importa (PDF firmado,
     cambios fuertes).
5. **Nunca perder trabajo.** Imprescindible: un apagón, un cierre por error o un fallo
   del programa no pueden borrar horas de estudio. Ver sección 5.
6. **Completo pero ordenado.** Ver sección 4. Cada cosa en su sitio: nunca todo a la
   vista a la vez, pero nada escondido ni difícil de encontrar.
7. **Rápido**, incluso con PDFs de cientos de páginas.
8. **Sin IA.** No se incluyen funciones de inteligencia artificial.

## 3. Qué significa "editar" (decisión tomada)
Hay dos niveles de edición:
- **Nivel 1 – Trabajar sobre el documento** (Fases 2 a 5): subrayar, resaltar, notas,
  dibujar, escribir texto encima, rellenar, firmar, añadir márgenes y hojas. Se guarda
  en el mismo PDF y cualquier lector lo ve. El texto original no cambia, pero el
  archivo sí.
- **Nivel 2 – Cambiar el texto original** (Fase 6): corregir o sustituir palabras y
  frases del propio documento. Es técnicamente difícil (los PDF no están hechos para
  esto) y se hará al final, empezando por correcciones puntuales.

## 4. Interfaz: modos de trabajo
La interfaz no debe parecer la cabina de una nave espacial. Se organiza en **modos**,
y cada modo muestra solo sus herramientas:
- **Leer:** solo el documento y lo básico (buscar, zoom, índice). Por defecto.
- **Estudiar:** subrayar, colores, notas, dibujo, márgenes, hojas en blanco,
  marcadores, panel de anotaciones, modo repaso.
- **Rellenar y firmar:** campos, texto, datos guardados, sellos, firma manuscrita,
  firma con certificado.
- **Organizar:** páginas, unir, dividir, convertir, tapar datos, exportar.

Reglas:
- Cambiar de modo con un clic (pestañas arriba) o un atajo (Ctrl+1…4). El programa
  recuerda el último modo usado en cada documento.
- **Buscador de funciones** (Ctrl+K): escribes "firmar", "unir", "rotar"… y aparece la
  función, esté en el modo que esté. Así nada queda escondido.
- Accesibilidad: botones grandes y con nombre (no solo iconos), descripción al pasar el
  ratón, todo usable con teclado, tamaño de la interfaz ajustable, buen contraste en
  modo claro y oscuro.
- Preparada para pantallas táctiles y lápiz (tabletas, Surface): botones con tamaño
  suficiente para el dedo.

## 5. Guardado, recuperación y versiones (obligatorio desde la Fase 2)
Se copia lo bueno de otros programas (la autorrecuperación de Word, las versiones de
Google Docs y Apple) y se evita lo malo (preguntar en cada cierre, hasta que se
contesta "sí" sin leer).

1. **Diario de recuperación (al instante, invisible).** Archivo pequeño, aparte del
   PDF, en la carpeta de datos del programa. Cada cambio (subrayado, nota, texto,
   campo, página…) se apunta en el momento. Escritura segura: nunca queda a medias.
   Tras un apagón o un cierre inesperado, al abrir el programa ofrece recuperar los
   cambios de cada documento. Cuando el PDF se guarda bien, esa parte se vacía.
2. **Guardado automático en el PDF.** Activado por defecto:
   - tras un rato sin editar (30 segundos por defecto, ajustable o desactivable);
   - al cambiar de pestaña;
   - al cerrar la pestaña o el programa: la X es "guardar y cerrar".
   Nunca cada pocos segundos mientras se edita.
3. **Escritura segura del PDF.** Se escribe en un archivo temporal completo junto al
   original y luego se sustituye. Si falla (archivo bloqueado por otro programa,
   OneDrive/Dropbox sincronizando, sin permisos), no se pierde nada: los cambios
   siguen en el diario, se reintenta y se avisa.
4. **Versiones anteriores (red de seguridad).** La primera vez que se cambia un PDF
   en cada sesión se guarda una copia de cómo estaba. "Archivo → Versiones
   anteriores" permite ver y restaurar cualquiera (se conservan las últimas; número
   y espacio ajustables). Así, si se guardó algo que no se quería, se puede volver.
5. **Pregunta antes de guardar solo cuando importa:**
   - el PDF está firmado (guardar invalida la firma): nunca se guarda solo;
   - hay cambios fuertes: borrar páginas, tapar datos, cambiar el texto original;
   - el archivo no se puede guardar en su sitio (adjunto de correo en carpeta
     temporal, solo lectura): ofrece "Guardar como";
   - otro programa ha cambiado el archivo mientras estaba abierto.
6. **Ajuste opcional** "Preguntar siempre antes de guardar al cerrar", desactivado
   por defecto.
7. **Indicador visible:** siempre se ve el estado ("Guardado", "Guardando…",
   "Cambios sin guardar").
8. **Diseño interno:** cada cambio es una "orden" que sabe aplicarse, deshacerse y
   apuntarse en el diario. Deshacer/rehacer, diario y recuperación salen de esa misma
   pieza, no de tres sistemas separados.
9. **Pruebas obligatorias:** simular cierres a la fuerza a mitad de edición y a mitad
   de guardado, y comprobar que no se pierde nada ni se corrompe el PDF.

## 6. Funciones por fases
### Fase 1 – Lector
- Abrir PDF (menú, arrastrar y soltar, doble clic, "Abrir con…", programa predeterminado).
- **Pestañas** para tener varios PDFs abiertos; **al abrir el programa vuelven las
  pestañas de la última vez**, cada una en su página.
- Scroll continuo, miniaturas, ir a página, índice del documento.
- Zoom, ajustar a ancho/página, rotar, pantalla completa.
- **Buscador excelente:**
  - No distingue tildes ni mayúsculas: "articulo" encuentra "Artículo"; "camion",
    "CAMIÓN". **La ñ no es una n**: "año" no encuentra "ano".
  - Encuentra palabras partidas con guion al final de línea y frases que saltan de
    línea (muy habitual en el BOE).
  - Lista de resultados con la frase alrededor; resaltado de todos en la página;
    siguiente/anterior con Intro y Mayús+Intro.
  - Opciones para palabra completa o coincidencia exacta.
- Seleccionar y copiar texto.
- Modo oscuro y modo lectura (tono sepia/cálido para leer muchas horas).
- Archivos recientes. Imprimir.
- **Instalador** y **versión portátil** (funciona sin instalar, por ejemplo en el
  ordenador del trabajo). La versión portátil guarda ajustes, diario y versiones
  junto al programa (carpeta `datos`), nunca en `%APPDATA%`. Formato: una carpeta
  en `.zip`, porque abre en menos de 1 segundo y un único `.exe` tarda casi 3.
- Páginas nítidas en pantallas con escala 125 %/150 %.
- **Aviso de nuevas versiones y actualización con un clic** (consulta GitHub
  Releases; desactivable). Al abrir, si hay versión nueva, avisa sin molestar y
  ofrece "Actualizar ahora": descarga la versión nueva, comprueba que la descarga
  está completa y es la publicada, la instala y reinicia el programa, que vuelve
  con las mismas pestañas. Nunca se actualiza sin que el usuario lo pida, y antes
  guarda lo pendiente. Funciona en la versión instalada y en la portátil (que
  conserva su carpeta `datos`). Si algo falla, sigue funcionando la versión que
  había. Requiere que el repositorio sea público: se hará público al publicar la
  versión 0.1.

### Fase 2 – Estudiar y anotar (prioridad principal)
Básico:
- Resaltar, subrayar y tachar texto seleccionándolo.
- **Todos los colores**: paleta rápida + selector de cualquier color, para subrayados,
  texto, notas, dibujos y formas. Grosor y opacidad ajustables.
- **Herramientas favoritas**: guardar combinaciones (p. ej. "rotulador amarillo fino",
  "bolígrafo rojo") en una barra rápida.
- Notas adhesivas, cuadros de texto (fuente, tamaño y color elegibles), flechas y
  formas, dibujo a mano alzada, borrador.
- **Lápiz y pantalla táctil**: presión del lápiz, ignorar la palma de la mano, el botón
  del lápiz borra, gestos de zoom y desplazamiento con los dedos.
- Seleccionar, mover, cambiar tamaño, copiar y borrar anotaciones fácilmente.
- Deshacer/rehacer ilimitado. Atajos de teclado para cada herramienta.
- **Mostrar/ocultar anotaciones** con un botón: ver el documento limpio o con todo lo
  propio. También al imprimir o exportar.

Para estudiar mejor:
- **Márgenes ampliables**: añadir espacio en blanco a los lados (o abajo) de una página
  o de todas, para escribir apuntes. Se guarda como PDF estándar.
- **Insertar hojas** en blanco, de rayas o cuadriculadas entre páginas, para esquemas.
- **Código de colores propio (opcional)**: no viene nada predefinido. Cada persona
  puede, si quiere, ponerle nombre a sus colores; si no, son simplemente colores.
- **Panel de anotaciones**: lista de todos los subrayados y notas del documento,
  filtrable por color, para saltar a cada uno.
- **Exportar resumen**: sacar todo lo subrayado y anotado a un documento de resumen.
- **Marcadores propios** para marcar artículos o páginas clave.
- **Saltar a un artículo, apartado o sección** escribiendo su número, en cualquier
  documento (leyes del BOE, temarios, contratos…).
- **Modo repaso**: tapar lo subrayado para intentar recordarlo; se destapa con un clic.
  Sin algoritmos ni programación de repasos.
- **Vista de dos documentos** lado a lado (p. ej. tema y ley).
- **Biblioteca del temario**: carpeta con todos los temas, búsqueda en todos a la vez
  (con las mismas reglas del buscador) y progreso por tema (leído / subrayado / repasado).
- **Enlaces entre documentos**: desde un texto o una nota, un enlace que abre otro
  PDF en el sitio exacto (p. ej. desde el tema 5, el artículo 14 de la Constitución).
  - Crear: seleccionar texto → clic derecho "Enlazar a…" → elegir documento (pestañas
    abiertas o biblioteca) → elegir destino escribiendo "art. 14" o yendo a la página
    y pulsando "Enlazar aquí".
  - Abrir: clic en el enlace → el destino se abre al lado (vista de dos documentos).
  - Se guarda como enlace PDF estándar a otro archivo (GoToR) con **ruta relativa**,
    para que funcione en cualquier ordenador con la misma estructura de carpetas.
  - Si el archivo se ha movido o renombrado: buscarlo en la biblioteca; si no aparece,
    preguntar "¿dónde está ahora?" y corregir de una vez todos los enlaces a él.
  - Si no existe (p. ej. el PDF se ha compartido sin el destino): aviso "documento no
    encontrado"; el subrayado y las notas se siguen viendo.
  - Limitación asumida: Adobe respeta estos enlaces; los navegadores (Edge, Chrome)
    suelen bloquearlos. El PDF sigue siendo válido en todos.
### Fase 2B – Documentos escaneados, OCR (fase fija, entre anotar y estudiar)
Muchos temarios son escaneados o traen un OCR de mala calidad. Todo lo de estudiar
(buscar, subrayar, saltar a artículo, modo repaso, resumen) depende del texto, así
que el OCR es una pieza central y se hace antes de las herramientas de estudio.
- Detectar páginas sin texto (escaneadas) y ofrecer "Reconocer texto" sin molestar.
- OCR en español (Tesseract, libre) que añade una capa de texto invisible: el PDF
  se ve igual y se guarda como PDF estándar (se puede buscar también en Adobe).
- En segundo plano, con progreso, cancelable, sin bloquear la lectura.
- Enderezar y limpiar la imagen antes de reconocer, para mejorar el resultado.
- Rehacer el OCR de PDFs que ya traen uno malo (todo o páginas concretas).
- El buscador y el subrayado se prueban con texto de OCR real, no solo con PDFs
  "limpios"; opción de búsqueda aproximada para fallos típicos (1/l, 0/O, rn/m).

### Fase 3 – Rellenar y firma manuscrita
- Rellenar formularios PDF (campos, casillas, desplegables) y escribir en PDFs sin campos.
- **Mis datos**: guardar nombre, DNI, dirección, teléfono, correo… (solo en el ordenador)
  y ponerlos en un formulario con un clic.
- **Sellos y marcas rápidas**: ✓, ✗, ●, fecha de hoy, "Recibido", sellos propios.
- **Firma guardada**: crear la firma una vez (dibujando, escribiendo el nombre o
  importando una imagen, quitando el fondo) y guardar también las iniciales.
- **Firmar con un clic**: se coloca la firma guardada; mover y redimensionar.
- Fecha automática junto a la firma; iniciales en todas las páginas con un clic.

### Fase 4 – Firma con certificado digital (validez legal)
- Firmar con el certificado instalado en Windows (p. ej. FNMT), con archivo .p12/.pfx
  y con DNIe o tarjeta (lector de tarjetas).
- Recordar el certificado y el aspecto de firma preferidos: firmar es elegir dónde y
  poner el PIN o la contraseña (que nunca se guarda).
- Formato PAdES (el estándar europeo/español), con sello de tiempo opcional.
- Firma visible (recuadro con nombre, fecha y la firma manuscrita si se quiere) o invisible.
- **Firmar varios documentos de una vez** (misma posición o firma invisible), pidiendo
  el PIN una sola vez si el certificado lo permite.
- Ver y comprobar las firmas que ya tiene un PDF.
- Prueba de validez: los PDFs firmados deben validarse en VALIDe (Gobierno de España)
  y en Adobe Reader.
- Riesgo conocido: pyHanko no usa directamente el almacén de certificados de Windows
  (donde suele estar el certificado FNMT). Hace falta un puente propio con Windows.
  Se comprueba con una prueba de concepto en la Fase 0; plan B si no sale: usar el
  `.p12` exportado o apoyarse en AutoFirma.

### Fase 5 – Organizar y convertir
- Unir, dividir, reordenar (arrastrando miniaturas), rotar, eliminar, extraer páginas.
- Insertar páginas de otro PDF o imágenes.
- **De foto a PDF**: convertir fotos de documentos en un PDF recortado, enderezado y
  legible (estilo escáner).
- **Exportar** páginas como imagen (PNG/JPG) o el documento como texto.
- **Tapar datos de verdad** (opcional, solo cuando se use): borrar definitivamente
  texto e imágenes de una zona (DNI, cuenta bancaria…) antes de enviar, de forma que
  no se pueda recuperar.
- Comprimir, poner/quitar contraseña.
- **Comparar dos versiones** de un documento: muestra qué texto se ha añadido, quitado
  o cambiado (p. ej. cuando se modifica una ley del temario).

### Fase 6 – Editar el texto original
- Corregir o sustituir texto del documento, empezando por cambios puntuales.

### Ideas para más adelante
- Versión para tableta o móvil (por eso la lógica PDF va separada de la interfaz).
- Mac/Linux si sale fácil.

### Descartado
Inteligencia artificial, leer en voz alta, tarjetas de estudio/Anki, repaso espaciado,
estadísticas y temporizador, descarga de leyes del BOE, mediciones y planos, funciones
de empresa o colaboración en línea.

## 7. Tecnología
- **Windows** es el objetivo principal. Se elige tecnología que también funcione en
  Mac/Linux sin esfuerzo extra, pero solo se prueba y publica para Windows.
- **Python + PySide6 (Qt)**: interfaz de escritorio (con soporte de lápiz y táctil).
- **PyMuPDF**: mostrar, buscar, anotar, rellenar, organizar, tapar datos, exportar.
  Se usa la versión 2. Trae consigo componentes de inteligencia artificial (análisis
  de páginas con modelos) que el programa no usa: no se cargan ni se incluyen en el
  `.exe`. Usarlos algún día sería una decisión aparte (principio "Sin IA").
- **pyHanko**: firma con certificado (PAdES, sellos de tiempo, DNIe por PKCS#11).
- Instalador `.exe` y versión portátil generados automáticamente en GitHub (GitHub
  Actions) y publicados en "Releases".
  Se crean con PyInstaller (empaquetado) e Inno Setup (instalador, sin pedir permisos
  de administrador). Para publicar una versión: poner el número en `app/__init__.py`
  y crear en GitHub una *Release* con la etiqueta `v` + ese número (p. ej. `v0.1.0`).
- Licencia: **AGPL-3.0** (software libre, obligatoria por usar PyMuPDF; compatible con
  compartirlo gratis o hacerlo público).
- **Tesseract** (Apache 2.0) con el idioma español, incluido en el instalador: OCR.
  Se usa el Tesseract que ya trae PyMuPDF dentro; solo se añade el archivo del idioma
  (`app/recursos/tessdata/spa.traineddata`, 2 MB).
- La lógica PDF (`core/`) no depende de la interfaz (`ui/`), para poder probarla sola
  y, en el futuro, reutilizarla en otra versión.
- Renderizado de páginas en segundo plano (sin bloquear la interfaz) y por partes,
  para que los PDFs enormes vayan fluidos. Las páginas se dibujan en un **proceso
  ayudante** aparte (`core/render_service.py`), no en un hilo: PyMuPDF para el resto
  de Python mientras dibuja (medido en la tarea 0.6). El ayudante abre su propia
  copia del documento, así que cuando haya cambios (anotaciones, Fase 2) hay que
  hacérselos llegar.
- Repositorio privado hasta la versión 0.1; después, público (aviso de versiones,
  descargas para cualquiera, minutos de GitHub Actions ilimitados y opción de firma
  de código gratuita para proyectos libres con SignPath).

### Letra pequeña del "PDF estándar"
- Cuadros de texto: otros lectores solo garantizan unas pocas fuentes básicas; con
  otras fuentes hay que incluir el aspecto dibujado para que se vean igual.
- Trazos con presión del lápiz: el trazo estándar tiene un solo grosor; el grosor
  variable se guarda como aspecto dibujado (Adobe y Edge lo respetan).
- Márgenes ampliables y hojas añadidas cambian la geometría: cuidar que anotaciones
  y enlaces no se muevan.
- Por eso las pruebas de cada función que guarda algo incluyen abrir el resultado en
  Edge y en Adobe y comparar.

## 8. Forma de trabajar
- El usuario no programa: dirige, prueba y decide. Claude programa todo.
- Explicar los avances en lenguaje sencillo, sin jerga.
- Al terminar cada tarea: qué se ha hecho, cómo probarlo y qué sigue.
- Los detalles pequeños de diseño los decide Claude y los explica. Se consultan
  antes las decisiones que cambian qué hace el programa, añaden una función o una
  dependencia, o tocan estos principios.
- Trabajar fase a fase y en tareas pequeñas; mantener `PLAN.md` actualizado.
- Cada tarea en su rama con un pull request. GitHub Actions ejecuta las pruebas en
  Windows y genera un `.exe` de prueba de ese pull request. El usuario lo prueba y
  se fusiona en `main`. Nunca se sube nada directamente a `main`.
- Al cerrar cada fase, revisión del código de esa fase en un hilo aparte.
- Código y comentarios en inglés; interfaz en español (preparada para traducir).
- Pruebas automáticas para la lógica PDF; carpeta `tests/ejemplos/` con PDFs de prueba
  (formulario, BOE, escaneado, con OCR malo, con contraseña, muy largo, firmado).
- No añadir dependencias sin justificarlo (licencia, tamaño, mantenimiento).
- Manejar bien PDFs con contraseña, dañados o enormes, sin que el programa se cierre.
- Pensar en la accesibilidad con lectores de pantalla (NVDA) desde el principio.

## 9. Estructura prevista
```
Lector-PDF/
  CLAUDE.md        # este archivo
  PLAN.md          # plan y estado de cada fase
  PRIMER_PROMPT.md # prompt para empezar a construir
  pyproject.toml   # dependencias (versiones fijadas) y configuración
  app/
    ui/            # ventanas, modos y paneles
    core/          # lógica PDF (abrir, buscar, anotar, firmar…)
  tests/
    core/          # pruebas de la lógica PDF
    ui/            # pruebas de la interfaz
    ejemplos/      # PDFs de prueba
  packaging/       # cómo se crea el programa de Windows y el instalador
  .github/workflows/  # pruebas y creación automática del instalador y la portátil
```
