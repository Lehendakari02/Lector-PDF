# Qué probar en Windows al acabar la Fase 0

Lista para la sesión de prueba. Se amplía con cada tarea. Para todo hace falta
descargar la versión de prueba del último pull request (en GitHub: el pull
request → "Checks" → "Crear programa" → "Summary" → al final, los archivos).

Windows avisará de "editor desconocido": "Más información" → "Ejecutar de todas
formas". Es normal hasta que el programa esté firmado.

## Tarea 0.2 – El programa y el instalador
- [ ] La versión portátil (`Lector-PDF-prueba-…`) se descomprime y `Lector-PDF.exe` abre.
- [ ] La ventana dice "Versión portátil" y una carpeta de datos junto al programa.
- [ ] Abre rápido (apunta más o menos cuánto tarda la primera vez y la segunda).
- [ ] El instalador (`Lector-PDF-instalador-…`) instala sin pedir permisos de
      administrador y el programa aparece en el menú Inicio.
- [ ] El programa instalado NO dice "Versión portátil".
- [ ] Se desinstala bien desde "Aplicaciones" de Windows.

## Tarea 0.4 – Modos, buscador de funciones, claro y oscuro
- [ ] Las pestañas Leer, Estudiar, Rellenar y firmar y Organizar cambian las herramientas.
- [ ] Ctrl+1, Ctrl+2, Ctrl+3 y Ctrl+4 hacen lo mismo.
- [ ] Ctrl+K abre el buscador; "firmar", "unir", "indice" (sin tilde) encuentran la función
      y al pulsar Intro cambia al modo que toca.
- [ ] Menú Ver → Aspecto → Oscuro y Claro: los dos se leen bien.
- [ ] Con "Oscuro" puesto, cerrar y abrir: sigue oscuro.
- [ ] ¿Te cuadran los nombres de las herramientas y en qué modo está cada una?
- [ ] Si tu pantalla está al 125 % o 150 %, ¿se ve nítido y con buen tamaño?

## Tarea 0.5 – Registro de errores
- [ ] Menú Ayuda → "Provocar un error de prueba": sale un aviso y el programa sigue abierto.
- [ ] En el aviso, "Copiar informe de error" y pegar en el Bloc de notas: sale el informe.
- [ ] El informe no contiene tu nombre de usuario de Windows (la carpeta personal sale como `~`).
- [ ] Menú Ayuda → "Copiar informe de error" funciona también sin el aviso.

## Tarea 0.6 – Rendimiento
Con un PDF tuyo largo (un tema o una ley de cientos de páginas) y, si tienes, uno escaneado:
- [ ] "Abrir" (modo Leer) y elegir el PDF: aparece enseguida.
- [ ] Bajar con la rueda del ratón por todo el documento: sin tirones.
- [ ] Arrastrar la barra de la derecha hasta la mitad de golpe: la página aparece
      casi al instante (puede verse un momento una hoja en blanco con su número).
- [ ] Ctrl + rueda acerca y aleja; "Ajustar al ancho" vuelve a encajar la página.
- [ ] El texto se ve nítido, sobre todo si tu pantalla está al 125 % o 150 %
      (compáralo con el mismo PDF en Edge o Adobe).
- [ ] Abajo a la derecha pone cuánto tarda en dibujarse cada página: apunta "la más
      lenta" con tu PDF más pesado.
- [ ] Con un PDF escaneado, lo mismo: ¿va fluido?

## Tarea 0.7 – Buscador
Con un PDF tuyo del BOE o de un temario (con texto, no escaneado):
- [ ] Ctrl+F (o "Buscar" en el modo Leer) abre el panel de búsqueda a la derecha.
- [ ] Buscar una palabra con tilde sin ponerla ("articulo", "administracion"): la encuentra.
- [ ] Buscar "año": no salen resultados de "ano". Con "Palabra completa" tampoco sale "años".
- [ ] Buscar una palabra que en el PDF esté partida con guion al final de una línea: la
      encuentra y marca los dos trozos.
- [ ] Buscar una frase de varias palabras que en el PDF salte de línea: la encuentra.
- [ ] Intro pasa al resultado siguiente y Mayús+Intro al anterior; al pulsar un resultado
      de la lista, el documento va a ese sitio.
- [ ] En un PDF largo los resultados van apareciendo sin que el programa se quede parado.
- [ ] Esc cierra la búsqueda y quita las marcas.
- [ ] ¿Echas algo en falta en el panel? ¿Lo prefieres a la derecha o en otro sitio?

## Tarea 0.8 – Firma con certificado (la prueba más importante de la fase)
Hace falta tu certificado FNMT instalado en Windows (el que usas en el navegador).
- [ ] Abre un PDF cualquiera que no sea importante. Modo "Rellenar y firmar" →
      "Firmar con certificado".
- [ ] ¿Aparece tu certificado en la lista, con tu nombre y la fecha de caducidad?
- [ ] "Firmar con este" → elige dónde guardar la copia. Si Windows pide contraseña o
      permiso para usar la clave, es normal: esa ventana es de Windows, no del programa.
- [ ] Sale "Documento firmado". Si sale un error: Ayuda → "Copiar informe de error" y
      pégamelo.
- [ ] Abre la copia firmada en **Adobe Reader**: arriba debe decir que está firmado, y
      en el panel de firmas, tu nombre. Apunta qué dice exactamente (válida, validez
      desconocida…).
- [ ] Sube la copia a **VALIDe** (valide.redsara.es → "Validar firma") y apunta el
      resultado.
- [ ] Prueba también con un PDF del BOE y con uno que ya esté firmado por otra persona
      (la firma anterior debe seguir siendo válida).
- [ ] Plan B, si tienes el certificado exportado en un archivo `.p12` o `.pfx`: mismo
      botón → "Usar un archivo .p12 o .pfx…" → contraseña → firmar y validar igual.

No subas a VALIDe documentos con datos que no quieras compartir: usa uno de prueba.

## Tarea 0.9 – Reconocer texto (OCR)
Con un PDF escaneado tuyo (un tema fotocopiado y escaneado, por ejemplo):
- [ ] Ábrelo y ve a una página con bastante texto. Modo "Estudiar" → "Reconocer texto"
      (o Ctrl+K y escribir "reconocer").
- [ ] Mientras trabaja (uno o dos segundos) el programa no se queda parado.
- [ ] Sale una ventana con el texto de la página. ¿Se parece al original? Fíjate en
      tildes, eñes y números de artículo.
- [ ] "Copiar texto" y pegar en el Bloc de notas funciona.
- [ ] Pruébalo con un escaneado malo (torcido, con sombras, subrayado a boli) y apunta
      qué tal: sirve para decidir cuánto hay que mejorar la imagen antes de reconocer.

De momento el texto solo se enseña; guardarlo dentro del PDF para poder buscar y
subrayar llega con la fase de documentos escaneados.
