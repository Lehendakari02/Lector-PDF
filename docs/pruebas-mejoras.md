# Pruebas de las mejoras pendientes (P.1 a P.5)

Para probar en Windows con el `.exe` de prueba o con la versión publicada que
las lleve. Cada paso: lo que haces → lo que debe pasar.

## P.1 Letras de otros idiomas en los cuadros de texto

1. Abre un PDF, modo **Estudiar → Texto** y escribe en la página
   «Ἀθῆναι, Москва, Việt, H₂O, x², ½» → se ve tal cual en la página.
2. Escribe otro texto igual y ponlo en **negrita** (botón N) → las letras
   griegas y rusas también salen en negrita.
3. Guarda (Ctrl+S) y abre el PDF en **Edge** → los dos textos se ven igual
   que en el programa, sin «?» ni cuadraditos.
4. Ábrelo en **Adobe Reader** → igual.
5. En Adobe, busca «Москва» (Ctrl+F) con «Incluir comentarios» marcado en
   las opciones de búsqueda (lo escrito encima es un comentario) → lo encuentra.

## P.2 Pestañas dormidas

1. Abre 15 o 20 PDFs a la vez (por ejemplo, todos los temas). Abre el
   **Administrador de tareas** (Ctrl+Mayús+Esc) y apunta cuánta memoria gasta
   «Lector PDF» (sumando sus procesos).
2. Para probar rápido: **Ajustes → General → Memoria** → «Dormir las pestañas
   que no miro tras» **5 minutos**.
3. Quédate en una pestaña sin cambiar de otra durante 6 minutos → en el
   Administrador de tareas hay muchos menos procesos «Lector PDF» y la
   memoria baja mucho.
4. Pulsa una pestaña de las de antes → aparece al momento en su página y en
   un instante se ve nítida; puedes pasar páginas, buscar y subrayar como
   siempre.
5. Escribe algo en una pestaña, **sin guardar** pasa a otra y espera a que se
   duerma; vuelve → lo escrito sigue ahí y **Deshacer** (Ctrl+Z) lo quita.
6. Vuelve a dejar el ajuste en 15 minutos (o apágalo si lo prefieres).

## P.3 Zoom muy alto

1. Abre un temario escaneado (o el BOE) y sube el zoom al **800 %** con la
   barra de abajo a la derecha → en un instante la letra se ve nítida, no
   estirada ni borrosa.
2. Muévete por la página con la rueda y arrastrando la barra → la zona nueva
   sale primero un poco borrosa y enseguida nítida; nada se queda en blanco.
3. Con ese zoom, subraya una palabra → el subrayado aparece sin parpadeos.
4. En el **Administrador de tareas**, la memoria de «Lector PDF» no se dispara
   (antes una sola página a este zoom gastaba unos 170 MB).

## P.4 Elegir las teclas

1. **Ajustes** (Ctrl+,) → pestaña **Teclado** → sale la lista de todas las
   funciones con su tecla.
2. Escribe «subrayar» en el buscador → solo queda «Subrayar», con la S.
3. Doble clic en «Subrayar» y pulsa **U** → la ventana dice «Libre…»;
   pulsa **Poner esta** → en la lista sale U y «Subrayar» en cursiva.
4. Cierra Ajustes, selecciona texto en un PDF y pulsa **U** → se subraya.
5. Vuelve a **Teclado**, doble clic en «Dibujar» y pulsa **R** → la ventana
   avisa «Ahora es de «Resaltar»…»; pulsa **Poner esta** → abajo dice que se
   ha quitado de «Resaltar». Con el documento delante, R coge el lápiz.
6. Doble clic en «Resumen» (o cualquier función sin tecla) y pulsa
   **Ctrl+Mayús+R** → funciona aunque estés escribiendo en el buscador.
7. Prueba **Ctrl++** y **Ctrl+-** → acercan y alejan.
8. Pulsa **Restablecer todas** → vuelven las de siempre (R resalta, S subraya).

## P.5 El lector de pantalla lee las páginas (cursor de lectura)

Sin lector de pantalla:

1. Abre el BOE de prueba y pulsa **F7** → abajo dice «Cursor de lectura
   activado» y sale una barra roja fina al principio del texto.
2. Flechas → la barra se mueve letra a letra y línea a línea; **Mayús+flechas**
   selecciona (se ve azul en la página) y **R** lo resalta.
3. Baja con la flecha hasta el final de la página → sigue en la siguiente.
   **Av Pág** / **Re Pág** cambian de página.
4. Un clic en otra parte → la barra va allí. **F7** otra vez → se quita.

Con NVDA (gratis en nvaccess.org):

5. Arranca NVDA y abre el programa → el cursor de lectura se activa solo.
   Entra en el documento (clic en la página) → NVDA dice «Página 1 de 39» y
   la primera línea.
6. Flechas arriba y abajo → lee línea a línea; **Ctrl+flechas** palabra a
   palabra; **NVDA+flecha abajo** lee todo seguido. Al pasar de página dice
   «Página 2 de 39».
7. Abre un PDF escaneado → dice que la página no tiene texto y que se puede
   reconocer.
8. Ajustes → General → Accesibilidad: quita «Activarlo solo si uso un lector
   de pantalla», cierra y vuelve a abrir el programa con NVDA → no se activa
   (F7 lo activa).
