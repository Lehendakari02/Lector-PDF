# Primer prompt (para pegar al empezar el hilo de construcción)

Vamos a construir **Lector-PDF**, un lector, editor y firmador de PDF para Windows.
Antes de hacer nada, lee enteros:
- `CLAUDE.md`: qué es el programa, principios, decisiones tomadas y forma de trabajar.
- `PLAN.md`: el plan por fases y tareas, con cómo comprobar cada una.

El plan ya se ha revisado a fondo (versión 0.5 de `CLAUDE.md`). Si aun así ves algo
que no tenga sentido, sea técnicamente arriesgado o se pueda mejorar, dímelo en un
mensaje corto antes de empezar; solo lo nuevo, sin repetir lo que ya está escrito.

Sobre mí: no sé programar. Tú programas todo; yo dirijo, pruebo en mi Windows y
decido. Háblame en español sencillo, sin jerga.

Empieza por la **Fase 0** (cimientos), tarea a tarea en el orden de `PLAN.md`, cada
una en su propia rama con su pull request:
- 0.1 a 0.5: estructura, pruebas automáticas en Windows en GitHub Actions, `.exe` de
  prueba en cada pull request, PDFs de prueba, esqueleto de la interfaz con los modos
  y registro de errores.
- 0.6 a 0.9: las cuatro pruebas de concepto (rendimiento, buscador, firma con el
  certificado del almacén de Windows y OCR con Tesseract incluido). Son para confirmar
  que la tecnología aguanta antes de seguir: si alguna falla o es más difícil de lo
  previsto, explícamelo con alternativas antes de continuar.

Al terminar cada tarea, dime qué has hecho, cómo lo pruebo (dónde descargo el `.exe`
y qué hago) y qué sigue. Cuando esté toda la Fase 0, espera mi confirmación antes de
pasar a la Fase 1.
