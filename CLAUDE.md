# Instrucciones del proyecto: Lector PDF

> Versión 0.2. Las partes marcadas con **[DECIDIR]** están pendientes de acordar.

## 1. Qué es y para quién
Aplicación de escritorio gratuita y de código abierto para leer, estudiar, rellenar,
editar y firmar PDFs. Pensada para una persona normal:
- **Estudiar** sobre PDFs (por ejemplo, temarios de oposición y textos del BOE):
  subrayar, anotar y repasar en el ordenador en lugar de con papel y boli.
  **Es la prioridad principal y debe ser lo mejor del programa.**
- **Rellenar** formularios y documentos.
- **Firmar** contratos y documentos laborales, de empresas y de la administración, con
  firma manuscrita y con **certificado digital con validez legal** (FNMT, DNIe).
- **Organizar** páginas: unir, dividir, reordenar, rotar, eliminar.

Sin ánimo de lucro: se podrá compartir con familia, amigos o publicarse.

## 2. Principios (no negociables)
1. **Todo en local.** Ningún documento sale del ordenador. Sin cuentas, sin nube, sin
   telemetría. Única excepción: el sello de tiempo de la firma, si el usuario lo activa.
2. **Sin muros de pago ni marcas de agua.**
3. **PDF estándar siempre.** Todo lo que se guarda (subrayados, notas, formularios,
   firmas) usa el estándar PDF y se ve igual en Adobe Reader, navegadores y otros
   visores. Nunca un formato que solo entienda este programa.
4. **El usuario decide cómo guardar:**
   - **Guardar** (Ctrl+S): guarda los cambios en el mismo archivo.
   - **Guardar como** (Ctrl+Mayús+S): crea una copia nueva.
   - Red de seguridad: copia de respaldo automática antes de sobrescribir y
     autoguardado de recuperación por si se cierra el programa inesperadamente.
   - Aviso si se va a modificar un PDF ya firmado (cambiarlo invalida la firma).
5. **Simple antes que completo.** Lo habitual, a la vista; lo avanzado, en menús.
6. **Rápido**, incluso con PDFs de cientos de páginas.

## 3. Qué significa "editar" (decisión tomada)
Hay dos niveles de edición:
- **Nivel 1 – Trabajar sobre el documento** (Fases 2 y 3): subrayar, resaltar, notas,
  dibujar, escribir texto encima, rellenar, firmar. Se guarda en el mismo PDF y
  cualquier lector lo ve. El texto original no cambia, pero el archivo sí.
- **Nivel 2 – Cambiar el texto original** (Fase 6): corregir o sustituir palabras y
  frases del propio documento. Es técnicamente difícil (los PDF no están hechos para
  esto) y se hará más adelante, empezando por correcciones puntuales.

## 4. Funciones por fases
### Fase 1 – Lector
- Abrir PDF (menú, arrastrar y soltar, "Abrir con…" de Windows, PDF predeterminado).
- **Pestañas** para tener varios PDFs abiertos.
- Scroll continuo, miniaturas, ir a página, índice del documento.
- Zoom, ajustar a ancho/página, rotar, vista a pantalla completa.
- Buscar texto (con resaltado de todos los resultados), seleccionar y copiar.
- Modo oscuro y **modo lectura** (tono sepia/cálido para leer muchas horas).
- Recordar la última página leída de cada documento. Archivos recientes.
- Imprimir.

### Fase 2 – Estudiar, anotar y rellenar (prioridad principal)
Básico:
- Resaltar, subrayar y tachar texto seleccionándolo, en varios colores.
- Notas adhesivas, cuadros de texto, flechas y formas, dibujo a mano alzada, borrador.
- Rellenar formularios PDF (campos, casillas, desplegables) y escribir en PDFs sin campos.
- Deshacer/rehacer ilimitado.
- Atajos de teclado para cada herramienta (estudiar rápido sin ratón).

Para estudiar mejor (propuestas, **[DECIDIR]** cuáles entran):
- **Colores con significado**: el usuario define qué significa cada color
  (p. ej. amarillo = importante, rojo = plazos, verde = definiciones).
- **Panel de anotaciones**: lista de todos los subrayados y notas del documento,
  filtrable por color, para saltar a cada uno.
- **Exportar resumen**: sacar todo lo subrayado y anotado a un documento de resumen.
- **Marcadores propios** para marcar artículos o páginas clave.
- **Modo repaso**: ocultar lo subrayado para intentar recordarlo (tipo tarjetas).
- **Biblioteca del temario**: carpeta con todos los temas, búsqueda en todos a la vez
  y progreso de estudio por tema (leído / subrayado / repasado).
- **Vista de dos documentos** lado a lado (p. ej. tema y ley del BOE).
- Herramientas pensadas para el BOE: saltar a un artículo por su número.

### Fase 3 – Firma manuscrita
- Crear firma dibujando, escribiendo el nombre o importando una imagen (quitando el fondo).
- Guardar varias firmas reutilizables; colocar, mover, redimensionar.
- Fecha automática; iniciales en todas las páginas.

### Fase 4 – Firma con certificado digital (validez legal)
- Firmar con el certificado instalado en Windows (p. ej. FNMT), con archivo .p12/.pfx
  y con DNIe o tarjeta (lector de tarjetas).
- Formato PAdES (el estándar europeo/español), con sello de tiempo opcional.
- Firma visible (recuadro con nombre y fecha) o invisible.
- Ver y comprobar las firmas que ya tiene un PDF.
- Prueba de validez: los PDFs firmados deben validarse en VALIDe (Gobierno de España)
  y en Adobe Reader.

### Fase 5 – Organizar páginas
- Unir, dividir, reordenar (arrastrando miniaturas), rotar, eliminar, extraer.
- Insertar páginas de otro PDF o imágenes (p. ej. fotos de un documento con el móvil).
- Comprimir, poner/quitar contraseña.

### Fase 6 – Editar el texto original
- Corregir o sustituir texto del documento, empezando por cambios puntuales.

### Ideas para más adelante
- OCR (convertir PDFs escaneados en texto que se pueda buscar y subrayar).
- Leer en voz alta. Versión para otros sistemas (Mac/Linux) si sale fácil.

## 5. Tecnología
- **Windows** es el objetivo principal. Se elige tecnología que también funcione en
  Mac/Linux sin esfuerzo extra, pero solo se prueba y publica para Windows.
- **Python + PySide6 (Qt)**: interfaz de escritorio.
- **PyMuPDF**: mostrar, anotar, rellenar y organizar páginas.
- **pyHanko**: firma con certificado (PAdES, sellos de tiempo, DNIe por PKCS#11).
- Instalador `.exe` para Windows generado automáticamente en GitHub (GitHub Actions)
  y publicado en la sección "Releases" del repositorio.
- Licencia: **AGPL-3.0** (software libre, obligatoria por usar PyMuPDF; compatible con
  compartirlo gratis o hacerlo público).

## 6. Forma de trabajar
- El usuario no programa: dirige, prueba y decide. Claude programa todo.
- Explicar los avances en lenguaje sencillo, sin jerga.
- Al terminar cada tarea: qué se ha hecho, cómo probarlo y qué sigue.
- Las decisiones de diseño o funciones se consultan antes de implementarlas.
- Trabajar fase a fase y en tareas pequeñas; mantener `PLAN.md` actualizado.
- Código y comentarios en inglés; interfaz en español.
- Pruebas automáticas para la lógica PDF; carpeta `tests/ejemplos/` con PDFs de prueba
  (formulario, BOE, escaneado, con contraseña, muy largo, firmado).
- No añadir dependencias sin justificarlo (licencia, tamaño, mantenimiento).
- Manejar bien PDFs con contraseña, dañados o enormes, sin que el programa se cierre.

## 7. Estructura prevista
```
lector-pdf/
  CLAUDE.md        # este archivo
  PLAN.md          # plan y estado de cada fase
  app/
    ui/            # ventanas y paneles
    core/          # lógica PDF (abrir, anotar, firmar…)
  tests/
    ejemplos/
  .github/workflows/  # creación automática del instalador .exe
```
