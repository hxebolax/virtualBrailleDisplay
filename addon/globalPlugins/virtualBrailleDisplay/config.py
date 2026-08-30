"""Configuración persistente del complemento mediante el sistema de NVDA."""

from __future__ import annotations

from typing import Any

import config as nvdaConfig

from .brailleUtils import validateCellCount

CONFIG_SECTION = "virtualBrailleDisplay"

DEFAULT_CELL_COUNT = 40
DEFAULT_ROW_COUNT = 1
DEFAULT_HISTORY_LIMIT = 1000
DEFAULT_CORRELATION_WINDOW_MS = 1500
DEFAULT_TEMPORAL_FALLBACK_MS = 250

# Cada entrada usa la sintaxis de validación de ConfigObj que emplea NVDA.
# Se mantiene una única definición para evitar valores predeterminados duplicados.
CONFIG_SPEC = {
	# Línea braille virtual.
	"cellCount": "integer(default=40, min=1, max=256)",
	"rowCount": "integer(default=1, min=1, max=40)",
	# Historiales y correlación.
	"historyLimit": "integer(default=1000, min=10, max=10000)",
	"correlationWindowMs": "integer(default=1500, min=50, max=10000)",
	"temporalFallbackMs": "integer(default=250, min=0, max=2000)",
	# Lectura de las listas con navegación por columnas.
	"listAnnounceRowNumber": "boolean(default=True)",
	"listAnnounceColumnHeader": "boolean(default=True)",
	"listAnnounceCellValue": "boolean(default=True)",
	"listAnnounceTotalRows": "boolean(default=False)",
	"listAnnounceEmptyCells": "boolean(default=True)",
	"listWrapColumns": "boolean(default=False)",
	"listSpeakOnly": "boolean(default=False)",
	# Cómo se entregan los avisos con el resultado de una acción.
	"actionAnnouncementMode": "option('speech', 'dialog', 'both', default='speech')",
	# Comportamiento del visor.
	"followLatestFrame": "boolean(default=True)",
	"openSimpleViewFirst": "boolean(default=False)",
	"ignoreEmptyFrames": "boolean(default=False)",
	"ignoreRepeatedFrames": "boolean(default=False)",
	"filterFocusedApplication": "boolean(default=False)",
	# Actualización de traducciones y documentación desde GitHub.
	"resourceUpdatesEnabled": "boolean(default=True)",
	"resourceUpdateIntervalHours": "integer(default=24, min=1, max=168)",
	# Registro continuo, siempre desactivado de fábrica por privacidad.
	"continuousLogging": "boolean(default=False)",
	"continuousLogFormat": "option('jsonl', 'txt', default='jsonl')",
	"continuousLogPath": "string(default='')",
}

# Límites aplicados al validar cada entero, para no repetirlos en cada asignación.
_INTEGER_LIMITS = {
	"cellCount": (1, 256),
	"rowCount": (1, 40),
	"historyLimit": (10, 10000),
	"correlationWindowMs": (50, 10000),
	"temporalFallbackMs": (0, 2000),
	"resourceUpdateIntervalHours": (1, 168),
}


def initializeConfig() -> None:
	"""Registra la especificación para que NVDA valide y persista los valores."""
	nvdaConfig.conf.spec[CONFIG_SECTION] = CONFIG_SPEC


def getValue(key: str) -> Any:
	"""Devuelve un valor persistido después de garantizar que la sección existe."""
	initializeConfig()
	return nvdaConfig.conf[CONFIG_SECTION][key]


def getBoolean(key: str) -> bool:
	"""Devuelve una opción booleana ya normalizada."""
	return bool(getValue(key))


def setBoolean(key: str, value: bool) -> None:
	"""Guarda una opción booleana comprobando que la clave existe en la especificación."""
	if key not in CONFIG_SPEC:
		raise KeyError(f"Opción desconocida: {key}")
	initializeConfig()
	nvdaConfig.conf[CONFIG_SECTION][key] = bool(value)


def getInteger(key: str) -> int:
	"""Devuelve una opción entera ya normalizada."""
	return int(getValue(key))


def setInteger(key: str, value: int) -> None:
	"""Guarda una opción entera comprobando los límites declarados."""
	if key not in _INTEGER_LIMITS:
		raise KeyError(f"Opción entera desconocida: {key}")
	minimum, maximum = _INTEGER_LIMITS[key]
	numeric = int(value)
	if not minimum <= numeric <= maximum:
		raise ValueError(f"«{key}» debe estar entre {minimum} y {maximum}")
	initializeConfig()
	nvdaConfig.conf[CONFIG_SECTION][key] = numeric


def getText(key: str) -> str:
	"""Devuelve una opción de texto ya normalizada."""
	return str(getValue(key) or "")


def setText(key: str, value: str) -> None:
	"""Guarda una opción de texto comprobando que la clave existe."""
	if key not in CONFIG_SPEC:
		raise KeyError(f"Opción desconocida: {key}")
	initializeConfig()
	nvdaConfig.conf[CONFIG_SECTION][key] = str(value or "")


def getCellCount() -> int:
	"""Devuelve el número de celdas por fila configurado."""
	return validateCellCount(getInteger("cellCount"))


def setCellCount(value: int) -> None:
	"""Guarda un tamaño de línea ya validado."""
	setInteger("cellCount", validateCellCount(value))


def getRowCount() -> int:
	"""Devuelve el número de filas simuladas de la línea virtual."""
	return getInteger("rowCount")


def setRowCount(value: int) -> None:
	"""Guarda el número de filas de una línea braille multilínea simulada."""
	setInteger("rowCount", value)


def getHistoryLimit() -> int:
	"""Devuelve el límite de entradas de cada historial."""
	return getInteger("historyLimit")


def setHistoryLimit(value: int) -> None:
	"""Guarda el límite del historial dentro del intervalo configurado."""
	setInteger("historyLimit", value)


def getCorrelationWindowMilliseconds() -> int:
	"""Devuelve la ventana máxima para buscar un evento externo relacionado."""
	return getInteger("correlationWindowMs")


def setCorrelationWindowMilliseconds(value: int) -> None:
	"""Guarda la ventana de correlación principal en milisegundos."""
	setInteger("correlationWindowMs", value)


def getTemporalFallbackMilliseconds() -> int:
	"""Devuelve la ventana corta usada cuando no coincide el texto."""
	return getInteger("temporalFallbackMs")


def setTemporalFallbackMilliseconds(value: int) -> None:
	"""Guarda la ventana de correlación exclusivamente temporal."""
	setInteger("temporalFallbackMs", value)


def getListAnnouncementOptions() -> dict[str, bool]:
	"""Agrupa las opciones que deciden qué se anuncia al recorrer las columnas."""
	return {
		"rowNumber": getBoolean("listAnnounceRowNumber"),
		"columnHeader": getBoolean("listAnnounceColumnHeader"),
		"cellValue": getBoolean("listAnnounceCellValue"),
		"totalRows": getBoolean("listAnnounceTotalRows"),
		"emptyCells": getBoolean("listAnnounceEmptyCells"),
		"wrapColumns": getBoolean("listWrapColumns"),
		"speakOnly": getBoolean("listSpeakOnly"),
	}
