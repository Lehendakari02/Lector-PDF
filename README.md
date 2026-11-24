# Lector-PDF

Lector, editor y firmador de PDF **gratuito, sin anuncios y que funciona sin conexión** para Windows.

Pensado para el día a día:

- 📖 **Leer** PDFs con comodidad: pestañas, modo oscuro, modo lectura.
- ✏️ **Estudiar y anotar**: subrayar, resaltar, notas y dibujo, guardado dentro del propio PDF.
- 📝 **Rellenar** formularios y escribir sobre cualquier documento.
- ✍️ **Firmar** con firma manuscrita o con **certificado digital** (FNMT, DNIe) con validez legal.
- 📑 **Organizar** páginas: unir, dividir, reordenar, rotar, comprimir, comparar.

Tus documentos nunca salen de tu ordenador. Los PDFs que guarda son estándar y se abren en cualquier otro lector.

## Estado

Versión 1.0: **todo lo previsto para leer, estudiar, rellenar, firmar y organizar**.

- **Leer**: pestañas que vuelven al abrir, buscador sin tildes ni mayúsculas (la ñ
  no es una n, encuentra palabras partidas con guion), índice, miniaturas, modo
  oscuro y papel sepia, imprimir y actualización con un clic.
- **Estudiar**: subrayar, resaltar y tachar con cualquier color, notas, texto sobre
  la página, dibujo con presión del lápiz, formas, herramientas favoritas, márgenes
  para apuntes, hojas en blanco, marcadores, panel de anotaciones, resumen, modo
  repaso, saltar a un artículo, dos documentos lado a lado, biblioteca del temario
  y enlaces entre documentos.
- **Documentos escaneados**: reconocer el texto (OCR en español, sin internet).
- **Rellenar y firmar**: formularios, «Mis datos», sellos, firma manuscrita y firma
  con certificado digital (FNMT, archivo .p12/.pfx, DNIe), también de varios
  documentos a la vez, y comprobar las firmas de un PDF.
- **Organizar**: ordenar, girar, eliminar e insertar páginas; unir, dividir y
  extraer; de foto a PDF; exportar como imagen o texto; tapar datos de verdad;
  comprimir; poner o quitar la contraseña; comparar dos versiones de un documento.
- **Nunca perder trabajo**: diario de recuperación tras un apagón, versiones
  anteriores y recuperar lo que se descartó con «No guardar».
- **Ayuda** dentro del programa (F1) y buscador de funciones (Ctrl+K).

Lo siguiente es cambiar el texto original del documento (Fase 6). El avance está en
[`PLAN.md`](PLAN.md).

## Descarga

En la sección [**Releases**](https://github.com/Lehendakari02/Lector-PDF/releases)
hay dos descargas de cada versión, para Windows 10 y 11:

- `Lector-PDF-…-instalador.exe`: se instala sin pedir permisos de administrador.
- `Lector-PDF-…-portatil.zip`: se descomprime y funciona sin instalar. Guarda sus
  ajustes en su propia carpeta.

Windows puede avisar de que no conoce el programa ("Windows protegió su PC"),
porque todavía no lleva firma de código: pulsa "Más información" y "Ejecutar de
todas formas".

## Para desarrollo

Hace falta Python 3.13.

```
python -m pip install -e ".[dev]" -c packaging/versiones-fijadas.txt
python -m app        # abre el programa
python -m pytest     # pruebas automáticas
```

## Licencia

Software libre bajo licencia [AGPL-3.0](LICENSE). Las piezas de software libre que usa y
sus licencias están en [`app/recursos/licencias/AVISOS.txt`](app/recursos/licencias/AVISOS.txt)
y, dentro del programa, en Ayuda → Acerca de.
