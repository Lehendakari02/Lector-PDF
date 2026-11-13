# Lector-PDF

Lector, editor y firmador de PDF **gratuito, sin anuncios y que funciona sin conexión** para Windows.

Pensado para el día a día:

- 📖 **Leer** PDFs con comodidad: pestañas, modo oscuro, modo lectura.
- ✏️ **Estudiar y anotar**: subrayar, resaltar, notas y dibujo, guardado dentro del propio PDF.
- 📝 **Rellenar** formularios y escribir sobre cualquier documento.
- ✍️ **Firmar** con firma manuscrita o con **certificado digital** (FNMT, DNIe) con validez legal.
- 📑 **Organizar** páginas: unir, dividir, reordenar, rotar.

Tus documentos nunca salen de tu ordenador. Los PDFs que guarda son estándar y se abren en cualquier otro lector.

## Estado

Versión 0.1: **el lector**. Abrir PDFs en pestañas, buscar sin tildes ni mayúsculas,
copiar texto, índice y miniaturas, modo oscuro y papel sepia, imprimir, PDFs con
contraseña y actualización con un clic.

Lo siguiente es estudiar y anotar (subrayar, notas, dibujo). Las funciones que aún
no están hechas aparecen en el programa en gris. El avance está en [`PLAN.md`](PLAN.md).

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
