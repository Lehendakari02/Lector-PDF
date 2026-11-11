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

🚧 En desarrollo. Consulta [`PLAN.md`](PLAN.md) para ver el avance.

## Descarga

Cuando haya una versión lista, el instalador `.exe` estará en la sección **Releases** de este repositorio.

## Para desarrollo

Hace falta Python 3.13.

```
python -m pip install -e ".[dev]"
python -m app        # abre el programa
python -m pytest     # pruebas automáticas
```

## Licencia

Software libre bajo licencia [AGPL-3.0](LICENSE).
