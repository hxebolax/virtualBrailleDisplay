"""Lectura del contexto real de NVDA en el instante previo a escribir en el driver.

Toda la información obtenida aquí procede del propio subsistema braille de NVDA:
qué búfer estaba activo, a qué está amarrada la línea y a qué objeto pertenecen las
regiones que se están representando. Es información de CONTEXTO comprobable, no una
identificación del proceso que llamó al Controller Client.
"""

from __future__ import annotations

import weakref

import braille
from logHandler import log

from .models import BufferKind, FrameContext

# Número máximo de regiones inspeccionadas por frame para no penalizar la escritura.
MAXIMUM_INSPECTED_REGIONS = 8

# Última descripción calculada, para no repetir consultas mientras el objeto no cambia.
# El parpadeo del cursor de NVDA provoca varias escrituras por segundo sobre el mismo
# objeto, y leer su nombre o su rol puede implicar una consulta viva a la aplicación.
_lastObjectReference: weakref.ReferenceType[object] | None = None
_lastObjectDescription: tuple[int | None, str | None, str | None, str | None] = (None, None, None, None)


def _describeObject(sourceObject: object | None) -> tuple[int | None, str | None, str | None, str | None]:
	"""Devuelve PID, aplicación, nombre y rol reutilizando la última consulta del mismo objeto."""
	global _lastObjectReference, _lastObjectDescription
	if sourceObject is None:
		return None, None, None, None
	if _lastObjectReference is not None and _lastObjectReference() is sourceObject:
		return _lastObjectDescription
	description = (
		_readProcessId(sourceObject),
		_readApplicationName(sourceObject),
		_readObjectName(sourceObject),
		_readObjectRole(sourceObject),
	)
	try:
		_lastObjectReference = weakref.ref(sourceObject)
	except TypeError:
		# Algunos objetos no admiten referencias débiles; simplemente no se memoriza.
		_lastObjectReference = None
	_lastObjectDescription = description
	return description


def resetObjectCache() -> None:
	"""Olvida la última descripción memorizada, por ejemplo al descargar el complemento."""
	global _lastObjectReference, _lastObjectDescription
	_lastObjectReference = None
	_lastObjectDescription = (None, None, None, None)


def readCurrentContext(handlerCellCount: int | None = None) -> FrameContext:
	"""Obtiene el contexto actual del gestor braille sin propagar nunca una excepción."""
	try:
		return _readCurrentContext(handlerCellCount)
	except Exception:
		log.debugWarning("No se pudo leer el contexto braille de NVDA", exc_info=True)
		return FrameContext(handlerCellCount=handlerCellCount)


def _readCurrentContext(handlerCellCount: int | None) -> FrameContext:
	"""Implementa la lectura del contexto asumiendo que el llamador captura los errores."""
	handler = braille.handler
	if handler is None:
		return FrameContext(handlerCellCount=handlerCellCount)
	buffer = getattr(handler, "buffer", None)
	bufferKind = _classifyBuffer(handler, buffer)
	regions = _visibleRegions(buffer)
	sourceObject = _firstRegionObject(regions)
	processId, processName, objectName, objectRole = _describeObject(sourceObject)
	return FrameContext(
		bufferKind=bufferKind,
		tether=_readTether(handler),
		processId=processId,
		processName=processName,
		windowTitle=objectName,
		objectRole=objectRole,
		regionCount=len(regions),
		handlerCellCount=handlerCellCount,
	)


def _classifyBuffer(handler: object, buffer: object) -> BufferKind:
	"""Distingue el búfer de mensajes del búfer principal comparando identidades reales."""
	if buffer is None:
		return BufferKind.UNKNOWN
	if buffer is getattr(handler, "messageBuffer", None):
		return BufferKind.MESSAGE
	if buffer is getattr(handler, "mainBuffer", None):
		return BufferKind.MAIN
	return BufferKind.UNKNOWN


def _readTether(handler: object) -> str | None:
	"""Devuelve a qué está amarrada la línea (foco o revisión) si NVDA lo expone."""
	getTether = getattr(handler, "getTether", None)
	if getTether is None:
		return None
	try:
		return str(getTether())
	except Exception:
		return None


def _visibleRegions(buffer: object) -> tuple[object, ...]:
	"""Devuelve una tupla acotada con las regiones visibles del búfer activo."""
	if buffer is None:
		return ()
	try:
		regions = list(getattr(buffer, "visibleRegions", ()) or ())
	except Exception:
		regions = list(getattr(buffer, "regions", ()) or ())
	return tuple(regions[:MAXIMUM_INSPECTED_REGIONS])


def _firstRegionObject(regions: tuple[object, ...]) -> object | None:
	"""Devuelve el primer objeto de NVDA asociado a una región visible."""
	for region in regions:
		sourceObject = getattr(region, "obj", None)
		if sourceObject is not None:
			return sourceObject
	return None


def _readProcessId(sourceObject: object) -> int | None:
	"""Lee el PID del objeto, admitiendo intercepores de árbol que delegan en su objeto raíz."""
	for candidate in (sourceObject, getattr(sourceObject, "rootNVDAObject", None)):
		if candidate is None:
			continue
		try:
			processId = getattr(candidate, "processID", None)
		except Exception:
			processId = None
		if isinstance(processId, int) and processId > 0:
			return processId
	return None


def _readApplicationName(sourceObject: object) -> str | None:
	"""Lee el nombre del módulo de aplicación resuelto por NVDA para ese objeto."""
	for candidate in (sourceObject, getattr(sourceObject, "rootNVDAObject", None)):
		if candidate is None:
			continue
		try:
			appModule = getattr(candidate, "appModule", None)
			appName = getattr(appModule, "appName", None)
		except Exception:
			appName = None
		if appName:
			return str(appName)
	return None


def _readObjectName(sourceObject: object | None) -> str | None:
	"""Lee el nombre accesible del objeto sin permitir que un error rompa la captura."""
	if sourceObject is None:
		return None
	try:
		name = getattr(sourceObject, "name", None)
	except Exception:
		return None
	return str(name) if name else None


def _readObjectRole(sourceObject: object | None) -> str | None:
	"""Lee el rol del objeto en un texto legible cuando NVDA lo tiene ya calculado."""
	if sourceObject is None:
		return None
	try:
		role = getattr(sourceObject, "role", None)
	except Exception:
		return None
	if role is None:
		return None
	displayString = getattr(role, "displayString", None)
	return str(displayString or role)
