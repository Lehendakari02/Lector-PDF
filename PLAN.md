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
| 0.5 | Registro de errores local y botón "Copiar informe de error" | Provoco un error de prueba, copio el informe y lo pego | ⬜ |
| 0.6 | Prueba de concepto: rendimiento (PDF de 500 páginas, renderizado en segundo plano, pantallas al 125/150 %) | Hago scroll por todo el documento sin tirones y el texto se ve nítido | ⬜ |
| 0.7 | Prueba de concepto: buscador (sin tildes, palabras partidas con guion, la ñ no es n) | "articulo" encuentra "Artícu-lo" partido; "año" no encuentra "ano" | ⬜ |
| 0.8 | Prueba de concepto: firma con certificado del almacén de Windows (FNMT) con pyHanko | Firmo un PDF con mi certificado instalado y Adobe/VALIDe lo dan por válido; si no sale, tengo explicadas las alternativas | ⬜ |
| 0.9 | Prueba de concepto: OCR con Tesseract incluido en el `.exe` | Reconozco una página escaneada en español sin instalar nada aparte; sé cuánto crece el instalador | ⬜ |

**Medidas de la tarea 0.2** (programa casi vacío, 11/11/2026; crecerá con las funciones):
instalador 42 MB; versión portátil 59 MB en `.zip`. La portátil es una carpeta en `.zip`
y no un único `.exe`: la carpeta abre en menos de 1 segundo y el `.exe` único tarda
2,7 segundos cada vez, porque se descomprime en cada arranque.

## Fase 1 – Lector
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 1.1 | Abrir un PDF y verlo con scroll continuo | Abro un tema del BOE y paso páginas con la rueda sin tirones | ⬜ |
| 1.2 | Zoom, ajustar a ancho/página, rotar, pantalla completa | Ctrl+rueda hace zoom; los botones ajustan la vista | ⬜ |
| 1.3 | Panel lateral: miniaturas e índice | Clic en una miniatura o en un apartado del índice me lleva allí | ⬜ |
| 1.4 | Buscador sin tildes ni mayúsculas, con palabras partidas por guion | Busco "articulo" y encuentra "Artículo", también si está partido entre líneas | ⬜ |
| 1.5 | Lista de resultados con contexto, resaltado y siguiente/anterior | Veo todos los resultados con su frase y salto entre ellos con Intro | ⬜ |
| 1.6 | Seleccionar y copiar texto | Copio un artículo y lo pego en otro programa | ⬜ |
| 1.7 | Pestañas (varios PDFs a la vez) | Tengo 3 temas abiertos y cambio entre ellos | ⬜ |
| 1.8 | Reabrir la sesión anterior, recordar página, archivos recientes | Cierro y reabro: vuelven mis pestañas, cada una en su página | ⬜ |
| 1.9 | Modo oscuro, modo lectura (sepia), tamaño de interfaz | Cambio de modo y se ve bien | ⬜ |
| 1.10 | Abrir con doble clic / "Abrir con" / arrastrar / programa predeterminado | Doble clic en un PDF lo abre en Lector-PDF | ⬜ |
| 1.11 | PDFs con contraseña o dañados | Pide la contraseña; un PDF roto da un aviso y no cierra el programa | ⬜ |
| 1.12 | Imprimir | Imprimo unas páginas concretas | ⬜ |
| 1.13 | Aviso de nuevas versiones (desactivable) | Si hay versión nueva en GitHub, me avisa (necesita el repositorio público) | ⬜ |
| 1.14 | Versión 0.1 (instalador y portátil) y repositorio público | Lo instalo, o lo abro sin instalar, y funciona todo lo anterior | ⬜ |

## Fase 2A – Anotar y autoguardado
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.1 | Guardar / Guardar como, con escritura segura (archivo temporal y sustitución) | Ctrl+S guarda en el mismo archivo; "Guardar como" crea otro; si el archivo está bloqueado, avisa y no pierdo nada | ⬜ |
| 2.2 | Resaltar, subrayar, tachar | Selecciono texto y lo marco; tras guardar se ve igual en Edge o Adobe | ⬜ |
| 2.3 | Paleta de colores completa, grosor y opacidad | Elijo cualquier color para cada herramienta | ⬜ |
| 2.4 | Deshacer / rehacer (cada cambio es una "orden", ver `CLAUDE.md` §5) | Ctrl+Z y Ctrl+Y funcionan con todo | ⬜ |
| 2.5 | **Diario de recuperación** | Apago el ordenador a la fuerza mientras subrayo, lo enciendo y no he perdido nada | ⬜ |
| 2.6 | **Guardado automático** (tras 30 s sin editar, al cambiar de pestaña, la X guarda y cierra) e indicador "Guardado / Guardando…" | Subrayo, cierro con la X y al reabrir está todo | ⬜ |
| 2.6b | **Versiones anteriores** y preguntas solo cuando importa (firmado, cambios fuertes, no se puede guardar, cambiado por otro programa) | Vuelvo a como estaba el PDF esta mañana; un PDF firmado nunca se guarda solo | ⬜ |
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
