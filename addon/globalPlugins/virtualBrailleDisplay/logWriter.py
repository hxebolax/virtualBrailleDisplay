"""Exportación de historiales en TXT, JSON y JSONL, manual o como registro continuo."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterable
from pathlib import Path

from .models import BrailleFrame, ExternalBrailleEvent

SUPPORTED_FORMATS = ("txt", "json", "jsonl")
CONTINUOUS_FORMATS = ("jsonl", "txt")
# Tamaño máximo de la cola: si el disco no sigue el ritmo se descartan registros
# antes que ralentizar jamás la escritura de celdas en el driver.
CONTINUOUS_QUEUE_SIZE = 2000


def saveRecords(
	path: str | Path,
	formatName: str,
	frames: Iterable[BrailleFrame],
	events: Iterable[ExternalBrailleEvent],
) -> None:
	"""Escribe una instantánea de los historiales sólo tras una acción explícita del usuario."""
	validatedFormat = formatName.lower().lstrip(".")
	if validatedFormat not in SUPPORTED_FORMATS:
		raise ValueError(f"Formato no admitido: {formatName}")
	target = Path(path)
	frameItems = tuple(frames)
	eventItems = tuple(events)
	if validatedFormat == "txt":
		content = _toText(frameItems, eventItems)
	elif validatedFormat == "json":
		content = json.dumps(
			{
				"frames": [frame.toDictionary() for frame in frameItems],
				"externalEvents": [event.toDictionary() for event in eventItems],
			},
			ensure_ascii=False,
			indent=2,
		)
	else:
		content = _toJsonLines(frameItems, eventItems)
	target.write_text(content, encoding="utf-8")


def _toText(frames: tuple[BrailleFrame, ...], events: tuple[ExternalBrailleEvent, ...]) -> str:
	"""Serializa historiales en un formato de texto humano."""
	lines = ["VIRTUAL BRAILLE DISPLAY", "", "EVENTOS EXTERNOS"]
	for event in events:
		lines.extend(
			(
				f"EVENTO #{event.eventId} {event.timestampIso}",
				f"API: {event.sourceApi}",
				f"Texto: {event.text}",
				f"PID: {event.processId if event.processId is not None else 'No disponible'}",
				f"Frame correlacionado: {event.correlatedFrameId}",
				f"Confianza: {event.correlationConfidence.value}",
				"",
			),
		)
	lines.append("FRAMES DEL DISPOSITIVO")
	for frame in frames:
		lines.extend(
			(
				f"FRAME #{frame.frameId} {frame.timestampIso}",
				f"Celdas: {frame.numCells}",
				f"Origen: {frame.originType.value}",
				f"Confianza: {frame.originConfidence.value}",
				f"Texto legible asociado: {frame.associatedText if frame.associatedText is not None else 'No disponible'}",
				f"Unicode: {frame.cellsUnicode}",
				f"Hex: {frame.cellsHex}",
				f"Decimal: {frame.cellsDecimal}",
				f"Binario: {frame.cellsBinary}",
				f"Puntos: {frame.activeDots}",
				"",
			),
		)
	return "\n".join(lines)


def _toJsonLines(frames: tuple[BrailleFrame, ...], events: tuple[ExternalBrailleEvent, ...]) -> str:
	"""Serializa cada evento y frame como un objeto JSON independiente."""
	lines: list[str] = []
	for event in events:
		item = {"type": "externalEvent", **event.toDictionary()}
		lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
	for frame in frames:
		item = {"type": "frame", **frame.toDictionary()}
		lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
	return "\n".join(lines) + ("\n" if lines else "")


class ContinuousLogger:
	"""Escribe frames y eventos en un archivo desde un hilo aparte.

	El objetivo es que ``display(cells)`` nunca realice entrada/salida: sólo deposita el
	registro en una cola acotada. Si la cola se llena, se descartan registros y se lleva
	la cuenta, en lugar de bloquear al subsistema braille de NVDA.
	"""

	def __init__(self):
		"""Crea un registrador inactivo, sin archivo ni hilo asociados."""
		self._lock = threading.RLock()
		self._queue: queue.Queue[str | None] | None = None
		self._thread: threading.Thread | None = None
		self._path: Path | None = None
		self._format = "jsonl"
		self._droppedRecords = 0

	@property
	def active(self) -> bool:
		"""Indica si hay un registro continuo en marcha."""
		with self._lock:
			return self._thread is not None

	@property
	def path(self) -> Path | None:
		"""Devuelve el archivo de destino del registro activo."""
		with self._lock:
			return self._path

	@property
	def droppedRecords(self) -> int:
		"""Devuelve cuántos registros se descartaron por saturación de la cola."""
		with self._lock:
			return self._droppedRecords

	def start(self, path: str | Path, formatName: str = "jsonl") -> None:
		"""Abre el archivo en modo de adición y arranca el hilo escritor."""
		validatedFormat = formatName.lower().lstrip(".")
		if validatedFormat not in CONTINUOUS_FORMATS:
			raise ValueError(f"Formato de registro continuo no admitido: {formatName}")
		target = Path(path)
		if not target.parent.exists():
			raise ValueError(f"La carpeta de destino no existe: {target.parent}")
		self.stop()
		with self._lock:
			self._path = target
			self._format = validatedFormat
			self._droppedRecords = 0
			self._queue = queue.Queue(maxsize=CONTINUOUS_QUEUE_SIZE)
			self._thread = threading.Thread(
				target=self._writerLoop,
				name="virtualBrailleDisplayLogger",
				daemon=True,
			)
			self._thread.start()

	def stop(self) -> None:
		"""Detiene el hilo escritor vaciando lo que quede pendiente."""
		with self._lock:
			thread = self._thread
			pending = self._queue
			self._thread = None
			self._queue = None
		if thread is None:
			return
		if pending is not None:
			try:
				pending.put_nowait(None)
			except queue.Full:
				pass
		thread.join(timeout=2.0)

	def logFrame(self, frame: BrailleFrame) -> None:
		"""Encola un frame sin realizar ninguna operación de disco en el hilo llamante."""
		self._enqueue({"type": "frame", **frame.toDictionary()})

	def logEvent(self, event: ExternalBrailleEvent) -> None:
		"""Encola un evento externo sin realizar ninguna operación de disco."""
		self._enqueue({"type": "externalEvent", **event.toDictionary()})

	def _enqueue(self, record: dict[str, object]) -> None:
		"""Serializa el registro y lo deposita en la cola descartándolo si está llena."""
		with self._lock:
			pending = self._queue
			formatName = self._format
		if pending is None:
			return
		line = _formatRecord(record, formatName)
		try:
			pending.put_nowait(line)
		except queue.Full:
			with self._lock:
				self._droppedRecords += 1

	def _writerLoop(self) -> None:
		"""Consume la cola y escribe en el archivo hasta recibir la señal de parada."""
		with self._lock:
			pending = self._queue
			target = self._path
		if pending is None or target is None:
			return
		with target.open("a", encoding="utf-8") as handle:
			while True:
				line = pending.get()
				if line is None:
					handle.flush()
					return
				handle.write(line)
				handle.flush()


def _formatRecord(record: dict[str, object], formatName: str) -> str:
	"""Convierte un registro en la línea que corresponde al formato elegido."""
	if formatName == "jsonl":
		return json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
	kind = record.get("type")
	identifier = record.get("frameId") if kind == "frame" else record.get("eventId")
	timestamp = record.get("timestampIso")
	if kind == "frame":
		detail = f"{record.get('numCells')} celdas | {record.get('cellsHex')}"
	else:
		detail = f"{record.get('sourceApi')} | {record.get('text')}"
	return f"{timestamp} {kind} #{identifier} {detail}\n"
