# Arquitectura técnica

## Fuentes analizadas

La implementación se diseñó contra copias locales, sin volver a clonarlas:

- NVDA 2026.1.1, etiqueta local `release-2026.1.1`, commit `5d92106f17e461dac62aa48257bbbf4183e033d0`.
- NVDA, commit `77973a3015e9a58dc8638d9a6dc61b9f60e853b4`, árbol 2026.3dev.
- AddonTemplate, commit `30318eae085fa81fe3a39045956c7a0516a0f981`.
- BrailleExtender, brailleEssentials, rdAccess, BRLTTY, HID-braille-ESP32 y el Braille Viewer histórico.
- Backend oficial de accessible-output2 consultado porque no estaba clonado localmente.

## Flujo real de Controller Client

```text
Aplicación externa
  accessible_output2.outputs.nvda.NVDA.braille(text)
        |
        v
nvdaControllerClient32/64.dll
  nvdaController_brailleMessage(const wchar_t *message)
        |
        v
RPC nvdaController (nvdaHelperLocal.dll)
        |
        | I_RpcBindingInqLocalClientPID -> PID/ejecutable del cliente
        v
source/NVDAHelper/__init__.py
  nvdaController_brailleMessage(text)
        |
        | queueHandler.queueFunction(eventQueue, braille.handler.message, text)
        v
braille.brailleHandler.BrailleHandler.message(text)
        |
        | TextRegion(text); Region.update()
        | louisHelper.translate(...)
        v
BrailleBuffer.update() / BrailleHandler.update()
        |
        | windowBrailleCells + cursor + padding
        v
BrailleHandler._writeCells(cells)
        |
        | pre_writeCells(cells, rawText, currentCellCount)
        | normalización al tamaño del driver
        v
brailleDisplayDrivers.virtualBraille.BrailleDisplayDriver.display(cells)
        |
        v
FrameStore -> visor / historial / exportación manual
```

### Funciones y clases concretas

1. `accessible_output2/outputs/nvda.py`, `NVDA.braille`: invoca `self.lib.nvdaController_brailleMessage(text)`.
2. `nvdaHelper/interfaces/nvdaController/nvdaController.idl`: define `brailleMessage([in,string] const wchar_t* message)`.
3. `source/NVDAHelper/__init__.py`, `nvdaController_brailleMessage`: comprueba el modo de reposo del foco y `config.conf["braille"]["reportLiveRegions"]`; encola `braille.handler.message`.
4. `source/braille/brailleHandler.py`, `BrailleHandler.message`: crea `TextRegion`, actualiza la región y el buffer de mensajes.
5. `source/braille/regions/base.py`, `Region.update`: llama a `louisHelper.translate` con la tabla activa y produce `brailleCells`.
6. `source/braille/brailleHandler.py`, `BrailleHandler.update`: toma `windowBrailleCells`, asigna `self._rawText = self.buffer.windowRawText`, añade blancos y conserva la posición del cursor.
7. `BrailleHandler._writeCells`: notifica `pre_writeCells` con celdas, `rawText` y tamaño; después normaliza filas/celdas y llama al driver.
8. `BrailleDisplayDriver.display`: recibe la colección final que constituye el nivel B.

## Componentes del complemento

| Componente | Responsabilidad |
|---|---|
| `virtualBraille.py` | Driver real y seleccionable; copia el argumento de `display`. |
| `frameStore.py` | Historiales acotados, IDs, timestamps, formatos derivados, filtrado y estadísticas. |
| `brailleUtils.py` | Conversión byte/Unicode/puntos, comparación y reparto en ventanas. |
| `brailleDecoder.py` | Traducción inversa aproximada y bajo demanda fuera del camino crítico. |
| `controllerTracker.py` | Hook reversible del callback nativo; captura texto, PID RPC y ejecutable. |
| `contextTracker.py` | Lectura del búfer, el amarre y el objeto de NVDA representados en cada frame. |
| `originTracker.py` | Correlación textual y temporal conservadora, y clasificación por búfer. |
| `diagnostics.py` | Explicación en lenguaje humano y detección de problemas de accesibilidad. |
| `frameText.py` | Elección del texto legible del frame indicando siempre su procedencia. |
| `gestures.py` | Teclas de encaminamiento y acordes braille simulados como gestos reales. |
| `runtime.py` | Estado compartido, `pre_writeCells`, filtro por aplicación y conexión del driver. |
| `gui.py` | Visor wx accesible con historiales, comparación, simulación e interacción. |
| `simpleView.py` | Ventana explicada en lenguaje llano para desarrolladores no usuarios de braille. |
| `settingsDialog.py` | Configuración con pestañas construida con `gui.guiHelper`. |
| `accessibleList.py` | Listas con navegación por columnas anunciada mediante `ui.message`. |
| `guiUtils.py` | Ayudantes que garantizan el orden etiqueta-control exigido por los lectores. |
| `logWriter.py` | Exportación manual TXT/JSON/JSONL y registro continuo en un hilo aparte. |
| `nvdaCompat.py` | Selección localizada de las APIs braille equivalentes de NVDA 2026.1 y 2026.3. |

### Contexto capturado por frame

`contextTracker.readCurrentContext` se ejecuta dentro de `pre_writeCells`, es decir, mientras
NVDA todavía tiene montado el búfer que ha producido las celdas. Obtiene:

- si el búfer activo es `handler.mainBuffer` o `handler.messageBuffer`;
- el resultado de `handler.getTether()`;
- el primer `region.obj` de `buffer.visibleRegions` y, a partir de él, `processID`,
  `appModule.appName`, nombre y rol.

Con esa evidencia el origen deja de ser desconocido en la navegación normal: un frame del
búfer de mensajes se clasifica como `BRAILLE_MESSAGE` y uno del búfer principal como
`NVDA_NAVIGATION`. La confianza `CONFIRMED` de esos dos casos se refiere exclusivamente a
**qué parte de NVDA generó las celdas**, nunca a qué aplicación pidió el mensaje.

Toda la lectura está protegida: cualquier excepción devuelve un contexto vacío y el frame se
captura igualmente, porque las celdas son la fuente de verdad y nunca deben perderse.

El nombre y el rol del objeto se memorizan con una referencia débil al último objeto
consultado. El parpadeo del cursor de NVDA provoca varias escrituras por segundo sobre el mismo
objeto y esas propiedades pueden implicar una consulta viva a la aplicación; con la memoria
sólo se consultan cuando el objeto cambia realmente.

## `display(cells)` y rendimiento

`display` no traduce texto, no consulta el foco, no escribe archivos y no toca controles wx. Entrega la colección a `RuntimeState.captureDisplay`, que:

1. consume un pequeño contexto ya preparado por `pre_writeCells`;
2. copia los valores a `bytes`;
3. asigna ID, tiempo de pared, `perf_counter_ns` e ID de hilo;
4. materializa formatos de un máximo configurado de 256 celdas;
5. añade el frame a una `deque` protegida por `RLock`;
6. notifica observadores ligeros.

El contexto consumido del mismo hilo conserva también `rawText`. NVDA lo documenta como el texto sin traducir que corresponde a las celdas y, en el flujo actual, procede de `BrailleBuffer.windowRawText`. El complemento lo guarda como `associatedText` y no reemplaza a los bytes finales.

Python mantiene este valor como Unicode. La GUI lo presenta directamente y las exportaciones TXT, JSON y JSONL lo codifican con UTF-8 y sin escapar innecesariamente caracteres en JSON.

Si `rawText` y el texto externo no están disponibles, `brailleDecoder.backTranslateCells` puede producir una ayuda aproximada con la tabla activa. En NVDA 2026.3 usa `louisHelper.backTranslate`; en 2026.1 adapta directamente `louis.backTranslate`. Esta operación sólo se ejecuta al presentar, copiar o comparar un frame, nunca en `display`, y el resultado se etiqueta como aproximado.

Mientras el visor tiene el foco, descarta sus notificaciones automáticas de presentación, pero no los frames almacenados. Esto corta el ciclo visor -> accesibilidad de wx -> salida braille -> visor. El botón **Actualizar ahora** obtiene una instantánea explícita y estable.

El visor agrupa notificaciones y encola como máximo un `wx.CallAfter` pendiente. Toda E/S se ejecuta únicamente al pulsar Guardar.

El driver declara `isThreadSafe = False`. En este caso NVDA llama inmediatamente a `display` después de `pre_writeCells`, lo que evita perder la relación de ese contexto y evita el mecanismo de coalescencia que descarta escrituras intermedias para drivers en segundo plano. La operación se mantiene acotada y sin E/S.

## Cambio de geometría

El tamaño se guarda en `virtualBrailleDisplay.cellCount` y el número de filas en
`virtualBrailleDisplay.rowCount`. Si el driver está activo, `RuntimeState.applyDisplayGeometry`
cambia temporalmente a `noBraille` como fallback y vuelve a seleccionar `virtualBraille`. El
nuevo constructor fija `numCols` y `numRows`; NVDA reconstruye dimensiones, buffer, ventana y
traducción. No se corta una cadena ya capturada.

Para líneas de más de una fila, `BrailleDisplayDriver` de NVDA prohíbe asignar `numCells` y
exige `numCols` y `numRows`, que es lo que hace el driver.

## Registro continuo

`logWriter.ContinuousLogger` mantiene un hilo escritor y una cola acotada. `display(cells)`
sólo serializa el registro y lo deposita en la cola; si la cola se llena se descartan
registros y se lleva la cuenta, en lugar de bloquear el subsistema braille de NVDA. El
registro está desactivado de fábrica y la interfaz avisa de que puede contener datos privados.

## Gestos simulados

`gestures.RouteToGesture` reproduce una tecla de encaminamiento con `source = "virtualBraille"`,
`id = "route"`, `cellIndexes` y el script `globalCommands.commands.script_braille_routeTo`, el
mismo esquema que usa el Braille Viewer de NVDA. `gestures.DotsInputGesture` hereda de
`BrailleDisplayGesture` y `BrailleInputGesture`, fija `dots` y `space` y compone su
identificador con `_makeDotsId()`, igual que los drivers reales con teclado braille. Ambos se
entregan con `inputCore.manager.executeGesture`, de modo que NVDA los procesa exactamente
igual que si procedieran de una línea física.

## APIs utilizadas

### Extensiones y APIs estables observadas

- NVDA 2026.1: `braille.BrailleDisplayDriver`, `braille.BrailleDisplayGesture`,
  `brailleInput.BrailleInputGesture` y `braille.pre_writeCells.register/unregister`.
- NVDA 2026.3: `braille.display.driver.BrailleDisplayDriver`,
  `braille.display.gesture.BrailleDisplayGesture`, `braille.input.gesture.BrailleInputGesture`
  y `braille.extensions.pre_writeCells.register/unregister`.
- `braille.handler.buffer`, `mainBuffer`, `messageBuffer`, `visibleRegions` y `getTether`.
- `braille.handler.scrollForward` y `braille.handler.scrollBack`.
- `inputCore.manager.executeGesture` y `globalCommands.commands.script_braille_routeTo`.
- `api.getFocusObject` y `api.copyToClip`.
- `ui.message` y `speech.speakMessage` para anunciar la navegación por columnas.
- `gui.guiHelper` (`BoxSizerHelper`, `ButtonHelper`, `associateElements`).
- `gui.message.MessageDialog`, `DialogType`, `DefaultButton` y `ReturnCode`.
- `addonHandler.initTranslation`.
- `globalPluginHandler.GlobalPlugin`.
- `scriptHandler.script`.
- wxPython suministrado por NVDA.

`nvdaCompat.py` intenta primero la organización moderna. Si esos imports no existen, utiliza exclusivamente los nombres equivalentes comprobados en la etiqueta local de NVDA 2026.1.1. No modifica `sys.path`, no parchea módulos y no oculta errores ajenos a esa reorganización.

### APIs internas o privadas

- `NVDAHelper._setDllFuncPointer`.
- `NVDAHelper.localLib.dll` y el símbolo de datos `_nvdaController_brailleMessage`.
- `winBindings.rpcrt4.I_RpcBindingInqLocalClientPID` para consultar al cliente mientras se atiende la llamada RPC.
- `appModuleHandler.getAppNameFromProcessID` para resolver el ejecutable del PID confirmado.
- `braille.handler.setDisplayByName`, incluido el argumento `isFallback`.

Todas las APIs privadas están encapsuladas. El hook se valida, evita una instalación doble, mantiene una referencia fuerte al callback de `ctypes` y restaura el puntero original al descargar el complemento. Un fallo al consultar o resolver el proceso deja esos campos vacíos y no impide que el callback original continúe.

## accessible-output2

El backend oficial usa `nvdaController_testIfRunning`, `nvdaController_speakText`, `nvdaController_cancelSpeech` y `nvdaController_brailleMessage`, cargando una DLL de 32 o 64 bits según el intérprete. `Auto.get_first_available_output` escoge el primer backend activo. En la versión inspeccionada, `Auto.output` sólo llama a `speak`; por eso las pruebas llaman a `braille` explícitamente.
