# PDFs de prueba

PDFs que usan las pruebas automáticas. Todo el contenido es inventado, salvo
`boe.pdf`, que es un documento público. **Nunca se guardan aquí documentos personales.**

| Archivo | Qué es | Para qué sirve |
|---|---|---|
| `boe.pdf` | La Constitución Española, texto consolidado del BOE (BOE-A-1978-31229), 39 páginas con índice. Fuente: Agencia Estatal Boletín Oficial del Estado, boe.es | Un documento real de estudio: buscador, índice, saltar a artículo |
| `largo.pdf` | 520 páginas de texto con índice | Rapidez con documentos enormes |
| `texto-partido.pdf` | Palabras partidas con guion al final de línea, "año" y "ano" | Buscador |
| `texto-dificil.pdf` | Letras unidas ("ﬁ", "ﬂ"), tildes y "ñ" escritas en dos piezas, una frase que sigue en la página siguiente, entre pie y cabecera, y comillas, apóstrofos y guiones tipográficos | Buscador |
| `formulario.pdf` | Campos de texto, casillas y lista desplegable | Rellenar formularios |
| `con-contrasena.pdf` | Pide contraseña al abrir. La contraseña es `lector` | PDFs protegidos |
| `escaneado.pdf` | 3 páginas que son solo una imagen torcida y con ruido | Reconocer texto (OCR) |
| `ocr-malo.pdf` | Escaneado con texto oculto lleno de fallos ("Articu1o", "ano") | Rehacer el OCR, búsqueda aproximada |
| `firmado.pdf` | Firmado con el certificado de prueba | Ver y comprobar firmas |
| `certificado-prueba.p12` | Certificado inventado. La contraseña es `prueba` | Firmar en las pruebas |

El certificado de prueba no identifica a nadie ni protege nada: está a la vista a
propósito, solo para las pruebas.

Todos menos `boe.pdf` se crean con `python tests/ejemplos/generar.py`. Solo hace
falta ejecutarlo para cambiarlos. `texto-dificil.pdf` se crea aparte, con la función
`make_tricky_text` de ese archivo (necesita la fuente DejaVu Serif).
