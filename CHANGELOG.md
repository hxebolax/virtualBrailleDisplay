# Historial de cambios

## 2026.08.30 — 30 de agosto de 2026

### Origen y contexto

- Nuevo `contextTracker`: cada frame guarda qué búfer de NVDA lo generó, el amarre de la línea
  y el proceso, la aplicación, el nombre y el rol del objeto cuyo contenido se representaba.
- La navegación normal y los mensajes braille dejan de aparecer como origen desconocido: se
  clasifican a partir de la identidad real del búfer de NVDA.
- El visor separa **aplicación cuyo contenido se representaba** de **aplicación solicitante**,
  para no confundir contexto con evidencia RPC.

### Filtro por aplicación

- Nuevo gesto que captura el PID de la aplicación enfocada en el instante de pulsarlo y abre el
  visor limitado a ella.
- Nuevo gesto para activar y desactivar ese filtro, y botones equivalentes en el visor.
- El filtro afecta a historial, comparación, estadísticas, exportación y explicación sencilla.

### Listas accesibles

- Nueva lista con navegación por columnas: flechas izquierda y derecha, Ctrl+1 a Ctrl+9 y
  Ctrl+Mayús+C para copiar la celda íntegra.
- Los anuncios usan `ui.message` de NVDA, sin ninguna biblioteca externa de voz.
- Es configurable qué se dice: número de fila, total de filas, nombre de columna, contenido,
  aviso de celda vacía, vuelta al final y anuncio sólo por voz.
- Las listas conservan el texto completo de cada celda, sin el recorte de Windows.

### Configuración

- Diálogo con pestañas: Línea braille, Captura e historial, Correlación de orígenes, Listas y
  lectura, y Registro y privacidad.
- Todos los controles se crean con `gui.guiHelper`, que sitúa la etiqueta antes del control.
  Con ello NVDA vuelve a anunciar el nombre del campo además de su valor.

### Nuevas herramientas

- **Explicación sencilla**: ventana en lenguaje llano, pensada para quien no conoce braille,
  con revisión automática de líneas en blanco, contenido recortado y datos no disponibles.
- **Comparación libre**: elección de los dos frames a comparar, con atajos para los dos últimos
  y para el antepenúltimo con el último.
- **Simulación de tamaño**: reparto del mismo buffer tal y como lo mostraría una línea de 14,
  20, 32, 40, 64 u 80 celdas.
- **Interacción con la línea**: teclas de encaminamiento, desplazamiento y acordes braille
  simulados como gestos reales de NVDA.
- **Filtro de texto** en el historial de frames.
- **Registro continuo** opcional en JSONL o texto, escrito en un hilo aparte y desactivado de
  fábrica.
- Gesto para anunciar el último frame sin abrir ninguna ventana.

### Menú

- Las dos entradas sueltas del menú Herramientas se sustituyen por un único submenú
  **Virtual Braille Display** con visor, explicación sencilla, conectar, desconectar, filtro por
  aplicación, anuncio del último frame, configuración y ayuda.
- La captura de la aplicación enfocada descarta el proceso de NVDA y recurre a
  `gui.mainFrame.prevFocus`, de modo que también funciona correctamente desde el menú.
- **Corregido**: los avisos lanzados desde el menú se perdían, porque al cerrarse el menú NVDA
  anuncia la ventana que recupera el foco y cancela la locución anterior. Ahora se emiten con
  `ui.delayedMessage`, la función que NVDA ofrece para confirmar acciones del menú.
- Nueva opción **Avisos con el resultado de una acción**: voz y braille, cuadro de mensaje o
  ambos, para quien no quiera depender de la voz.

### Traducciones y actualización de recursos

- Se integra [Actualizador-Recursos-NVDA](https://github.com/hxebolax/Actualizador-Recursos-NVDA):
  las traducciones y la documentación se publican en una release aparte y llegan al usuario sin
  instalar una versión nueva del complemento.
- Flujo de trabajo de GitHub que, al fusionar un `.po`, compila el `.mo`, genera el
  `manifest.ini` traducido y la documentación HTML, y publica el paquete de recursos.
- Etiqueta de recursos automática desde `addon_version`: con `2026.08.30` es `recursos_2026.08`,
  calculada igual en el flujo de trabajo y en el complemento.
- Plantilla `virtualBrailleDisplay.pot` y punto de partida en
  `addon/locale/en/LC_MESSAGES/nvda.po`.
- Nueva pestaña **Actualizaciones** en la configuración, con comprobación automática e intervalo.
- Nuevo elemento de menú y gesto para buscar recursos nuevos manualmente.
- Nuevo documento `docs/traducciones.md` con el flujo completo.
- Módulo `versioning.py` que calcula la etiqueta de recursos con la misma regla que el flujo de
  trabajo y la pasa explícitamente. Evita que una deducción fallida caiga en `recursos-latest`,
  una etiqueta inexistente que haría que el complemento dejase de buscar recursos en silencio.
- Corrección local del flujo de trabajo: buscaba `readme.md` en minúsculas, que en Linux no
  encuentra el `README.md` del repositorio.

### Documentación

- README reescrito: de 647 a 346 líneas, en 16 secciones en vez de 26, con la información
  repetida unificada y tablas en lugar de prosa.
- **Corregido**: los enlaces del índice no llevaban a ningún sitio. Los encabezados no reciben
  identificadores al convertirse a HTML, así que ahora cada sección lleva un ancla explícita en
  el Markdown, que funciona tanto en el HTML generado como al leer el archivo en cualquier visor.

### Línea braille

- Soporte de líneas multilínea mediante `numRows` y `numCols`, hasta 40 filas.
- Opciones para no guardar frames vacíos ni repetidos.

## 0.1.4 — 2026-08-30

- Añade una pestaña **Resumen amigable** y separa los datos avanzados en **Datos técnicos exactos**.
- Presenta texto exacto de NVDA, texto externo o traducción inversa aproximada, indicando siempre la fuente.
- Evita la realimentación del visor reteniendo actualizaciones automáticas mientras su ventana tiene el foco.
- Añade **Actualizar ahora** para inspeccionar instantáneas estables.
- Renombra los botones dinámicos para distinguir pausa de actualizaciones y fijación de frames.
- Convierte el estado de línea, tamaño y modo en información accesible mediante Tab.
- Añade nombres y descripciones accesibles a las dos listas.
- Traduce orígenes y niveles de confianza a explicaciones en español.
- Reescribe la comparación con resumen, textos anterior/actual y descripción de patrones y puntos.
- Añade pruebas de traducción inversa para NVDA 2026.1 y 2026.3.

## 0.1.3 — 2026-08-30

- El foco inicial del diálogo de configuración comienza en **Número de celdas** y no en **Aceptar**.
- Cada cuadro combinado y campo numérico recibe un nombre accesible derivado de su etiqueta.
- NVDA anuncia ahora nombre, valor y tipo de control al navegar con Tab.
- Las etiquetas siguen el patrón estándar y no se convierten en paradas de Tab independientes.

## 0.1.2 — 2026-08-30

- Corrige la carga en NVDA 2026.1.1, donde `braille` todavía es un módulo único.
- Añade una capa localizada para seleccionar `braille.BrailleDisplayDriver` y `braille.pre_writeCells` en 2026.1.
- Conserva las rutas `braille.display.driver` y `braille.extensions` de NVDA 2026.3.
- Declara como versión mínima real NVDA 2026.1.
- Añade pruebas automáticas de ambas arquitecturas de imports.

## 0.1.1 — 2026-08-30

- Añade a cada frame el texto legible de la ventana braille proporcionado por NVDA.
- Muestra ese texto en el frame actual y en el historial de frames.
- Incluye el texto legible al copiar y al exportar TXT, JSON o JSONL.
- Verifica mediante pruebas caracteres UTF-8, incluidos acentos, eñe y euro.
- Mantiene `display(cells)` como fuente de verdad; no realiza traducción inversa ambigua.

## 0.1.0 — 2026-08-30

- Driver braille virtual seleccionable con tamaños de 1 a 256 celdas.
- Captura exacta de `display(cells)` con marcas de tiempo de pared y monotónicas.
- Visor wx accesible con Unicode, hexadecimal, decimal, binario y puntos braille.
- Historial independiente de frames y eventos externos, limitado a 1000 por defecto.
- Comparación de celdas cambiadas, añadidas y eliminadas.
- Pausa del visor y congelación de frame sin detener la captura.
- Conexión y desconexión lógica; reinicialización al cambiar el tamaño.
- Exportación manual TXT, JSON y JSONL con advertencia de privacidad.
- Hook localizado y reversible para `nvdaController_brailleMessage`, con PID RPC y ejecutable del cliente cuando están disponibles.
- Correlación textual/temporal marcada siempre como probable, nunca confirmada.
- Aplicaciones de prueba de consola y wxPython mediante accessible-output2.
- Pruebas unitarias para conversiones, historial, comparación, correlación y logs.
