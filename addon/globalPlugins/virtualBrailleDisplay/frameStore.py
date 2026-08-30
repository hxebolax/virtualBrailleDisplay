"""Almacenamiento en memoria, acotado y seguro entre hilos."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from datetime import datetime

from .brailleUtils import (
	cellsToActiveDots,
	cellsToBinary,
	cellsToDecimal,
	cellsToHex,
	cellsToUnicode,
	normalizeCells,
)
from .models import BrailleFrame, ExternalBrailleEvent, FrameOrigin, OriginConfidence

FrameListener = Callable[[BrailleFrame], None]
EventListener = Callable[[ExternalBrailleEvent], None]


def _isoTimestamp(timestampNanoseconds: int) -> str:
	"""Convierte nanosegundos desde Epoch en una marca ISO local con milisegundos."""
	return (
		datetime.fromtimestamp(timestampNanoseconds / 1_000_000_000)
		.astimezone()
		.isoformat(
			timespec="milliseconds",
		)
	)


class FrameStore:
	"""Mantiene frames y eventos en dos historiales independientes y acotados."""

	def __init__(self, maximumItems: int = 1000):
		"""Inicializa historiales vacíos con un límite común."""
		self._lock = threading.RLock()
		self._maximumItems = max(1, int(maximumItems))
		self._frames: deque[BrailleFrame] = deque(maxlen=self._maximumItems)
		self._events: deque[ExternalBrailleEvent] = deque(maxlen=self._maximumItems)
		self._nextFrameId = 1
		self._nextEventId = 1
		self._frameListeners: set[FrameListener] = set()
		self._eventListeners: set[EventListener] = set()

	@property
	def maximumItems(self) -> int:
		"""Devuelve la capacidad configurada de cada historial."""
		with self._lock:
			return self._maximumItems

	def setMaximumItems(self, maximumItems: int) -> None:
		"""Cambia la capacidad conservando los elementos más recientes."""
		validated = max(1, int(maximumItems))
		with self._lock:
			if validated == self._maximumItems:
				return
			self._frames = deque(self._frames, maxlen=validated)
			self._events = deque(self._events, maxlen=validated)
			self._maximumItems = validated

	def captureFrame(self, cells: Iterable[int], origin: FrameOrigin) -> BrailleFrame:
		"""Copia y registra un frame procedente directamente del método ``display``."""
		wallNanoseconds = time.time_ns()
		monotonicNanoseconds = time.perf_counter_ns()
		rawCells = normalizeCells(cells)
		with self._lock:
			frameId = self._nextFrameId
			self._nextFrameId += 1
		frame = BrailleFrame(
			frameId=frameId,
			timestamp=wallNanoseconds / 1_000_000_000,
			timestampIso=_isoTimestamp(wallNanoseconds),
			monotonicTimestamp=monotonicNanoseconds / 1_000_000_000,
			monotonicNanoseconds=monotonicNanoseconds,
			numCells=len(rawCells),
			cellsRaw=rawCells,
			cellsDecimal=cellsToDecimal(rawCells),
			cellsHex=cellsToHex(rawCells),
			cellsBinary=cellsToBinary(rawCells),
			cellsUnicode=cellsToUnicode(rawCells),
			activeDots=cellsToActiveDots(rawCells),
			threadId=threading.get_ident(),
			associatedText=origin.associatedText,
			originType=origin.originType,
			originConfidence=origin.originConfidence,
			applicationName=origin.applicationName,
			processId=origin.processId,
			requestedText=origin.requestedText,
			correlatedEventId=origin.correlatedEventId,
			correlationReason=origin.correlationReason,
			context=origin.context,
		)
		with self._lock:
			self._frames.append(frame)
			listeners = tuple(self._frameListeners)
		for listener in listeners:
			self._notifyListener(listener, frame)
		return frame

	def addExternalEvent(
		self,
		text: str,
		sourceApi: str,
		processId: int | None = None,
		processName: str | None = None,
	) -> ExternalBrailleEvent:
		"""Registra una solicitud externa sin completar datos que la API no ofrece."""
		wallNanoseconds = time.time_ns()
		monotonicNanoseconds = time.perf_counter_ns()
		with self._lock:
			eventId = self._nextEventId
			self._nextEventId += 1
		event = ExternalBrailleEvent(
			eventId=eventId,
			timestamp=wallNanoseconds / 1_000_000_000,
			timestampIso=_isoTimestamp(wallNanoseconds),
			monotonicTimestamp=monotonicNanoseconds / 1_000_000_000,
			monotonicNanoseconds=monotonicNanoseconds,
			text=text,
			sourceApi=sourceApi,
			processId=processId,
			processName=processName,
			confidence=OriginConfidence.CONFIRMED,
			threadId=threading.get_ident(),
		)
		with self._lock:
			self._events.append(event)
			listeners = tuple(self._eventListeners)
		for listener in listeners:
			self._notifyListener(listener, event)
		return event

	def markEventCorrelated(
		self,
		eventId: int,
		frameId: int,
		confidence: OriginConfidence,
		reason: str,
	) -> None:
		"""Anota en el evento la correlación resultante sin convertirla en confirmación."""
		with self._lock:
			event = next((item for item in self._events if item.eventId == eventId), None)
			if event is None:
				return
			event.correlatedFrameId = frameId
			event.correlationConfidence = confidence
			event.correlationReason = reason
			listeners = tuple(self._eventListeners)
		for listener in listeners:
			self._notifyListener(listener, event)

	def getFrames(self, processId: int | None = None) -> tuple[BrailleFrame, ...]:
		"""Devuelve una instantánea ordenada del historial, opcionalmente filtrada por proceso."""
		with self._lock:
			frames = tuple(self._frames)
		if processId is None:
			return frames
		return tuple(frame for frame in frames if frame.matchesProcess(processId))

	def getLastFrame(self, processId: int | None = None) -> BrailleFrame | None:
		"""Devuelve el frame más reciente que cumple el filtro indicado."""
		frames = self.getFrames(processId)
		return frames[-1] if frames else None

	def getKnownProcesses(self) -> tuple[tuple[int, str], ...]:
		"""Enumera los procesos observados en el historial para poder ofrecerlos como filtro."""
		names: dict[int, str] = {}
		for frame in self.getFrames():
			for processId, processName in (
				(frame.context.processId, frame.context.processName),
				(frame.processId, frame.applicationName),
			):
				if processId is None:
					continue
				if processName or processId not in names:
					names[processId] = str(processName or "")
		return tuple(sorted(names.items()))

	def getStatistics(self, processId: int | None = None) -> dict[str, int]:
		"""Resume el historial para el panel de diagnóstico sin recalcular nada costoso."""
		frames = self.getFrames(processId)
		blank = sum(1 for frame in frames if frame.isBlank)
		messages = sum(1 for frame in frames if frame.isMessage)
		full = sum(1 for frame in frames if frame.numCells and frame.usedCells >= frame.numCells)
		return {
			"frames": len(frames),
			"blankFrames": blank,
			"messageFrames": messages,
			"fullWidthFrames": full,
			"events": len(self.getEvents()),
		}

	def getEvents(self) -> tuple[ExternalBrailleEvent, ...]:
		"""Devuelve una instantánea ordenada del historial de eventos."""
		with self._lock:
			return tuple(self._events)

	def getFrame(self, frameId: int) -> BrailleFrame | None:
		"""Busca un frame por identificador."""
		with self._lock:
			return next((frame for frame in self._frames if frame.frameId == frameId), None)

	def getRecentUncorrelatedEvents(self, sinceNanoseconds: int) -> tuple[ExternalBrailleEvent, ...]:
		"""Devuelve eventos aún no correlacionados posteriores a un instante monotónico."""
		with self._lock:
			return tuple(
				event
				for event in self._events
				if event.correlatedFrameId is None and event.monotonicNanoseconds >= sinceNanoseconds
			)

	def clear(self) -> None:
		"""Limpia ambos historiales sin reutilizar identificadores anteriores."""
		with self._lock:
			self._frames.clear()
			self._events.clear()

	def registerFrameListener(self, listener: FrameListener) -> None:
		"""Registra un observador ligero para frames nuevos."""
		with self._lock:
			self._frameListeners.add(listener)

	def unregisterFrameListener(self, listener: FrameListener) -> None:
		"""Retira un observador de frames si estaba registrado."""
		with self._lock:
			self._frameListeners.discard(listener)

	def registerEventListener(self, listener: EventListener) -> None:
		"""Registra un observador ligero para eventos externos."""
		with self._lock:
			self._eventListeners.add(listener)

	def unregisterEventListener(self, listener: EventListener) -> None:
		"""Retira un observador de eventos si estaba registrado."""
		with self._lock:
			self._eventListeners.discard(listener)

	@staticmethod
	def _notifyListener(listener: Callable[[object], None], item: object) -> None:
		"""Aísla errores de observadores para que nunca inutilicen el driver."""
		try:
			listener(item)
		except Exception:
			logging.getLogger(__name__).exception("Error en un observador de Virtual Braille Display")
