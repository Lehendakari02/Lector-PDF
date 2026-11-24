# Pruebas que quedan por hacer

Esta lista sustituye a las de las fases 0 a 4 y a la de las mejoras. Solo
quedan las pruebas que **no** se hicieron el 23/11/2026, cuando Claude probó
la versión 0.7.0 en el ordenador de Julen (resultados en `PLAN.md`, apartado
«Pruebas con Adobe»). Las de la Fase 5 siguen en `docs/pruebas-fase-5.md`.

Casi todo lo que queda necesita algo que Claude no puede hacer: el lápiz o la
pantalla táctil, NVDA, el DNIe, escribir un PIN o una contraseña, cerrar el
programa a la fuerza, Edge, Word, papel, o tus propios datos. Cada paso: lo
que haces → lo que debe pasar.

## Lo que ya está probado (no hace falta repetirlo)

Abrir, girar la vista, pantalla completa, ir a una página, índice y
miniaturas, buscador (tildes, ñ, mayúsculas, «fi», vista girada), copiar
texto, pestañas, modo lectura, Ctrl+K, la ventana de imprimir y sus avisos,
aviso de versiones y actualizar con un clic, Acerca de, volver a las pestañas
al abrir, Guardar y avisos al guardar (archivo abierto en Adobe, PDF firmado),
saltar a un artículo, marcadores, modo repaso, ver al lado, exportar resumen
en PDF, versiones anteriores, enlaces entre documentos, zoom al 600 %, cursor
de lectura con el teclado, lista de teclas, y todo lo que se mira en Adobe
(anotaciones, colores, formas, sellos, márgenes, hojas, OCR, formulario,
letras de otros idiomas, firmas con certificado: hueco, invisible, sello de
tiempo, varias a la vez, PDF protegido, anotar un PDF firmado).

## Con tus manos (ratón y teclado)

1. **Resaltar con el rotulador en la mano:** Estudiar → Resaltar sin nada
   seleccionado → cada frase que selecciones queda resaltada; doble clic
   resalta una palabra; Esc suelta el rotulador.
2. **Colores:** la flechita de Resaltar → otro color, «Más colores…» y
   opacidad al 40 % → se ven al momento; al cerrar y abrir cada herramienta
   sigue con su color.
3. **Deshacer hasta como estaba guardado** (arreglado el 23/11): resalta algo
   y pulsa Ctrl+Z → abajo vuelve a poner «Guardado», la pestaña pierde el ● y
   al cerrarla no pregunta.
4. **Notas y textos:** Nota → clic → escribe con ñ y tildes → se lee al pasar
   el ratón; clic para cambiarla; Borrar y Ctrl+Z la devuelve. Texto → clic →
   escribe dos líneas, A+, N y rojo → al hacer clic fuera se queda igual.
   `->` se convierte en →; el botón «→ ✓» pone símbolos.
5. **Dibujar, formas y borrador:** dibuja, cambia color y grosor, haz una
   flecha, un recuadro con relleno claro, un rombo con línea discontinua y una
   llave; Mayús deja la línea recta. El borrador quita un trazo entero.
6. **Elegir y mover:** sin herramienta, clic en una forma → tiradores;
   arrastra, cambia el tamaño, flechas del teclado, Supr, Ctrl+D, Ctrl+C y
   Ctrl+V (también en otro PDF). Clic en un resaltado → barra de colores para
   cambiarle el color.
7. **Favoritas:** guarda «Dibujar · rojo · grueso» en favoritas; úsala,
   cámbiale el nombre, muévela y quítala; al cerrar y abrir siguen.
8. **Ocultar anotaciones** (tecla O): la página queda limpia y al imprimir la
   casilla «Con las anotaciones» sale sin marcar.
9. **Una tecla para cada herramienta:** D dibujar, B borrador, R, S, T, N, X,
   F; 1 y 2 cogen las favoritas; escribiendo en el buscador las letras no
   cogen nada.
10. **Elegir otra tecla:** Ajustes → Teclado → doble clic en «Subrayar» → U →
    funciona; «Restablecer todas» lo deja como estaba. Ctrl++ y Ctrl+−
    acercan y alejan.
11. **Hoja en blanco:** Insertar hoja → Cuadriculada y De rayas; haz un
    esquema; Ctrl+Z quita el esquema y luego la hoja.
12. **Márgenes:** Añadir margen a la izquierda y abajo, en todas las páginas;
    el subrayado se va con el texto; Deshacer lo quita.
13. **Panel de anotaciones** (F4 → Anotaciones): filtra por color; un clic
    lleva a cada una; cambia solo al resaltar o borrar.
14. **Nombres para tus colores:** clic derecho en el amarillo → «Ponerle
    nombre…» → sale en el panel y en el resumen; «Quitarle el nombre».
15. **Volver a como estaba al abrirlo** (Archivo): quita todo de una vez;
    Ctrl+Y lo devuelve uno a uno.
16. **Recuperar cambios descartados:** resalta, cierra la pestaña → No
    guardar → Archivo → Recuperar cambios descartados → vuelven.
17. **Ajustes → Guardado:** «Guardar siempre», «No guardar nunca sin que lo
    pida» y «Guardar solo mientras trabajo» (10 segundos) hacen lo que dicen;
    al acabar, déjalo en «Preguntar» y sin guardar solo.
18. **Otro programa cambia el archivo** mientras está abierto (gíralo en Edge
    y guarda) → al guardar aquí avisa.
19. **Adjunto de correo** abierto sin descargar → al guardar ofrece guardarlo
    en una carpeta tuya.
20. **Biblioteca del temario:** elige la carpeta de tus temas → salen en orden
    («Tema 2» antes que «Tema 10»), con leído, subrayados y repaso; «Buscar en
    todos los temas» y doble clic en un resultado; se acuerda de la carpeta.
21. **Crear un enlace** desde un tema: selecciona «artículo 14», clic derecho
    → Enlazar a… → la ley → `art. 14` → «Enlazar aquí»; mueve la ley de
    carpeta y comprueba «Documento no encontrado» y «¿Dónde está ahora?…».
22. **Escaneados:** abre un escaneado sin texto → franja «Reconocer texto» →
    progreso, Cancelar, buscar y subrayar después; «Volver a reconocer texto»
    con `tests/ejemplos/ocr-malo.pdf` y la búsqueda «Aproximada, para
    escaneados».
23. **Ventana** (arreglado el 23/11): maximiza el programa, ciérralo y ábrelo
    → vuelve maximizado. Con otro tamaño, vuelve con ese tamaño y en su sitio.
24. **Imprimir de verdad:** una página, `1-3, 7`, por las dos caras, en blanco
    y negro y con una página apaisada; Cancelar a medias para.
25. **Barra que se desliza:** estrecha la ventana en Estudiar → las
    herramientas siguen en una fila, con una flecha a cada lado; cada clic
    desliza, mantenerla pulsada sigue deslizando, la rueda del ratón también;
    con la ventana ancha no salen flechas.
26. **PDF dañado o que no es PDF:** cambia la extensión de una foto a `.pdf`
    → avisa y el programa sigue abierto.
27. **Copiar informe de error** (Ayuda): se pega en el Bloc de notas sin tu
    nombre de usuario.

## Corregir texto (Fase 6, tarea 6.1)

Con un PDF hecho con Word (un contrato, un tema tuyo) y con el BOE:

1. **Una palabra:** doble clic en una palabra → Organizar → «Corregir texto» →
   escribe otra → se ve como si siempre hubiera estado ahí (misma letra, tamaño
   y color) y el resto de la línea se corre sin montarse.
2. **Línea justificada:** cambia una palabra en medio de un párrafo del BOE →
   la línea sigue llegando al margen derecho.
3. **Título centrado:** cambia una palabra de un título → sigue centrado.
4. **Una letra que el documento no usa** (por ejemplo una «Ñ» o una «Q»
   mayúscula) → abajo dice qué letra de Windows ha usado; ¿se nota?
5. **Buscar y copiar:** busca la palabra nueva → la encuentra; selecciona la
   frase entera y cópiala al Bloc de notas → sale en su orden.
6. **No cabe:** escribe algo muy largo → dice «no cabe» y no cambia nada.
7. **Deshacer, guardar y Edge:** Ctrl+Z la devuelve; vuelve a cambiarla,
   guarda y abre el PDF en Edge → se ve igual y se puede buscar.
8. **Escaneado:** en una página escaneada dice que es una foto y no la toca.

## Formularios y firma a mano (con tus datos)

1. **Rellenar** un formulario oficial: Tab y Mayús+Tab, casillas, opciones
   Sí/No (solo una marcada, también en Adobe y Edge), desplegables con
   nombres, Ctrl+Intro en un campo de varias líneas, Ctrl+Z.
2. **Escribir en un PDF sin campos** (Rellenar y firmar → Escribir).
3. **Mis datos:** guárdalos una vez y usa «Rellenar el formulario con mis
   datos» en formularios reales; dime qué campos no reconoce.
4. **Sellos:** ✓, ✗, ●, fecha de hoy, Recibido y un sello propio.
5. **Tu firma y tus iniciales:** dibujada, escrita y desde una foto (también
   en vertical); firmar con un clic, la fecha encima si va abajo del todo,
   iniciales en todas las páginas; Ctrl+S propone «-firmado».
6. **Firma visible** (arreglado el 23/11): ponla encima de texto → el recuadro
   es blanco y se lee bien, aquí y en Adobe.

## Firma con certificado (con tu PIN o contraseña)

1. **Archivo .p12/.pfx:** Firmar con certificado → «Usar un archivo .p12 o
   .pfx…» → contraseña → válido en VALIDe; contraseña mala → no firma.
2. **Cancelar el PIN** de Windows → «Firma cancelada» y no se crea nada.
3. **DNIe** con lector de tarjetas: sale con la marca «DNIe»; firma una y
   varias (¿cuántas veces pide el PIN?); sin tarjeta → «Mete la tarjeta».
4. **PDF con contraseña:** se abre con ella y el firmado la sigue pidiendo.
5. **Sin internet y con sello de tiempo** → ofrece «Firmar sin sello de
   tiempo».
6. **VALIDe** (valide.redsara.es): sube un firmado por el programa.

## Cerrar a la fuerza (Administrador de tareas)

1. Resalta, escribe una nota a medias o pon una hoja, **sin guardar**, y
   Finalizar tarea → al abrir ofrece recuperarlo todo, en su página.
2. «Ahora no» → luego está en Archivo → Recuperar cambios descartados.
3. A mitad de «Reconocer texto» → al volver a pulsarlo, avanza rápido.

## Lápiz y pantalla táctil (Surface o tableta)

Arrastrar y pellizcar, mantener el dedo para seleccionar o para el menú,
dibujar con presión, apoyar la palma sin pintar, goma y botón del lápiz,
Ajustes → Lápiz y dedo, y pellizcar en el panel táctil de un portátil.

## NVDA (lector de pantalla)

Con NVDA el cursor de lectura se enciende solo: lee «Página 1 de 39», línea a
línea, palabra a palabra y todo seguido; en un escaneado avisa de que no hay
texto.

## Memoria y pestañas dormidas

Abre 15 o 20 PDF, pon «Dormir las pestañas» en 5 minutos y mira en el
Administrador de tareas que baja la memoria; al volver a una pestaña aparece
al momento y lo escrito sin guardar sigue ahí. Déjalo en 15 minutos.

## Instalar, portátil y Windows

1. **Portátil:** se descomprime, abre sin instalar y crea su carpeta `datos`;
   al actualizarla la conserva.
2. **«Abrir con» y doble clic:** con el programa abierto, otro PDF entra como
   pestaña nueva; tres PDF a la vez quedan en una sola ventana.
3. **Pantalla al 125 % o 150 %:** todo nítido y del tamaño adecuado.
4. **Edge:** lo que se mira en Adobe debería verse igual en Edge (marcas,
   notas, formas, textos, hojas, márgenes, sellos y firmas).
5. **Exportar resumen a Word:** se abre en Word, con colores, y se puede
   editar.
