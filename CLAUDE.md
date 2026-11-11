# Instrucciones del proyecto: Lector-PDF

> Versión 0.4. Todas las decisiones principales están tomadas.

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
   firma con certificado y la comprobación de nuevas versiones en GitHub.
2. **Sin muros de pago ni marcas de agua.**
3. **PDF estándar siempre.** Todo lo que se guarda (subrayados, notas, formularios,
   firmas, márgenes, hojas añadidas) usa el estándar PDF y se ve igual en Adobe Reader,
   navegadores y otros visores. Nunca un formato que solo entienda este programa.
4. **El usuario decide cómo guardar:**
   - **Guardar** (Ctrl+S): guarda los cambios en el mismo archivo.
   - **Guardar como** (Ctrl+Mayús+S): crea una copia nueva.
   - Aviso si se va a modificar un PDF ya firmado (cambiarlo invalida la firma).
5. **Nunca perder trabajo (autoguardado).** Imprescindible: un apagón, un cierre por
   error o un fallo del programa no pueden borrar horas de estudio. Ver sección 5.
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

## 5. Autoguardado y recuperación (obligatorio desde la Fase 2)
- **Diario de cambios:** cada cambio (subrayado, nota, texto, campo rellenado…) se
  apunta al instante en un archivo de recuperación en la carpeta de datos del
  programa (`%APPDATA%\Lector-PDF\recuperacion`). Escritura segura: se escribe en un
  archivo temporal y se renombra, para que un apagón no lo deje a medias.
- **Guardado automático en el propio PDF:** activado por defecto, cada pocos segundos
  tras dejar de editar (y al cambiar de pestaña o cerrar). Se puede desactivar y
  ajustar el intervalo en Ajustes.
- **Copia de respaldo:** la primera vez que se modifica un PDF en cada sesión, se
  guarda una copia del original en la carpeta de respaldos (se conservan las últimas).
- **Recuperación:** al abrir el programa tras un cierre inesperado, ofrece recuperar
  los cambios no guardados de cada documento.
- **Indicador visible:** siempre se ve el estado ("Guardado", "Guardando…", "Cambios
  sin guardar"). Al cerrar con cambios sin guardar, se avisa.
- **Pruebas obligatorias:** simular cierres a la fuerza a mitad de edición y comprobar
  que no se pierde nada ni se corrompe el PDF.

## 6. Funciones por fases
### Fase 1 – Lector
- Abrir PDF (menú, arrastrar y soltar, doble clic, "Abrir con…", programa predeterminado).
- **Pestañas** para tener varios PDFs abiertos; **al abrir el programa vuelven las
  pestañas de la última vez**, cada una en su página.
- Scroll continuo, miniaturas, ir a página, índice del documento.
- Zoom, ajustar a ancho/página, rotar, pantalla completa.
- **Buscador excelente:**
  - No distingue tildes ni mayúsculas: "articulo" encuentra "Artículo"; "camion",
    "CAMIÓN".
  - Encuentra palabras partidas con guion al final de línea y frases que saltan de
    línea (muy habitual en el BOE).
  - Lista de resultados con la frase alrededor; resaltado de todos en la página;
    siguiente/anterior con Intro y Mayús+Intro.
  - Opciones para palabra completa o coincidencia exacta.
- Seleccionar y copiar texto.
- Modo oscuro y modo lectura (tono sepia/cálido para leer muchas horas).
- Archivos recientes. Imprimir.
- **Instalador** y **versión portátil** (un `.exe` que funciona sin instalar, por
  ejemplo en el ordenador del trabajo).
- **Aviso de nuevas versiones** (consulta GitHub Releases; desactivable).

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
- **Enlaces entre documentos** *(pendiente de confirmar)*: desde una nota o un
  subrayado, crear un enlace que abre otro PDF en la página exacta (p. ej. desde el
  tema, el artículo de la ley).
- **Vista de dos documentos** lado a lado (p. ej. tema y ley).
- **Biblioteca del temario**: carpeta con todos los temas, búsqueda en todos a la vez
  (con las mismas reglas del buscador) y progreso por tema (leído / subrayado / repasado).
- **Comparar dos versiones** de un documento: muestra qué texto se ha añadido, quitado
  o cambiado (p. ej. cuando se modifica una ley del temario).

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

### Fase 6 – Editar el texto original
- Corregir o sustituir texto del documento, empezando por cambios puntuales.

### Ideas para más adelante
- OCR (convertir PDFs escaneados en texto que se pueda buscar y subrayar).
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
- **pyHanko**: firma con certificado (PAdES, sellos de tiempo, DNIe por PKCS#11).
- Instalador `.exe` y versión portátil generados automáticamente en GitHub (GitHub
  Actions) y publicados en "Releases".
- Licencia: **AGPL-3.0** (software libre, obligatoria por usar PyMuPDF; compatible con
  compartirlo gratis o hacerlo público).
- La lógica PDF (`core/`) no depende de la interfaz (`ui/`), para poder probarla sola
  y, en el futuro, reutilizarla en otra versión.

## 8. Forma de trabajar
- El usuario no programa: dirige, prueba y decide. Claude programa todo.
- Explicar los avances en lenguaje sencillo, sin jerga.
- Al terminar cada tarea: qué se ha hecho, cómo probarlo y qué sigue.
- Las decisiones de diseño o funciones se consultan antes de implementarlas.
- Trabajar fase a fase y en tareas pequeñas; mantener `PLAN.md` actualizado.
- Código y comentarios en inglés; interfaz en español (preparada para traducir).
- Pruebas automáticas para la lógica PDF; carpeta `tests/ejemplos/` con PDFs de prueba
  (formulario, BOE, escaneado, con contraseña, muy largo, firmado).
- No añadir dependencias sin justificarlo (licencia, tamaño, mantenimiento).
- Manejar bien PDFs con contraseña, dañados o enormes, sin que el programa se cierre.

## 9. Estructura prevista
```
Lector-PDF/
  CLAUDE.md        # este archivo
  PLAN.md          # plan y estado de cada fase
  PRIMER_PROMPT.md # prompt para empezar a construir
  app/
    ui/            # ventanas, modos y paneles
    core/          # lógica PDF (abrir, buscar, anotar, firmar…)
  tests/
    ejemplos/
  .github/workflows/  # creación automática del instalador y la versión portátil
```
