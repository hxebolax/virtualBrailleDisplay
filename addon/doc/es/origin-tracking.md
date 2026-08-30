# Seguimiento del origen

## Qué se conoce con certeza

El hook se instala en el puntero de función que `NVDAHelper.initialize` asigna a `_nvdaController_brailleMessage`. Cuando entra en el wrapper, se sabe de forma confirmada que hubo una llamada a la API Controller Client y se conoce su argumento de texto.

Ese registro es un `ExternalBrailleEvent` independiente. Su confianza `CONFIRMED` sólo confirma **la existencia de la solicitud**, no que un frame posterior proceda de ella.

## Cómo se obtiene la identidad del cliente

La interfaz RPC actual declara:

```c
error_status_t __stdcall brailleMessage([in,string] const wchar_t* message);
```

El callback Python correspondiente declara:

```python
@WINFUNCTYPE(c_long, c_wchar_p)
def nvdaController_brailleMessage(text):
    ...
```

No hay parámetro de PID, ejecutable ni ID de correlación en la firma. La función `nvdaController_getProcessId` de la API cliente obtiene el PID de **NVDA**, no el proceso llamante.

Sin embargo, el wrapper se ejecuta todavía en el hilo que atiende la llamada RPC. En ese punto transitorio consulta `winBindings.rpcrt4.I_RpcBindingInqLocalClientPID(None, ...)`, la misma vinculación presente en NVDA, y obtiene el PID del cliente local. Después resuelve el nombre con `appModuleHandler.getAppNameFromProcessID(pid, includeExt=True)`. Ambos datos se guardan en el evento antes de delegar al callback original.

El PID se considera confirmado cuando RPC devuelve éxito. El ejecutable es el nombre resuelto por NVDA para ese PID. Si la consulta RPC falla, devuelve un PID no válido o el proceso ya no puede resolverse, los campos correspondientes quedan vacíos: el complemento nunca los deduce del foco ni inventa una identidad.

La identidad sólo existe en el `ExternalBrailleEvent`. Después, el núcleo encola únicamente `braille.handler.message` y `text`; `TextRegion`, `BrailleBuffer` y `display(cells)` no reciben el PID ni un ID de correlación. Por eso la identidad del evento es confirmada, pero su asociación con un frame posterior sigue siendo probable.

El proceso enfocado no se usa como sustituto. NVDA consulta el foco para respetar el modo de reposo, pero eso no demuestra qué proceso hizo la llamada RPC.

## Cómo se correlaciona

1. El hook registra el evento externo con tiempo monotónico.
2. El callback original encola `BrailleHandler.message(text)`.
3. `pre_writeCells` aporta `rawText` y las celdas previas a la normalización del driver. Se encuentra en `braille` en NVDA 2026.1 y en `braille.extensions` en NVDA 2026.3.
4. El correlador busca eventos no asociados dentro de una ventana limitada.
5. Prefiere coincidencia textual exacta; admite coincidencia parcial cuando una ventana larga está truncada o desplazada.
6. Sólo usa proximidad temporal sin texto si existe exactamente un candidato dentro de una ventana corta.
7. `display(cells)` comprueba que las celdas coincidan con `pre_writeCells`, permitiendo sólo el recorte o relleno cero que hace NVDA.

Incluso con todas esas evidencias el resultado es `PROBABLE`, porque otra actualización podría intercalarse entre colas. Si hay candidatos ambiguos o buffers incompatibles, el origen queda `UNKNOWN`.

`rawText` se conserva además como **texto legible asociado** aunque no exista ningún evento externo. Este dato describe el texto de la ventana que NVDA relaciona con las celdas, pero no confirma el origen del frame. Si el contexto y el buffer final no son compatibles, tampoco se reutiliza ese texto.

Cuando faltan tanto `rawText` como texto externo, el visor puede presentar una traducción inversa aproximada. Esa ayuda no cambia el origen ni la confianza del frame y nunca se almacena como evidencia confirmada.

## Concurrencia y mensajes repetidos

- Los eventos se ordenan por IDs y tiempo monotónico.
- Un evento elegido queda reservado hasta el siguiente `display` del mismo hilo.
- Para textos exactos repetidos se consume primero el evento pendiente más antiguo, siguiendo el orden de la cola.
- Dos eventos recientes con texto no coincidente impiden la correlación exclusivamente temporal.
- Una actualización de foco que produzca otro buffer no hereda la atribución si las celdas no coinciden.

## Punto privado y restauración

NVDA no ofrece un punto de extensión público específico para Controller Client braille messages. `braille.extensions._pre_showBrailleMessage` es privado, no aporta texto y también cubre otros mensajes. Interceptar `BrailleHandler.message` mezclaría mensajes internos con externos.

Por eso se usa como último recurso `NVDAHelper._setDllFuncPointer` para redirigir sólo `_nvdaController_brailleMessage`. El componente:

- comprueba que los símbolos existan;
- impide parches duplicados;
- consulta el PID mientras conserva el contexto de la llamada RPC;
- delega en el callback original y devuelve su código;
- mantiene vivo el callback `WINFUNCTYPE`;
- restaura el puntero original en `terminate`;
- no modifica ningún archivo del núcleo de NVDA.

Si una versión futura cambia los símbolos del callback, el driver y la captura de nivel B siguen funcionando; únicamente se desactiva el historial de eventos externos y NVDA registra una advertencia. Si cambia o falla la consulta RPC, los eventos todavía se capturan con texto, pero sin PID ni ejecutable.

## Identificación cooperativa futura

Una aplicación propia podría enviar antes un mensaje por named pipe local con PID, `applicationId`, texto y `correlationId`. Esa información permitiría una asociación explícita cuando se diseñe un protocolo autenticado y con límites. No forma parte de 0.1.0 y no es necesaria para capturar aplicaciones existentes.

## Contexto de aplicación por frame

Además del origen, cada frame guarda un bloque de **contexto** obtenido dentro de
`pre_writeCells`, cuando el búfer que produjo las celdas todavía está montado:

| Campo | Procedencia exacta en NVDA |
|---|---|
| `bufferKind` | Comparación de identidad entre `handler.buffer`, `handler.mainBuffer` y `handler.messageBuffer`. |
| `tether` | `braille.handler.getTether()`. |
| `contextProcessId` | `region.obj.processID` de la primera región visible del búfer. |
| `contextProcessName` | `region.obj.appModule.appName`. |
| `contextWindowTitle` | `region.obj.name`. |
| `contextObjectRole` | `region.obj.role.displayString`. |
| `regionCount` | Número de regiones visibles inspeccionadas, hasta ocho. |

Ese PID responde a la pregunta «¿de qué aplicación es el contenido que NVDA estaba
representando?». **No** responde a «¿qué proceso llamó a `nvdaController_brailleMessage`?».

Son preguntas distintas y el complemento nunca las mezcla:

- Un mensaje del Controller Client crea una `TextRegion` sin objeto asociado, de modo que el
  contexto no aporta PID. La identidad del cliente sólo llega por el
  `ExternalBrailleEvent` con el PID de RPC.
- Un frame de navegación sí tiene objeto y, por tanto, contexto de aplicación, pero no hubo
  ninguna llamada externa que atribuir.

Por eso el visor muestra dos campos separados: **aplicación cuyo contenido se representaba**
(contexto) y **aplicación solicitante** (evidencia RPC del evento externo).

## Filtro por aplicación elegido por el usuario

El complemento ofrece un gesto que captura el PID de la aplicación enfocada **en el momento en
que el usuario pulsa la tecla**, antes de mostrar ninguna ventana propia. Ese PID se usa para
filtrar lo que se muestra en el visor.

Esto no contradice la regla de no confundir foco con proceso llamante:

- el PID no se escribe en el frame ni cambia su origen ni su confianza;
- es una decisión explícita del usuario sobre qué quiere ver;
- el filtro compara con el PID de contexto y con el PID confirmado de un evento externo
  correlacionado, nunca con una suposición.

Al abrir el visor con el gesto, el foco todavía pertenece a la aplicación del usuario. Si se
pulsa el botón equivalente ya dentro del visor, la aplicación enfocada es el propio visor: la
interfaz lo advierte explícitamente en lugar de guardar un dato engañoso.
