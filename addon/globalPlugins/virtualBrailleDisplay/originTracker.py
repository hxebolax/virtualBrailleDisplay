"""Correlación prudente entre solicitudes externas, preescrituras y frames finales."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass

from . import config as addonConfig
from .brailleUtils import normalizeCells
from .frameStore import FrameStore
from .models import (
	BufferKind,
	ExternalBrailleEvent,
	FrameContext,
	FrameOrigin,
	OriginConfidence,
	OriginType,
)


@dataclass(slots=True)
class PreWriteContext:
	"""Conserva el contexto efímero emitido justo antes de escribir en el driver."""

	cells: bytes
	rawText: str
	currentCellCount: int
	monotonicNanoseconds: int
	threadId: int
	event: ExternalBrailleEvent | None
	reason: str | None
	context: FrameContext


class OriginTracker:
	"""Asocia frames con eventos sólo cuando existe evidencia temporal y textual suficiente."""

	def __init__(self, frameStore: FrameStore):
		"""Inicializa el correlador sin contexto pendiente."""
		self._frameStore = frameStore
		self._lock = threading.RLock()
		self._preWritesByThread: dict[int, PreWriteContext] = {}
		self._reservedEventIds: set[int] = set()

	def notePreWrite(
		self,
		cells: Iterable[int],
		rawText: str,
		currentCellCount: int,
		context: FrameContext | None = None,
	) -> None:
		"""Recibe el punto de extensión de NVDA y prepara contexto para el ``display`` inmediato."""
		nowNanoseconds = time.perf_counter_ns()
		threadId = threading.get_ident()
		event, reason = self._selectExternalEvent(rawText or "", nowNanoseconds)
		preWriteContext = PreWriteContext(
			cells=normalizeCells(cells),
			rawText=rawText or "",
			currentCellCount=int(currentCellCount),
			monotonicNanoseconds=nowNanoseconds,
			threadId=threadId,
			event=event,
			reason=reason,
			context=context if context is not None else FrameContext(),
		)
		with self._lock:
			previous = self._preWritesByThread.get(threadId)
			if previous is not None and previous.event is not None:
				self._reservedEventIds.discard(previous.event.eventId)
			self._preWritesByThread[threadId] = preWriteContext
			if event is not None:
				self._reservedEventIds.add(event.eventId)

	def consumeForDisplay(self, cells: Iterable[int]) -> FrameOrigin:
		"""Consume el contexto del mismo hilo y devuelve una atribución para el buffer final."""
		displayCells = normalizeCells(cells)
		threadId = threading.get_ident()
		with self._lock:
			context = self._preWritesByThread.pop(threadId, None)
		if context is None:
			return FrameOrigin()
		if context.event is not None:
			with self._lock:
				self._reservedEventIds.discard(context.event.eventId)
		if not self._cellsAreCompatible(context.cells, displayCells):
			return FrameOrigin(
				originType=OriginType.UNKNOWN,
				originConfidence=OriginConfidence.CONTEXT,
				correlationReason="El contexto pre_writeCells no coincide con el buffer final.",
				context=context.context,
			)
		if context.event is None:
			return self._originFromBuffer(context)
		return FrameOrigin(
			originType=OriginType.CORRELATED_EXTERNAL_MESSAGE,
			originConfidence=OriginConfidence.PROBABLE,
			associatedText=context.rawText,
			applicationName=context.event.processName,
			processId=context.event.processId,
			requestedText=context.event.text,
			correlatedEventId=context.event.eventId,
			correlationReason=context.reason,
			context=context.context,
		)

	def reset(self) -> None:
		"""Descarta contextos temporales al descargar el complemento."""
		with self._lock:
			self._preWritesByThread.clear()
			self._reservedEventIds.clear()

	@staticmethod
	def _originFromBuffer(context: PreWriteContext) -> FrameOrigin:
		"""Clasifica el frame según qué búfer de NVDA lo generó, que sí es evidencia directa.

		La confianza confirmada se refiere únicamente al subsistema de NVDA que produjo las
		celdas. Nunca afirma qué aplicación pidió el mensaje: eso sólo lo aporta un evento
		externo correlacionado.
		"""
		bufferKind = context.context.bufferKind
		if bufferKind is BufferKind.MESSAGE:
			return FrameOrigin(
				originType=OriginType.BRAILLE_MESSAGE,
				originConfidence=OriginConfidence.CONFIRMED,
				associatedText=context.rawText,
				correlationReason="NVDA estaba mostrando su búfer de mensajes braille.",
				context=context.context,
			)
		if bufferKind is BufferKind.MAIN and context.context.regionCount > 0:
			return FrameOrigin(
				originType=OriginType.NVDA_NAVIGATION,
				originConfidence=OriginConfidence.CONFIRMED,
				associatedText=context.rawText,
				correlationReason="NVDA estaba mostrando su búfer principal de navegación.",
				context=context.context,
			)
		return FrameOrigin(associatedText=context.rawText, context=context.context)

	def _selectExternalEvent(
		self,
		rawText: str,
		nowNanoseconds: int,
	) -> tuple[ExternalBrailleEvent | None, str | None]:
		"""Escoge como máximo un evento pendiente mediante reglas conservadoras."""
		windowNanoseconds = addonConfig.getCorrelationWindowMilliseconds() * 1_000_000
		candidates = self._frameStore.getRecentUncorrelatedEvents(nowNanoseconds - windowNanoseconds)
		with self._lock:
			candidates = tuple(event for event in candidates if event.eventId not in self._reservedEventIds)
		if not candidates:
			return None, None
		exact = tuple(event for event in candidates if event.text == rawText)
		if exact:
			return exact[0], "Coincidencia textual exacta y proximidad temporal; atribución no confirmada."
		partial = tuple(event for event in candidates if self._textsAreCompatible(event.text, rawText))
		if len(partial) == 1:
			return partial[0], "Coincidencia textual parcial y proximidad temporal; atribución no confirmada."
		fallbackNanoseconds = addonConfig.getTemporalFallbackMilliseconds() * 1_000_000
		veryRecent = tuple(
			event
			for event in candidates
			if nowNanoseconds - event.monotonicNanoseconds <= fallbackNanoseconds
		)
		if len(veryRecent) == 1:
			return veryRecent[0], "Único evento en la ventana temporal corta; atribución no confirmada."
		return None, None

	@staticmethod
	def _textsAreCompatible(requestedText: str, rawText: str) -> bool:
		"""Comprueba una coincidencia parcial útil para ventanas braille desplazadas o truncadas."""
		if not requestedText or not rawText:
			return False
		return rawText in requestedText or requestedText in rawText

	@staticmethod
	def _cellsAreCompatible(preWriteCells: bytes, displayCells: bytes) -> bool:
		"""Admite normalización por recorte o relleno con ceros realizada por NVDA."""
		commonLength = min(len(preWriteCells), len(displayCells))
		if preWriteCells[:commonLength] != displayCells[:commonLength]:
			return False
		if len(displayCells) > commonLength:
			return all(value == 0 for value in displayCells[commonLength:])
		return True
