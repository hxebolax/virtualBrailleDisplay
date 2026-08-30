# Virtual Braille Display 2026.08.30

Complemento de NVDA que se registra como una **línea braille más** y guarda, byte a byte, lo que
NVDA entrega a `display(cells)`. Sirve para saber qué recibiría una línea braille real sin tener
una, y para comprobar si una aplicación expone información útil en braille.

Autor: Héctor J. Benítez Corredera · Licencia: GNU GPL versión 2 o posterior

---

## Índice

1. [Qué hace](#que-hace)
2. [Requisitos e instalación](#instalacion)
3. [Primeros pasos](#primeros-pasos)
4. [El submenú de Herramientas](#submenu)
5. [Gestos asignables](#gestos)
6. [El visor](#visor)
7. [La explicación sencilla](#explicacion-sencilla)
8. [Filtrar por una aplicación](#filtro)
9. [Navegar por las listas](#listas)
10. [Configuración](#configuracion)
11. [Privacidad y registro](#privacidad)
12. [Probar con aplicaciones externas](#aplicaciones-externas)
13. [Origen y confianza](#origen)
14. [Traducciones](#traducciones)
15. [Desarrollo](#desarrollo)
16. [Problemas frecuentes](#problemas)
17. [Limitaciones y hoja de ruta](#limitaciones)

---

<a id="que-hace"></a>

## Qué hace

Captura dos niveles de información y nunca los mezcla:

| Nivel | Qué es | Dónde se ve |
|---|---|---|
| **B — Frames** | Los bytes exactos que NVDA entrega a `display(cells)`. Es la fuente de verdad. | Historial de frames |
| **A — Eventos externos** | El texto que una aplicación pidió mostrar con `nvdaController_brailleMessage`. | Historial de eventos externos |

Cada frame guarda además **contexto** leído del propio NVDA justo antes de escribir: qué búfer lo
generó (navegación o mensaje), a qué está amarrada la línea, y el proceso, la aplicación, el
nombre y el rol del objeto que se estaba representando.

Nunca reconstruye el braille desde la voz, ni usa OCR, ni supone que el proceso enfocado es el
que llamó al Controller Client, ni inventa un PID.

<a id="instalacion"></a>

## Requisitos e instalación

Necesita **Windows** y **NVDA 2026.1 o posterior** (funciona con el módulo `braille` único de
2026.1 y con el paquete reorganizado de 2026.3). No requiere ninguna biblioteca externa. Los
ejemplos sí necesitan Python 3, `accessible-output2` y `wxPython`.

1. Abra `virtualBrailleDisplay-2026.08.30.nvda-addon` y confirme la instalación.
2. Reinicie NVDA.
3. En las opciones de braille de NVDA, seleccione **Virtual Braille Display** como pantalla braille.

<a id="primeros-pasos"></a>

## Primeros pasos

1. Asigne un gesto a **Abre el visor filtrado por la aplicación que tiene el foco**, en
   **Preferencias > Gestos de entrada > Virtual Braille Display**.
2. Ponga el foco en la aplicación que quiere revisar y pulse ese gesto: el complemento captura su
   PID y abre el visor mostrando sólo lo que produce ella.
3. Use la aplicación con normalidad; los frames van apareciendo en el historial.
4. Si no lee braille, pulse **Vista sencilla**: obtendrá el mismo dato explicado en español llano.

<a id="submenu"></a>

## El submenú de Herramientas

Todo está agrupado en **NVDA > Herramientas > Virtual Braille Display**:

| Elemento | Qué hace |
|---|---|
| Visor de frames y eventos… | Abre el visor técnico. |
| Explicación sencilla… | Abre la ventana en lenguaje llano. |
| Conectar la línea virtual | Selecciona Virtual Braille Display como pantalla braille. |
| Desconectar la línea virtual | Selecciona «sin braille» conservando los historiales. |
| Filtrar por la aplicación que tenía el foco | Filtra por la aplicación desde la que abrió el menú. |
| Quitar el filtro de aplicación | Vuelve a mostrar todas las aplicaciones. |
| Anunciar el último frame | Dice el texto y la ocupación del último frame. |
| Buscar traducciones y documentación nuevas | Descarga los recursos publicados desde la última versión. |
| Configuración… | Abre el diálogo con pestañas. |
| Ayuda del complemento | Abre esta documentación. |

Dos detalles pensados para que el menú funcione de verdad:

- **El filtro acierta con la aplicación.** Al abrir el menú el foco pasa al propio menú, que
  pertenece a NVDA. El complemento descarta ese PID y usa `gui.mainFrame.prevFocus`, el objeto
  que NVDA guarda al abrir un menú: exactamente la aplicación desde la que usted lo abrió.
- **Los avisos no se pierden.** Un `ui.message` emitido al cerrarse el menú lo cancela el anuncio
  de la ventana que recupera el foco. Los avisos del menú usan `ui.delayedMessage`, la función
  que NVDA ofrece para confirmar acciones del menú. Si prefiere no depender de la voz, en
  [Configuración](#configuracion) puede pedir un cuadro de mensaje.

<a id="gestos"></a>

## Gestos asignables

En **Preferencias > Gestos de entrada**, categoría **Virtual Braille Display**. Ninguno trae
tecla asignada de fábrica.

| Comando | Qué hace |
|---|---|
| Abre el visor de Virtual Braille Display | Abre el visor. Según la configuración, filtra antes por la aplicación enfocada o abre la vista sencilla. |
| Abre el visor filtrado por la aplicación que tiene el foco | Captura el PID de su aplicación y abre el visor limitado a ella. |
| Activa o desactiva el filtro por la aplicación que tiene el foco | Alterna el filtro sin abrir ninguna ventana. |
| Abre la explicación sencilla de la salida braille | Abre la ventana en lenguaje llano. |
| Anuncia el último frame recibido por la línea virtual | Dice el texto y la ocupación del último frame. |
| Busca traducciones y documentación nuevas del complemento | Comprueba si hay recursos nuevos sin esperar a la comprobación automática. |

<a id="visor"></a>

## El visor

Empieza con un **resumen de estado** enfocable con Tab: conexión, geometría, modo del visor,
filtro activo y número de frames y eventos. Debajo, siete pestañas:

| Pestaña | Contenido |
|---|---|
| Resumen amigable | Ocupación real del frame, origen y confianza, parte de NVDA que lo generó, aplicación representada, aplicación solicitante y PID, texto legible y su procedencia. |
| Datos técnicos exactos | Unicode Braille, hexadecimal, decimal, binario, puntos por celda y reparto por filas. |
| Historial de frames | Lista accesible con filtro de texto y desplegable de aplicación. Seleccionar una fila fija ese frame. |
| Eventos externos | Solicitudes recibidas por Controller Client, con PID, aplicación y frame correlacionado. |
| Comparación | Dos desplegables **Frame A** y **Frame B** con los últimos cien frames, más los atajos *Comparar los dos últimos*, *Comparar antepenúltimo con último* y *Usar el frame mostrado como B*. El resultado explica cuántas celdas cambian y, en cada una, patrón Unicode, puntos y valor hexadecimal. |
| Simulación de tamaño | Reparte el mismo buffer en las ventanas que mostraría una línea de 14, 20, 32, 40, 64 u 80 celdas. No traduce nada de nuevo: agrupa de otro modo las mismas celdas. |
| Interacción con la línea | Teclas de encaminamiento, desplazar atrás y adelante, y acordes braille de los puntos 1 a 8 más espacio. Se entregan a NVDA como gestos reales; requieren la línea conectada. |

Botones: **Conectar**, **Desconectar**, **Pausar actualizaciones** (sólo la interfaz; la captura
sigue), **Fijar frame mostrado**, **Actualizar ahora**, **Filtrar por aplicación enfocada**,
**Quitar filtro**, **Vista sencilla**, **Copiar**, **Guardar…**, **Limpiar**, **Configuración…**
y **Cerrar**.

Mientras el visor tiene el foco no se refresca solo, para no crear un bucle entre su propia
accesibilidad y la salida braille. Use **Actualizar ahora** para cargar una instantánea.

<a id="explicacion-sencilla"></a>

## La explicación sencilla

Ventana pensada para quien ve, no conoce braille y quiere que su aplicación sea accesible.
Muestra qué texto estaría leyendo una persona con línea braille, de dónde sale, de qué aplicación
y cuánto espacio ocupa; y debajo, una revisión automática:

| Observación | Qué significa |
|---|---|
| La línea braille se quedó en blanco | Nadie percibe nada. Suele ser un control sin nombre accesible o una ventana que no expone texto. |
| Hay puntos pero no se pudo recuperar el texto | Revise la tabla braille activa. |
| El contenido llena la línea completa | Probablemente el texto continúa y hay que desplazar la línea; ponga lo importante al principio. |
| El contenido casi llena la línea | En una línea de 14 o 20 celdas ya no cabría de una vez. |
| En una línea de 20 celdas ocuparía varias ventanas | Indica cuántos desplazamientos harían falta. |
| Procede de una solicitud de una aplicación externa | La atribución es probable, nunca confirmada. |
| No se pudo determinar el origen | Las celdas siguen siendo exactas; lo desconocido es qué parte de NVDA las produjo. |
| Sin aplicación identificada | Ni el contexto ni una solicitud externa aportaron un proceso, y no se deduce del foco. |

**Copiar informe** lleva todo el texto al portapapeles.

<a id="filtro"></a>

## Filtrar por una aplicación

Sirve para ver sólo lo que produce su programa. Hay tres formas: el gesto de teclado (la mejor,
porque el foco todavía es el de su aplicación), el submenú de Herramientas, y el desplegable
**Mostrar sólo la aplicación** del historial de frames.

El filtro compara con dos datos reales, nunca con una suposición: el PID de contexto del frame y
el PID confirmado por RPC de un evento externo correlacionado. Afecta al historial, la
comparación, las estadísticas, la exportación y la explicación sencilla, pero **no cambia el
origen ni la confianza** de ningún frame: es una decisión de visualización.

El botón *Filtrar por aplicación enfocada* dentro del visor avisa si no puede determinar la
aplicación, porque con el visor abierto el foco es el propio visor.

<a id="listas"></a>

## Navegar por las listas

NVDA ya lee la fila entera con las flechas arriba y abajo. El complemento añade el recorrido
celda a celda:

| Tecla | Acción |
|---|---|
| Flecha derecha / izquierda | Columna siguiente / anterior de la fila enfocada. |
| Ctrl+1 … Ctrl+9 | Salta directamente a esa columna. |
| Ctrl+Mayús+C | Copia el texto íntegro de la celda enfocada. |

Los anuncios usan `ui.message`, la función propia de NVDA, que habla y envía el texto a la línea
braille a la vez; no interviene ninguna biblioteca externa. Las listas guardan el texto
**completo** de cada celda, porque el control nativo de Windows recorta a unos 511 caracteres.

<a id="configuracion"></a>

## Configuración

Seis pestañas. Todos los controles se crean con `gui.guiHelper`, que sitúa la etiqueta antes
del control; ése es el orden que necesita un lector de pantalla para anunciar el nombre del campo
además de su valor.

| Pestaña | Opciones |
|---|---|
| **Línea braille** | Celdas por fila (14, 20, 32, 40, 64, 80 o personalizado de 1 a 256) y filas de la línea (1 a 40, para simular una línea multilínea). Al cambiarlas, NVDA reinicializa el driver y **recalcula de verdad** la salida braille. |
| **Captura e historial** | Frames y eventos conservados (10 a 10000); no guardar frames vacíos; no guardar frames repetidos; seguir el frame más reciente al abrir; abrir primero la vista sencilla; filtrar por la aplicación enfocada al abrir con un gesto. |
| **Correlación de orígenes** | Ventana de correlación (50 a 10000 ms) y ventana sólo temporal (0 a 2000 ms), que sólo se usa si no hay coincidencia de texto y existe un único candidato. |
| **Listas y avisos** | Qué se dice al recorrer columnas: número de fila, total de filas, nombre de columna, contenido, aviso de celda vacía, vuelta al final y anuncio sólo por voz. Y **avisos con el resultado de una acción**: voz y braille, cuadro de mensaje, o ambos. |
| **Actualizaciones** | Comprobar automáticamente al iniciar NVDA y horas entre comprobaciones. |
| **Registro y privacidad** | Registro continuo, su formato (JSON Lines o texto) y el archivo de destino. |

Si desactiva todas las opciones de lectura de columnas, se sigue diciendo el contenido de la
celda, para no dejar la navegación en silencio.

<a id="privacidad"></a>

## Privacidad y registro

El braille que recibe la línea puede contener contraseñas, documentos, mensajes y notificaciones.

- Los historiales viven **sólo en memoria** y desaparecen al cerrar NVDA.
- No se escribe nada en disco automáticamente.
- **Guardar…** exporta una instantánea en TXT, JSON o JSONL, en UTF-8 y tras una advertencia
  explícita. En JSONL cada registro lleva un campo `type` con valor `frame` o `externalEvent`.
- El **registro continuo** está desactivado de fábrica. Cuando se activa, escribe en un hilo
  aparte con una cola acotada: `display(cells)` sólo deposita el registro y sigue. Si el disco no
  sigue el ritmo se descartan registros y se lleva la cuenta, antes que ralentizar a NVDA.

Actívelo mientras depure y desactívelo después.

<a id="aplicaciones-externas"></a>

## Probar con aplicaciones externas

Funciona con aplicaciones ya existentes, sin modificarlas:

```python
from accessible_output2.outputs.auto import Auto

output = Auto()
output.braille("Descarga completada")
```

El recorrido es: la aplicación llama a `nvdaController_brailleMessage` en la DLL del Controller
Client → RPC → `NVDAHelper` encola `BrailleHandler.message(text)` → `TextRegion` y liblouis →
`_writeCells` notifica `pre_writeCells` → `display(cells)` en la línea virtual.

En `examples/` hay dos programas que se ejecutan **fuera** de NVDA:
`test_accessible_output2.py`, que comprueba que NVDA está activo y permite repetir mensajes, y
`wx_test_app.py`, una aplicación wxPython con botones para enviar a voz y braille o sólo a
braille. En la versión de `accessible_output2` analizada, `Auto.output` sólo habla; por eso los
ejemplos llaman a `braille(text)` explícitamente.

<a id="origen"></a>

## Origen y confianza

Cada frame lleva un origen y un nivel de confianza:

| Origen | Cuándo se usa |
|---|---|
| `NVDA_NAVIGATION` | El búfer activo era el principal y tenía regiones visibles. |
| `BRAILLE_MESSAGE` | El búfer activo era el de mensajes de NVDA. |
| `CORRELATED_EXTERNAL_MESSAGE` | Se correlacionó con una solicitud externa. |
| `UNKNOWN` | NVDA no aportó contexto suficiente. |

| Confianza | Qué significa exactamente |
|---|---|
| `CONFIRMED` | La identidad del búfer de NVDA es comprobable. Confirma **qué parte de NVDA** generó las celdas, nunca qué aplicación pidió el mensaje. |
| `PROBABLE` | Correlación por texto y tiempo con una solicitud externa. |
| `CONTEXT` | Sólo hay contexto; no se atribuye origen. |
| `UNKNOWN` | Sin determinar. |

**La distinción clave.** El visor muestra dos aplicaciones distintas y nunca las confunde:

- *Aplicación cuyo contenido se representaba*: contexto obtenido de `region.obj`. Responde a «de
  quién es el texto que se está mostrando».
- *Aplicación solicitante*: PID confirmado por `I_RpcBindingInqLocalClientPID` mientras se
  atendía la llamada RPC. Responde a «quién llamó a `nvdaController_brailleMessage`».

NVDA no transporta la identidad del cliente RPC hasta `display(cells)`. Por eso la identidad del
evento es confirmada, pero su asociación con un frame posterior es, como mucho, probable. El
detalle completo está en [`docs/origin-tracking.md`](docs/origin-tracking.md).

<a id="traducciones"></a>

## Traducciones

El complemento está escrito en español y admite traducciones a cualquier idioma. Lo importante:
**las traducciones y la documentación viajan aparte del complemento**, en una release de
recursos, de modo que llegan al usuario sin instalar una versión nueva.

**Si quiere traducirlo:** parta de `virtualBrailleDisplay.pot`, que está en la raíz del
repositorio, o de la plantilla ya preparada en `addon/locale/en/LC_MESSAGES/nvda.po`. Cree
`addon/locale/{idioma}/LC_MESSAGES/nvda.po` y envíelo. No hace falta compilar nada.

**Qué pasa después:** al fusionar el archivo, un flujo de trabajo de GitHub compila el `.po`,
genera el `manifest.ini` traducido y la documentación en HTML, lo empaqueta todo y lo publica en
la release de recursos. Aceptar una traducción se reduce a fusionar un archivo.

**Si usa el complemento:** comprueba si hay recursos nuevos al iniciar NVDA, como mucho una vez
al día. Puede cambiarlo o desactivarlo en **Configuración > Actualizaciones**, y comprobarlo
cuando quiera desde **Herramientas > Virtual Braille Display > Buscar traducciones y
documentación nuevas**. Sólo se descargan traducciones y documentación: nunca código.

La etiqueta de la release de recursos se calcula sola desde la versión del complemento: con
`2026.08.30` es `recursos_2026.08`. El flujo de trabajo y el complemento usan la misma regla, y
esa regla está cubierta por pruebas, así que no pueden desincronizarse.

El detalle completo, incluido qué conviene saber al traducir, está en
[`docs/traducciones.md`](docs/traducciones.md).

<a id="desarrollo"></a>

## Desarrollo

El código vive en `addon/globalPlugins/virtualBrailleDisplay/`, con el driver aparte en
`addon/brailleDisplayDrivers/virtualBraille.py`. Cada módulo tiene una responsabilidad: captura y
almacén (`runtime`, `frameStore`, `contextTracker`, `originTracker`, `controllerTracker`),
conversión y explicación (`brailleUtils`, `brailleDecoder`, `diagnostics`, `frameText`),
interfaz (`gui`, `simpleView`, `settingsDialog`, `accessibleList`, `guiUtils`, `messages`) y
apoyo (`config`, `models`, `logWriter`, `gestures`, `nvdaCompat`) y actualización de recursos
(`resourceUpdates`, más `actualizadorRecursos` sin modificar).

Compilar, y limpiar con `scons -c`:

```bash
scons
```

Pruebas, que no requieren NVDA:

```bash
python -m pytest tests -q
```

Estilo:

```bash
python -m ruff check .
```

Documentación técnica: [`docs/architecture.md`](docs/architecture.md) (flujo real y APIs de NVDA
utilizadas), [`docs/origin-tracking.md`](docs/origin-tracking.md) (qué se sabe, qué no y dónde se
pierde) y [`docs/traducciones.md`](docs/traducciones.md) (flujo completo de traducción) y
[`docs/testing.md`](docs/testing.md) (pruebas automáticas y 45 casos manuales).

<a id="problemas"></a>

## Problemas frecuentes

| Síntoma | Qué comprobar |
|---|---|
| No aparece ningún frame | Que **Virtual Braille Display** esté seleccionado en las opciones de braille y que el resumen de estado diga «Línea conectada». |
| El filtro no muestra nada | Probablemente se capturó el PID del visor. Pulse *Quitar filtro* y vuelva a capturarlo con el gesto desde su aplicación. |
| No llegan eventos externos | NVDA en ejecución, `accessible_output2` detectándolo, mensajes braille activados y llamada explícita a `braille(text)`. Si NVDA registra «API interna ausente», el hook no pudo instalarse en esa versión; la captura de frames sigue funcionando. |
| El encaminamiento o el acorde no hacen nada | Requieren la línea virtual conectada. |
| Se pierde un aviso del menú | No debería: usan `ui.delayedMessage`. Si ocurre, active el cuadro de mensaje en *Listas y avisos*. |
| NVDA no anuncia el nombre de un campo | Es un defecto, no una limitación: comuníquelo. |

<a id="limitaciones"></a>

## Limitaciones y hoja de ruta

- La traducción inversa que se ofrece cuando NVDA no aporta texto es **aproximada** y siempre se
  etiqueta como tal; nunca sustituye a las celdas.
- La asociación entre una solicitud externa y un frame es, como mucho, **probable**.
- El PID de contexto identifica la aplicación cuyo contenido se representaba, no necesariamente
  la que pidió el mensaje.
- El hook de Controller Client usa una API interna de NVDA. Si cambia, sólo se desactiva el
  historial de eventos externos.
- No hay dispositivo HID virtual: la línea existe dentro de NVDA.

Pendiente: protocolo cooperativo por IPC local para que una aplicación declare su PID y un
identificador de correlación antes de llamar al Controller Client, convirtiendo la atribución en
confirmada; un módulo auxiliar `virtual_braille_debug`; e investigación de un dispositivo HID
Braille virtual para Windows.
