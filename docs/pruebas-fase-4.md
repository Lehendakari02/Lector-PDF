# Pruebas de la Fase 4 – Firma con certificado digital

Lo que solo se puede comprobar con tu certificado de verdad. Ve marcando lo que
funcione y dime lo que no.

## Tarea 4.1 – Firmar con el certificado instalado en Windows (FNMT)

1. Abre un PDF cualquiera y, en el modo Rellenar y firmar, pulsa **Firmar con
   certificado**. Haz clic en la página donde quieres la firma (desde la
   tarea 4.3; ver más abajo).
2. Sale la lista de certificados de Windows: tu certificado FNMT debe estar
   elegido. Los del propio ordenador salen apagados.
3. Pulsa **Firmar con este**. Windows te pide la contraseña o el PIN en su
   propia ventana (si lo instalaste con protección).
4. Acepta el nombre «…-firmado.pdf». El documento firmado se abre en una
   pestaña nueva y el aviso dice "firmado por" tu nombre.
5. Sube el firmado a **VALIDe** (valide.redsara.es → Validar firma) y ábrelo
   con **Adobe Reader**: los dos deben dar la firma por válida. Si Adobe dice
   que "la identidad del firmante es desconocida", es normal hasta que Adobe
   confíe en la FNMT; dime qué pone exactamente.
6. Escribe algo en un documento sin guardar y firma: pregunta "Guardar y
   firmar", y lo escrito sale en el firmado.
7. Firma a mano un documento (Firmar → Poner mi firma), guárdalo como
   «-firmado» y luego fírmalo con certificado: se firma en su sitio, sin otra
   copia, y sigue en la misma página.
8. Firma otra vez otro documento: tu certificado ya sale elegido.
9. Pulsa Cancelar en la ventana del PIN de Windows: dice "Firma cancelada" y
   no se crea nada.

## Tarea 4.2 – Firmar con un archivo .p12 o .pfx

1. Usa la copia de tu certificado que guardaste al instalarlo (el archivo
   .pfx con contraseña).
2. Firmar con certificado → **Usar un archivo .p12 o .pfx…** → elige el
   archivo y escribe su contraseña.
3. El firmado debe salir válido en VALIDe y Adobe, igual que en la 4.1.
4. Vuelve a firmar otro documento: sale un botón «Usar «tu-archivo.pfx»»;
   solo pide la contraseña.
5. Pon mal la contraseña: dice que lo compruebes y no firma.


## Tarea 4.3 – Firma visible o invisible y sello de tiempo

1. Firmar con certificado: al pasar el ratón por la página sale un recuadro
   azul discontinuo. Haz clic donde quieras la firma.
2. El firmado muestra un recuadro con tu firma manuscrita a la izquierda (si
   la tienes guardada) y a la derecha "Firmado digitalmente por", tu nombre y
   la fecha. Míralo también en Adobe y en Edge: debe verse igual.
3. Prueba en una página girada (Organizar → girar, guardar y firmar): el
   recuadro sale derecho.
4. Pulsa Esc en vez de hacer clic: no se firma nada.
5. **Ajustes → Firma**:
   - "Invisible": al firmar ya no pide sitio; la firma solo se ve en el
     panel de firmas de Adobe.
   - Quita "Poner mi firma manuscrita en el recuadro": el recuadro solo lleva
     el texto.
   - Activa "Añadir un sello de tiempo": firma un documento y súbelo a VALIDe;
     debe decir que tiene sello de tiempo (dime qué pone). En Adobe, en las
     propiedades de la firma, sale "La firma incluye un sello de hora".
   - Con el sello activado, desconecta internet y firma: avisa y ofrece
     "Firmar sin sello de tiempo".

## Tarea 4.4 – Firmar varios documentos de una vez

1. Copia 10 PDF cualesquiera en una carpeta.
2. **Archivo → Firmar varios documentos…** → Añadir documentos… → elige los 10.
3. Deja "Visible, en la última página" y "Abajo a la derecha" y pulsa
   **Firmar 10 documentos**. Elige tu certificado.
4. **Lo importante:** dime cuántas veces te pide Windows el PIN o la
   contraseña. Lo ideal es una; con algunos certificados Windows lo pide en
   cada firma y eso no lo decide el programa.
5. Al terminar dice "Firmados 10 de 10" y en la carpeta hay diez
   «…-firmado.pdf». Abre un par: el recuadro está abajo a la derecha de la
   última página. Súbelos a VALIDe.
6. Repite con tu archivo .pfx: la contraseña se pone una sola vez.
7. Mete en la lista un PDF con contraseña: dice que ese no se ha podido y
   firma los demás.

## Tarea 4.5 – Firmar con el DNIe

Necesitas un lector de tarjetas y el PIN del DNIe.

1. Conecta el lector y mete el DNIe. Si Windows no lo reconoce, instala el
   controlador de dnielectronico.es (Descargas → Windows).
2. Firmar con certificado: si la lista no muestra el DNIe, pulsa
   **Actualizar**. Deben salir dos con la marca "DNIe": el de FIRMA elegido y
   el de AUTENTICACIÓN apagado.
3. Pulsa **Firmar con este**: Windows pide el PIN del DNIe. Sube el firmado a
   VALIDe.
4. Prueba "Firmar varios documentos" con el DNIe: dime cuántas veces pide el
   PIN.
5. Si el DNIe no aparece en la lista ni con Actualizar, dímelo: hay un plan B.

## Tarea 4.6 – Ver y comprobar firmas

1. Abre un PDF firmado por ti (de las pruebas anteriores): abajo dice que
   está firmado.
2. Rellenar y firmar → **Comprobar firmas**: debe decir ✔ "Firma válida",
   tu nombre, "AC FNMT Usuarios" (o la del DNIe) y la fecha.
3. Abre algún PDF firmado que te haya llegado de fuera (una nómina, un
   certificado de la administración…) y compara con lo que dice Adobe.
4. Añade una nota a un PDF firmado y pulsa Guardar: avisa de que la firma
   dejará de valer. Guarda una copia y comprueba la copia: sale ✖ "Firma
   rota". Es lo esperado hoy (el programa reescribe el archivo entero al
   guardar; ver la revisión de la Fase 4). Con un PDF al que otro programa
   añadió notas sí debe salir ✔ y "después se añadieron notas".
5. Si en algún caso sale ⚠ o ✖ y Adobe o VALIDe dicen que está bien, dime
   cuál.

## Tarea 4.8 – Arreglos de la revisión de la Fase 4

1. **PIN equivocado al firmar varios** (con el DNIe ten cuidado: tres PIN mal
   lo bloquean; prueba esto con tu certificado FNMT si su clave tiene
   contraseña). Firmar varios documentos, 3 documentos, y pon mal el PIN o la
   contraseña la primera vez: el lote **se para** y dice "El PIN o la
   contraseña no es correcto". No vuelve a pedirlo para los demás.
2. Saca la tarjeta del lector y firma: dice "Mete la tarjeta en el lector".
3. **La ventana del PIN de Windows** sale delante del programa, no detrás.
4. **PDF con restricciones:** uno que se abre sin contraseña pero no deja
   imprimir o copiar (muchos de la administración). Firmar con certificado:
   ahora firma. Ábrelo en Adobe: la firma es válida y sigue protegido.
5. **PDF con contraseña:** ábrelo en el programa con su contraseña y firma: el
   firmado sigue pidiendo la misma contraseña. Si es un PDF hecho con este
   mismo programa u otros basados en MuPDF, puede decir que no se puede
   firmar tal cual (limitación conocida).
6. **Página girada:** firma un escaneado con páginas giradas: el recuadro sale
   justo donde haces clic.
7. **Formulario con un campo de texto «Firma1»** (frecuente en formularios
   oficiales): ahora firma.
8. **Sin ratón:** Firmar con certificado → Intro: la firma va abajo a la
   derecha de la página que ves.
9. En Ajustes → Firma escribe otro servidor de sellos y cierra con Esc:
   al volver sigue el que escribiste.
