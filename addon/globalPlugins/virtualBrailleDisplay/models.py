"""Modelos de datos inmutables y serializables del complemento."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OriginType(str, Enum):
	"""Enumera los orígenes que el complemento puede representar sin inventar datos."""

	UNKNOWN = "UNKNOWN"
	NVDA_NAVIGATION = "NVDA_NAVIGATION"
	CONTROLLER_CLIENT = "CONTROLLER_CLIENT"
	BRAILLE_MESSAGE = "BRAILLE_MESSAGE"
	CORRELATED_EXTERNAL_MESSAGE = "CORRELATED_EXTERNAL_MESSAGE"


class OriginConfidence(str, Enum):
	"""Enumera el grado de confianza de una atribución de origen."""

	UNKNOWN = "UNKNOWN"
	CONTEXT = "CONTEXT"
	PROBABLE = "PROBABLE"
	CONFIRMED = "CONFIRMED"


class BufferKind(str, Enum):
	"""Distingue qué búfer del subsistema braille de NVDA produjo el frame."""

	UNKNOWN = "UNKNOWN"
	MAIN = "MAIN"
	MESSAGE = "MESSAGE"


@dataclass(frozen=True, slots=True)
class FrameContext:
	"""Contexto observado en NVDA justo antes de escribir en el driver.

	Es información de CONTEXTO verificable dentro de NVDA (qué búfer estaba activo y a qué
	objeto pertenecían las regiones braille). Nunca identifica al proceso que llamó al
	Controller Client: para eso existe :class:`ExternalBrailleEvent`.
	"""

	bufferKind: BufferKind = BufferKind.UNKNOWN
	tether: str | None = None
	processId: int | None = None
	processName: str | None = None
	windowTitle: str | None = None
	objectRole: str | None = None
	regionCount: int = 0
	handlerCellCount: int | None = None

	def toDictionary(self) -> dict[str, Any]:
		"""Devuelve una copia serializable del contexto."""
		return {
			"bufferKind": self.bufferKind.value,
			"tether": self.tether,
			"contextProcessId": self.processId,
			"contextProcessName": self.processName,
			"contextWindowTitle": self.windowTitle,
			"contextObjectRole": self.objectRole,
			"regionCount": self.regionCount,
			"handlerCellCount": self.handlerCellCount,
		}


@dataclass(frozen=True, slots=True)
class FrameOrigin:
	"""Describe el origen atribuido a un frame y la evidencia disponible."""

	originType: OriginType = OriginType.UNKNOWN
	originConfidence: OriginConfidence = OriginConfidence.UNKNOWN
	associatedText: str | None = None
	applicationName: str | None = None
	processId: int | None = None
	requestedText: str | None = None
	correlatedEventId: int | None = None
	correlationReason: str | None = None
	context: FrameContext = field(default_factory=FrameContext)


@dataclass(frozen=True, slots=True)
class BrailleFrame:
	"""Representa una llamada exacta a ``display(cells)`` ya materializada."""

	frameId: int
	timestamp: float
	timestampIso: str
	monotonicTimestamp: float
	monotonicNanoseconds: int
	numCells: int
	cellsRaw: bytes
	cellsDecimal: str
	cellsHex: str
	cellsBinary: str
	cellsUnicode: str
	activeDots: str
	threadId: int
	associatedText: str | None
	originType: OriginType
	originConfidence: OriginConfidence
	applicationName: str | None
	processId: int | None
	requestedText: str | None
	correlatedEventId: int | None
	correlationReason: str | None
	context: FrameContext = field(default_factory=FrameContext)

	@property
	def contextProcessId(self) -> int | None:
		"""Atajo al PID del proceso cuyo contenido NVDA estaba representando."""
		return self.context.processId

	@property
	def contextProcessName(self) -> str | None:
		"""Atajo al ejecutable del proceso cuyo contenido NVDA estaba representando."""
		return self.context.processName

	@property
	def isMessage(self) -> bool:
		"""Indica si el frame procede del búfer de mensajes braille de NVDA."""
		return self.context.bufferKind is BufferKind.MESSAGE

	@property
	def usedCells(self) -> int:
		"""Cuenta las celdas realmente ocupadas, ignorando el relleno final vacío."""
		return len(self.cellsRaw.rstrip(b"\x00"))

	@property
	def isBlank(self) -> bool:
		"""Indica si el frame no contiene ningún punto activo."""
		return self.usedCells == 0

	def matchesProcess(self, processId: int | None) -> bool:
		"""Indica si el frame corresponde a un PID, considerando contexto y origen externo."""
		if processId is None:
			return True
		return processId in (self.context.processId, self.processId)

	def toDictionary(self) -> dict[str, Any]:
		"""Devuelve un diccionario apto para JSON sin perder los bytes del frame."""
		data: dict[str, Any] = {
			"frameId": self.frameId,
			"timestamp": self.timestamp,
			"timestampIso": self.timestampIso,
			"monotonicTimestamp": self.monotonicTimestamp,
			"monotonicNanoseconds": self.monotonicNanoseconds,
			"numCells": self.numCells,
			"usedCells": self.usedCells,
			"cellsRaw": list(self.cellsRaw),
			"cellsDecimal": self.cellsDecimal,
			"cellsHex": self.cellsHex,
			"cellsBinary": self.cellsBinary,
			"cellsUnicode": self.cellsUnicode,
			"activeDots": self.activeDots,
			"threadId": self.threadId,
			"associatedText": self.associatedText,
			"originType": self.originType.value,
			"originConfidence": self.originConfidence.value,
			"applicationName": self.applicationName,
			"processId": self.processId,
			"requestedText": self.requestedText,
			"correlatedEventId": self.correlatedEventId,
			"correlationReason": self.correlationReason,
		}
		data.update(self.context.toDictionary())
		return data


@dataclass(slots=True)
class ExternalBrailleEvent:
	"""Representa una solicitud de braille observada antes de que NVDA la traduzca."""

	eventId: int
	timestamp: float
	timestampIso: str
	monotonicTimestamp: float
	monotonicNanoseconds: int
	text: str
	sourceApi: str
	processId: int | None
	processName: str | None
	confidence: OriginConfidence
	threadId: int
	correlatedFrameId: int | None = None
	correlationConfidence: OriginConfidence = OriginConfidence.UNKNOWN
	correlationReason: str | None = None

	def toDictionary(self) -> dict[str, Any]:
		"""Devuelve una copia serializable del evento externo."""
		return {
			"eventId": self.eventId,
			"timestamp": self.timestamp,
			"timestampIso": self.timestampIso,
			"monotonicTimestamp": self.monotonicTimestamp,
			"monotonicNanoseconds": self.monotonicNanoseconds,
			"text": self.text,
			"sourceApi": self.sourceApi,
			"processId": self.processId,
			"processName": self.processName,
			"confidence": self.confidence.value,
			"threadId": self.threadId,
			"correlatedFrameId": self.correlatedFrameId,
			"correlationConfidence": self.correlationConfidence.value,
			"correlationReason": self.correlationReason,
		}


@dataclass(frozen=True, slots=True)
class CellDifference:
	"""Describe el cambio de una celda entre dos frames."""

	position: int
	changeType: str
	oldValue: int | None
	newValue: int | None


@dataclass(frozen=True, slots=True)
class ApplicationFilter:
	"""Restringe el visor a los frames de un proceso concreto."""

	processId: int | None = None
	processName: str | None = None

	@property
	def isActive(self) -> bool:
		"""Indica si hay un proceso seleccionado."""
		return self.processId is not None

	def accepts(self, frame: BrailleFrame) -> bool:
		"""Indica si un frame debe mostrarse con el filtro actual."""
		return frame.matchesProcess(self.processId)
