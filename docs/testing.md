# Pruebas

## Pruebas unitarias automatizadas

Comando:

```powershell
python -m unittest discover -s tests -t . -v
```

La suite cubre:

- los 256 desplazamientos byte -> Unicode Braille;
- cada bit -> punto 1 a 8;
- hexadecimal, decimal, binario y puntos activos;
- valores y tamaños inválidos;
- historial acotado, limpieza e IDs;
- comparación de cambios, adiciones y eliminaciones;
- serialización TXT, JSON y JSONL;
- correlación exacta, ambigüedad temporal, buffer incompatible, relleno y recorte.
- instalación/restauración del hook, delegación al callback original y captura de PID/ejecutable RPC.
- conservación del texto legible sin evento externo y exportación UTF-8 con caracteres no ASCII.
- imports de la clase base, de los gestos y de `pre_writeCells` en las arquitecturas 2026.1 y 2026.3.
- traducción inversa aproximada mediante liblouis en NVDA 2026.1 y mediante `louisHelper` moderno.
- lectura, validación y persistencia de todas las opciones declaradas en `CONFIG_SPEC`.
- filtrado del historial por proceso, enumeración de procesos observados y estadísticas.
- observaciones del diagnóstico: línea en blanco, línea llena, ocupación real y ausencia de proceso.
- reparto del mismo buffer en ventanas de otro tamaño sin perder ni alterar ningún byte.
- registro continuo en JSONL y en texto, formatos rechazados, carpeta inexistente y parada limpia.

Resultado de la ejecución de la versión 2026.08.30: **64 pruebas superadas**.

## Lista de pruebas manuales

1. Seleccionar `Virtual Braille Display` y navegar por controles: deben aparecer frames con origen desconocido.
2. Ejecutar `examples/test_accessible_output2.py` y enviar braille: debe aparecer un evento Controller Client con PID/ejecutable y un frame probable.
3. Ejecutar `examples/wx_test_app.py`: probar ambos botones.
4. Ejecutar dos instancias y enviar mensajes distintos rápidamente: no debe atribuirse un frame cuando haya ambigüedad.
5. Cambiar el foco mientras llega un mensaje: el frame incompatible debe quedar desconocido.
6. Cambiar la tabla de salida de NVDA y repetir el mismo texto: comparar bytes.
7. Cambiar de 40 a 20 celdas: comprobar reinicialización y nuevo frame de 20 bytes.
8. Desconectar, enviar un mensaje, reconectar y verificar que el historial anterior permanece.
9. Pausar y congelar: comprobar que los IDs siguen avanzando.
10. Exportar cada formato y revisar la advertencia de privacidad.
11. Navegar por texto con acentos o símbolos y comprobar que **Texto legible asociado** coincide y se conserva al exportar en UTF-8.
12. Abrir Configuración: el foco debe caer en el cuaderno de pestañas; al tabular, NVDA debe anunciar el nombre y el valor de cada control, incluido **Celdas por fila**, y no detenerse separadamente en las etiquetas.
13. Recorrer Resumen amigable, Datos técnicos, las dos listas, Comparación, Simulación e Interacción; cada control debe anunciar su propósito.
14. Mantener el foco dentro del visor y comprobar que no crea un bucle de frames visible; usar **Actualizar ahora** para cargar una instantánea.
15. Comparar dos frames y comprobar que se anuncien textos anterior/actual, resumen y cambios de puntos en español.
16. En una lista, moverse con flecha derecha e izquierda: NVDA debe anunciar fila, columna y contenido según la configuración; en los extremos debe avisar de primera o última columna salvo que esté activada la vuelta.
17. Pulsar Ctrl+1 a Ctrl+9 en una lista: debe anunciarse directamente la columna correspondiente y avisarse si no existe.
18. Desactivar en Configuración el número de fila y la cabecera: al recorrer columnas sólo debe decirse el contenido.
19. Activar «Anunciar sólo por voz» y comprobar que la línea braille deja de recibir los anuncios de columna.
20. Pulsar Ctrl+Mayús+C sobre una celda y comprobar que se copia su texto íntegro, no el recortado por Windows.
21. Desde una aplicación cualquiera, pulsar el gesto **Abre el visor filtrado por la aplicación que tiene el foco**: NVDA debe anunciar el nombre y el PID capturados y el visor debe mostrar sólo frames de ese proceso.
22. Con el filtro activo, usar otra aplicación y comprobar que sus frames no aparecen; pulsar **Quitar filtro** y comprobar que vuelven a verse.
23. Pulsar el botón **Filtrar por aplicación enfocada** desde dentro del visor: debe advertir de que la aplicación enfocada es el propio visor.
24. En Comparación, elegir Frame A y Frame B en los desplegables y comparar; probar también **Comparar los dos últimos** y **Comparar antepenúltimo con último**.
25. Seleccionar un frame en el historial, pulsar **Usar el frame mostrado como B** y comparar.
26. En Simulación de tamaño, elegir 20 celdas con un frame largo y comprobar cuántas ventanas harían falta.
27. Poner 2 o más filas en Configuración, comprobar que NVDA reinicializa el driver y que **Reparto por filas** muestra el contenido dividido.
28. En Interacción, indicar una celda y simular la tecla de encaminamiento: el cursor debe desplazarse en la aplicación.
29. En Interacción, marcar puntos 1, 2 y 5 y enviar el acorde en un campo de edición: NVDA debe escribir el carácter correspondiente.
30. Usar **Desplazar atrás** y **Desplazar adelante** con un texto más largo que la línea.
31. Abrir la **explicación sencilla** con un frame en blanco: debe aparecer el aviso de que la línea se queda vacía.
32. Abrir la explicación sencilla con un texto que llene la línea: debe avisar de un posible recorte.
33. Activar el registro continuo con un archivo JSONL, generar frames, desactivarlo y comprobar el contenido del archivo.
34. Activar «No guardar frames vacíos» y «No guardar frames repetidos» y comprobar que el historial deja de crecer con actualizaciones redundantes.
35. Pulsar el gesto **Anuncia el último frame recibido** sin abrir ninguna ventana.
36. Abrir **NVDA > Herramientas**: debe haber un único submenú **Virtual Braille Display**, no elementos sueltos, y recorrerlo con las flechas debe anunciar cada elemento.
37. Desde el submenú, usar **Conectar la línea virtual** y **Desconectar la línea virtual**: NVDA debe anunciar el resultado de cada acción.
38. Desde una aplicación cualquiera, abrir el submenú y elegir **Filtrar por la aplicación que tenía el foco**: debe anunciar el nombre y el PID de esa aplicación, nunca los de NVDA.
39. Desde el submenú, abrir **Configuración…** y comprobar que el diálogo se comporta como modal y que al cerrarlo el foco vuelve a su sitio.
40. Desde el submenú, abrir **Ayuda del complemento** y comprobar que se muestra la documentación instalada.
41. Desactivar el complemento en el Almacén de complementos y comprobar que el submenú desaparece por completo del menú Herramientas.
42. Elegir **Conectar la línea virtual** en el submenú y comprobar que el aviso se escucha **entero** después de que NVDA anuncie la ventana que recupera el foco, sin quedar cortado.
43. Repetir la comprobación con **Desconectar**, **Filtrar por la aplicación que tenía el foco**, **Quitar el filtro** y **Anunciar el último frame**.
44. Poner en **Configuración > Listas y avisos** el modo «Mostrarlos en un cuadro de mensaje» y comprobar que las acciones del menú abren un cuadro en vez de hablar.
45. Poner el modo «Las dos cosas» y comprobar que se hace lo uno y lo otro.

## Condiciones necesarias para mensajes externos

- NVDA debe estar ejecutándose.
- El backend de accessible-output2 debe detectar NVDA.
- NVDA debe tener habilitado el informe braille de regiones dinámicas.
- Los mensajes braille no deben estar desactivados.
- Debe usarse `braille(text)` explícitamente con la versión de `Auto` analizada.

Las pruebas unitarias no sustituyen la prueba dentro de un proceso NVDA real; validan las piezas puras y las reglas que evitan atribuciones falsas.
