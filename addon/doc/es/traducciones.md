# Traducciones y actualización de recursos

El complemento está escrito en español. Las traducciones a otros idiomas y la documentación se
publican **aparte del complemento**, en una release de recursos, de modo que llegan al usuario
sin tener que instalar una versión nueva.

---

## Para quien traduce

### 1. Obtener la plantilla

En la raíz del repositorio está `virtualBrailleDisplay.pot`, generado con:

```bash
scons pot
```

Contiene todas las cadenas traducibles del complemento, con la referencia al archivo y la línea
en que aparece cada una.

### 2. Crear el archivo del idioma

Cree `addon/locale/{idioma}/LC_MESSAGES/nvda.po` a partir de la plantilla. El código de idioma
es el que usa NVDA: `en`, `fr`, `de`, `pt_BR`, `zh_TW`…

Como punto de partida hay una plantilla ya preparada en
`addon/locale/en/LC_MESSAGES/nvda.po`, con la cabecera rellena y todas las cadenas sin traducir.

Puede editarla con Poedit, con Lokalize o con cualquier editor de texto.

### 3. Comprobar y enviar

Antes de enviar, compruebe que el archivo es válido:

```bash
msgfmt --check -o NUL addon/locale/es/LC_MESSAGES/nvda.po
```

Envíelo como *pull request* o hágalo llegar al autor. **No hace falta enviar el `.mo`
compilado**: lo genera el flujo de trabajo automáticamente.

### Qué conviene saber al traducir

- Los marcadores entre llaves, como `{frameId}` o `{count}`, deben conservarse tal cual.
- El carácter `&` marca la tecla de acceso rápido de un botón o de un elemento de menú. Colóquelo
  delante de una letra que no choque con las demás de ese mismo diálogo.
- Las cadenas con `ngettext` tienen forma singular y plural; complete ambas.
- Los saltos de línea `\n` de los textos explicativos mantienen la anchura de los párrafos en los
  diálogos: consérvelos donde tengan sentido en su idioma.
- El texto de `buildVars.py` (resumen, descripción y registro de cambios) también se traduce y
  aparece en el Almacén de complementos de NVDA.

---

## Qué ocurre al enviar una traducción

Al llegar el archivo a la rama principal, el flujo de trabajo
`.github/workflows/compilar_idiomas.yml` se ejecuta solo y hace lo siguiente:

1. Compila cada `.po` a `.mo` con `msgfmt`.
2. Genera un `manifest.ini` traducido por idioma, usando `manifest-translated.ini.tpl` y las
   cadenas de `buildVars.py`.
3. Copia el `README.md` de la raíz a `addon/doc/es/readme.md`.
4. Convierte a HTML todos los `.md` de `addon/doc/{idioma}/`, con el título traducido, el idioma
   correcto y la hoja de estilos.
5. Copia `style.css` a `addon/doc/`.
6. Calcula un hash combinado de todos los recursos y lo guarda en `addon/recursos_info.json`.
7. Empaqueta todo en `virtualBrailleDisplay_recursos.zip`.
8. Publica ese ZIP en una release marcada como *prerelease*, con la etiqueta de recursos.
9. Vuelve a subir al repositorio los archivos compilados.

Todo el proceso es automático. Para el mantenedor, aceptar una traducción se reduce a fusionar el
archivo `.po`.

---

## La etiqueta de recursos

La etiqueta se calcula **automáticamente** a partir de `addon_version`, tomando sus dos primeros
componentes numéricos:

| Versión del complemento | Etiqueta de recursos |
|---|---|
| `2026.08.30` | `recursos_2026.08` |
| `2026.09.15` | `recursos_2026.09` |

Ese mismo cálculo lo hacen el flujo de trabajo y el complemento en tiempo de ejecución, de modo
que no hay que configurar la etiqueta en dos sitios ni pueden desincronizarse.

La consecuencia práctica es útil: el tercer número queda libre para correcciones que no cambian
textos ni documentación. Puede publicar `2026.08.31` sin generar una release de recursos nueva, y
los usuarios seguirán recibiendo los recursos de `recursos_2026.08`.

Si algún día quisiera fijar una etiqueta manualmente, tendría que definirla **a la vez** en
`TAG_RELEASE` del flujo de trabajo y en el parámetro `tag_release` del constructor de
`ActualizadorRecursos`. Si no coinciden, la API de GitHub devuelve 404 y el complemento deja de
buscar recursos en silencio. Por eso se usa el modo automático.

---

## Para quien usa el complemento

El complemento comprueba si hay recursos nuevos al iniciar NVDA, como mucho una vez cada 24
horas. Ambas cosas se pueden cambiar en **Configuración > Actualizaciones**, y la comprobación
automática se puede desactivar.

En cualquier momento se puede comprobar manualmente desde **Herramientas > Virtual Braille
Display > Buscar traducciones y documentación nuevas**, o con el gesto *Busca traducciones y
documentación nuevas del complemento*.

Sólo se descargan traducciones y documentación: **nunca código**. Cuando se instala algo nuevo, el
complemento lo dice y recuerda que conviene reiniciar NVDA para aplicarlo por completo. Si no hay
nada nuevo, la comprobación automática no dice nada.

---

## Compilación local

Para compilar los recursos sin esperar al flujo de trabajo:

```bash
python scons_idiomas.py
```

Opciones útiles: `--solo-idiomas`, `--solo-docs`, `--sin-manifest` y `--sin-html`.

El complemento completo se compila con `scons`, que también genera los `.mo` y la documentación
HTML dentro del `.nvda-addon`.

---

## Archivos implicados

| Archivo | Papel |
|---|---|
| `virtualBrailleDisplay.pot` | Plantilla con todas las cadenas traducibles. |
| `addon/locale/{idioma}/LC_MESSAGES/nvda.po` | Traducción de un idioma. Es lo único que envía un traductor. |
| `addon/locale/{idioma}/LC_MESSAGES/nvda.mo` | Compilado; lo genera el flujo de trabajo. |
| `addon/locale/{idioma}/manifest.ini` | Resumen y descripción traducidos; lo genera el flujo de trabajo. |
| `addon/doc/{idioma}/*.md` y `*.html` | Documentación por idioma. |
| `manifest-translated.ini.tpl` | Plantilla del manifest traducido. |
| `scons_idiomas.py` | Compilación local equivalente a la del flujo de trabajo. |
| `addon/globalPlugins/virtualBrailleDisplay/actualizadorRecursos.py` | Módulo que descarga e instala los recursos. |
| `addon/globalPlugins/virtualBrailleDisplay/resourceUpdates.py` | Integración del módulo anterior con este complemento. |

`actualizadorRecursos.py` y `scons_idiomas.py` proceden de
[Actualizador-Recursos-NVDA](https://github.com/hxebolax/Actualizador-Recursos-NVDA) y se
mantienen **sin modificar**, para poder actualizarlos sobrescribiéndolos. Por eso están excluidos
de las comprobaciones de estilo en `pyproject.toml`.
