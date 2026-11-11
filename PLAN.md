# Plan de Lector-PDF

> Plan aprobado. Las instrucciones completas están en `CLAUDE.md`.

Estado: ⬜ pendiente · 🔄 en curso · ✅ hecho

Cada tarea dice **cómo comprobar que está terminada** (lo prueba el usuario en su Windows).
Al acabar cada fase se publica una versión descargable en *Releases*.

---

## Fase 0 – Cimientos
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 0.1 | Estructura del proyecto y dependencias | El código se organiza según `CLAUDE.md` | ⬜ |
| 0.2 | Creación automática del instalador y la versión portátil en GitHub | Al subir cambios aparecen un instalador y un `.exe` portátil que abren una ventana en Windows | ⬜ |
| 0.3 | PDFs de prueba en `tests/ejemplos/` (BOE, formulario, largo, escaneado, con contraseña) | Existen y las pruebas automáticas los usan | ⬜ |
| 0.4 | Esqueleto de la interfaz: pestañas de modos (Leer, Estudiar, Rellenar y firmar, Organizar) y buscador de funciones (Ctrl+K) | Cambio de modo y cambian las herramientas visibles | ⬜ |

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
| 1.13 | Aviso de nuevas versiones (desactivable) | Si hay versión nueva en GitHub, me avisa | ⬜ |
| 1.14 | Versión 0.1 (instalador y portátil) | Lo instalo, o lo abro sin instalar, y funciona todo lo anterior | ⬜ |

## Fase 2A – Anotar y autoguardado
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.1 | Guardar / Guardar como | Ctrl+S guarda en el mismo archivo; "Guardar como" crea otro | ⬜ |
| 2.2 | Resaltar, subrayar, tachar | Selecciono texto y lo marco; tras guardar se ve igual en Edge o Adobe | ⬜ |
| 2.3 | Paleta de colores completa, grosor y opacidad | Elijo cualquier color para cada herramienta | ⬜ |
| 2.4 | Deshacer / rehacer | Ctrl+Z y Ctrl+Y funcionan con todo | ⬜ |
| 2.5 | **Autoguardado, diario de recuperación y respaldos** | Apago el ordenador a la fuerza mientras subrayo, lo enciendo y no he perdido nada | ⬜ |
| 2.6 | Indicador "Guardado / Guardando…" y aviso al cerrar | Siempre sé si mis cambios están a salvo | ⬜ |
| 2.7 | Notas adhesivas y cuadros de texto | Escribo notas y texto con la fuente, tamaño y color que quiero | ⬜ |
| 2.8 | Dibujo a mano alzada, flechas, formas, borrador | Dibujo y borro sobre la página | ⬜ |
| 2.9 | Seleccionar, mover, redimensionar, copiar y borrar anotaciones | Corrijo una anotación mal puesta sin rehacerla | ⬜ |
| 2.10 | Herramientas favoritas | Guardo "rotulador amarillo fino" y lo uso con un clic | ⬜ |
| 2.11 | Lápiz y pantalla táctil | Subrayo con lápiz en una tableta sin que la mano pinte | ⬜ |
| 2.12 | Mostrar/ocultar anotaciones (también al imprimir/exportar) | Con un botón veo el documento limpio | ⬜ |
| 2.13 | Atajos de teclado para cada herramienta | Cambio de herramienta sin usar el ratón | ⬜ |
| 2.14 | Versión 0.2 | Estudio un tema completo con el programa durante una sesión real | ⬜ |

## Fase 2B – Herramientas de estudio
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 2.15 | Márgenes ampliables | Añado margen a una página y escribo en él; se ve en otros lectores | ⬜ |
| 2.16 | Insertar hojas en blanco, de rayas o cuadriculadas | Meto una hoja cuadriculada para un esquema | ⬜ |
| 2.17 | Panel de anotaciones filtrable por color | Veo todos mis subrayados de un color y salto a cada uno | ⬜ |
| 2.18 | Código de colores propio (opcional, nada predefinido) | Si quiero, pongo nombre a mis colores; si no, no aparece nada | ⬜ |
| 2.19 | Marcadores propios | Marco artículos clave y vuelvo a ellos con un clic | ⬜ |
| 2.20 | Saltar a artículo, apartado o sección por su número | Escribo "art. 14" o "3.2" en cualquier documento y me lleva allí | ⬜ |
| 2.21 | Exportar resumen | Saco un documento con todo lo subrayado, ordenado por página | ⬜ |
| 2.22 | Modo repaso | Lo subrayado se tapa y lo descubro al hacer clic | ⬜ |
| 2.23 | Vista de dos documentos lado a lado | Veo el tema y la ley a la vez | ⬜ |
| 2.24 | Enlaces entre documentos *(pendiente de confirmar)* | Desde una nota del tema, un clic abre la ley en el artículo exacto | ⬜ |
| 2.25 | Biblioteca del temario | Elijo mi carpeta de temas, busco en todos y veo mi progreso | ⬜ |
| 2.26 | Comparar dos versiones de un documento | Veo qué ha cambiado entre dos versiones de una ley | ⬜ |
| 2.27 | Versión 0.3 | — | ⬜ |

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
| 3.8 | Versión 0.4 | — | ⬜ |

## Fase 4 – Firma con certificado digital
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 4.1 | Firmar con certificado instalado en Windows (FNMT) | El PDF firmado sale válido en VALIDe y en Adobe | ⬜ |
| 4.2 | Firmar con archivo .p12/.pfx | Ídem | ⬜ |
| 4.3 | Firma visible o invisible; sello de tiempo opcional; recordar preferencias | Firmar es elegir dónde y poner el PIN | ⬜ |
| 4.4 | Firmar varios documentos de una vez | Firmo 10 documentos poniendo el PIN una vez | ⬜ |
| 4.5 | Firmar con DNIe y lector de tarjetas | Firmo con el DNIe (cuando tenga lector) | ⬜ |
| 4.6 | Ver y verificar firmas existentes | Abro un PDF firmado y me dice quién lo firmó y si es válido | ⬜ |
| 4.7 | Versión 0.5 | — | ⬜ |

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
| 5.8 | Versión 1.0 | — | ⬜ |

## Fase 6 – Editar el texto original
| # | Tarea | Terminado cuando… | Estado |
|---|-------|-------------------|--------|
| 6.1 | Corregir texto puntual | Cambio una palabra del documento y se ve natural | ⬜ |

## Ideas para más adelante
OCR · versión para tableta o móvil · Mac/Linux.
