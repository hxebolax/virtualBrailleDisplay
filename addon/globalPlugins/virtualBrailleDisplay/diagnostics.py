"""Explicación en lenguaje humano de un frame braille y detección de problemas frecuentes.

Este módulo está pensado para dos públicos:

- quien conoce braille y quiere confirmar qué recibiría una línea física;
- quien no conoce braille ni lectores de pantalla y sólo necesita saber si su aplicación
  está exponiendo información útil.

No contiene dependencias de NVDA ni de wx para poder probarse de forma aislada.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import addonHandler

addonHandler.initTranslation()

from .brailleUtils import cellToDots, cellToUnicode, splitIntoWindows  # noqa: E402
from .models import BrailleFrame, BufferKind, OriginConfidence, OriginType  # noqa: E402

# Porcentaje a partir del cual se considera que la ventana braille va justa de espacio.
CROWDED_RATIO = 0.9


class Severity(str, Enum):
	"""Clasifica la importancia de cada observación del diagnóstico."""

	INFORMATION = "INFORMATION"
	SUGGESTION = "SUGGESTION"
	WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class Observation:
	"""Representa una observación explicada para una persona sin conocimientos de braille."""

	severity: Severity
	title: str
	detail: str

	@property
	def severityLabel(self) -> str:
		"""Devuelve el nombre traducible de la severidad."""
		return {
			Severity.INFORMATION: _("Información"),
			Severity.SUGGESTION: _("Sugerencia"),
			Severity.WARNING: _("Aviso"),
		}[self.severity]


def originLabel(originType: OriginType) -> str:
	"""Convierte un identificador interno de origen en una explicación breve."""
	return {
		OriginType.UNKNOWN: _("Origen desconocido"),
		OriginType.NVDA_NAVIGATION: _("Navegación normal de NVDA"),
		OriginType.CONTROLLER_CLIENT: _("NVDA Controller Client"),
		OriginType.BRAILLE_MESSAGE: _("Mensaje braille de NVDA"),
		OriginType.CORRELATED_EXTERNAL_MESSAGE: _("Mensaje de aplicación externa correlacionado"),
	}[originType]


def confidenceLabel(confidence: OriginConfidence) -> str:
	"""Explica el nivel de confianza sin exponer únicamente el nombre técnico inglés."""
	return {
		OriginConfidence.UNKNOWN: _("Sin determinar"),
		OriginConfidence.CONTEXT: _("Sólo contexto; no atribuido"),
		OriginConfidence.PROBABLE: _("Probable, no confirmado"),
		OriginConfidence.CONFIRMED: _("Confirmado"),
	}[confidence]


def bufferLabel(bufferKind: BufferKind) -> str:
	"""Explica qué parte del subsistema braille de NVDA generó el frame."""
	return {
		BufferKind.UNKNOWN: _("No determinado"),
		BufferKind.MAIN: _("Búfer principal: contenido del foco o de la revisión"),
		BufferKind.MESSAGE: _("Búfer de mensajes: aviso temporal mostrado por NVDA"),
	}[bufferKind]


def describeCell(value: int | None) -> str:
	"""Describe una celda por patrón, puntos y valor para lectores sin conocimientos de braille."""
	if value is None:
		return _("sin celda")
	dots = cellToDots(value)
	dotsText = ", ".join(str(dot) for dot in dots) if dots else _("ninguno; celda vacía")
	return _("{pattern}, puntos {dots}, valor hexadecimal 0x{value:02X}").format(
		pattern=cellToUnicode(value),
		dots=dotsText,
		value=value,
	)


def describeApplication(frame: BrailleFrame) -> str:
	"""Resume a qué aplicación pertenece el contenido representado en el frame."""
	name = frame.context.processName
	processId = frame.context.processId
	if name and processId is not None:
		return _("{name} (PID {pid})").format(name=name, pid=processId)
	if name:
		return str(name)
	if processId is not None:
		return _("PID {pid}").format(pid=processId)
	return _("No disponible")


def describeOccupancy(frame: BrailleFrame) -> str:
	"""Explica cuánto espacio de la línea ocupa el contenido de este frame."""
	if not frame.numCells:
		return _("La línea no declaró ninguna celda.")
	used = frame.usedCells
	percentage = round(used * 100 / frame.numCells)
	return _("Ocupa {used} de {total} celdas ({percentage} por ciento de la línea).").format(
		used=used,
		total=frame.numCells,
		percentage=percentage,
	)


def summarizeForHumans(frame: BrailleFrame, readableText: str, readableSource: str) -> str:
	"""Redacta un párrafo comprensible para quien no lee braille ni usa lector de pantalla."""
	lines = [
		_("Qué está viendo ahora mismo una persona con línea braille:"),
		"",
		_("Texto: {text}").format(text=readableText),
		_("De dónde sale ese texto: {source}.").format(source=readableSource),
		_("Aplicación cuyo contenido se estaba representando: {application}.").format(
			application=describeApplication(frame),
		),
		_("Parte de NVDA que lo generó: {buffer}.").format(buffer=bufferLabel(frame.context.bufferKind)),
		describeOccupancy(frame),
	]
	return "\n".join(lines)


def analyzeFrame(frame: BrailleFrame, readableText: str | None) -> list[Observation]:
	"""Detecta situaciones que suelen indicar un problema de accesibilidad o de tamaño."""
	observations: list[Observation] = []
	observations.extend(_analyzeContent(frame, readableText))
	observations.extend(_analyzeSpace(frame))
	observations.extend(_analyzeOrigin(frame))
	if not observations:
		observations.append(
			Observation(
				Severity.INFORMATION,
				_("Sin incidencias detectadas"),
				_("El frame contiene texto, cabe en la línea y su origen está identificado."),
			),
		)
	return observations


def _analyzeContent(frame: BrailleFrame, readableText: str | None) -> list[Observation]:
	"""Comprueba si la línea recibió realmente contenido legible."""
	observations: list[Observation] = []
	if frame.isBlank:
		observations.append(
			Observation(
				Severity.WARNING,
				_("La línea braille se quedó en blanco"),
				_(
					"NVDA envió una línea sin ningún punto activo. Quien use braille no percibe nada. "
					"Suele ocurrir cuando un control no tiene nombre accesible, cuando el foco cayó en "
					"un contenedor vacío o cuando la ventana no expone texto.",
				),
			),
		)
		return observations
	if not readableText or not readableText.strip():
		observations.append(
			Observation(
				Severity.SUGGESTION,
				_("Hay puntos pero no se pudo recuperar el texto"),
				_(
					"Las celdas contienen información, pero NVDA no facilitó el texto asociado y la "
					"traducción inversa no dio resultado. Compruebe la tabla braille activa.",
				),
			),
		)
	return observations


def _analyzeSpace(frame: BrailleFrame) -> list[Observation]:
	"""Comprueba si el contenido llena la línea y podría estar recortado."""
	observations: list[Observation] = []
	if not frame.numCells:
		return observations
	used = frame.usedCells
	if used >= frame.numCells:
		observations.append(
			Observation(
				Severity.WARNING,
				_("El contenido llena la línea completa"),
				_(
					"Se han ocupado las {total} celdas disponibles. Es muy probable que el texto continúe "
					"y que la persona tenga que desplazar la línea para leer el resto. Considere acortar "
					"la información más importante o situarla al principio.",
				).format(total=frame.numCells),
			),
		)
	elif used >= frame.numCells * CROWDED_RATIO:
		observations.append(
			Observation(
				Severity.SUGGESTION,
				_("El contenido casi llena la línea"),
				_(
					"Quedan pocas celdas libres. En una línea más corta, como las de 14 o 20 celdas, "
					"este mismo contenido ya no cabría de una vez.",
				),
			),
		)
	shortDisplayWindows = len(splitIntoWindows(frame.cellsRaw[:used] or b"\x00", 20))
	if used and shortDisplayWindows > 1:
		observations.append(
			Observation(
				Severity.INFORMATION,
				_("En una línea de 20 celdas ocuparía varias ventanas"),
				_(
					"El mismo contenido necesitaría {count} desplazamientos en una línea de 20 celdas.",
				).format(count=shortDisplayWindows),
			),
		)
	return observations


def _analyzeOrigin(frame: BrailleFrame) -> list[Observation]:
	"""Explica las limitaciones de la atribución de origen sin exagerarlas."""
	observations: list[Observation] = []
	if frame.originType is OriginType.CORRELATED_EXTERNAL_MESSAGE:
		observations.append(
			Observation(
				Severity.INFORMATION,
				_("Procede de una solicitud de una aplicación externa"),
				_(
					"Una aplicación pidió a NVDA mostrar un mensaje braille y este frame se le atribuyó "
					"por proximidad temporal y coincidencia de texto. La atribución es probable, "
					"nunca confirmada.",
				),
			),
		)
	elif frame.originType is OriginType.UNKNOWN:
		observations.append(
			Observation(
				Severity.INFORMATION,
				_("No se pudo determinar el origen"),
				_(
					"NVDA no facilitó contexto suficiente para este frame. Las celdas siguen siendo "
					"exactas: lo único desconocido es qué parte de NVDA las produjo.",
				),
			),
		)
	if frame.context.processId is None and frame.processId is None:
		observations.append(
			Observation(
				Severity.INFORMATION,
				_("Sin aplicación identificada"),
				_(
					"Ni las regiones braille ni una solicitud externa aportaron un proceso. "
					"El complemento no deduce la aplicación a partir del foco porque el foco no tiene "
					"por qué coincidir con quien pidió el mensaje.",
				),
			),
		)
	return observations


def buildPlainReport(frame: BrailleFrame, readableText: str, readableSource: str) -> str:
	"""Genera el informe completo en lenguaje humano listo para copiar o mostrar."""
	lines = [summarizeForHumans(frame, readableText, readableSource), "", _("Revisión automática:")]
	for observation in analyzeFrame(frame, readableText):
		lines.append("")
		lines.append(f"{observation.severityLabel}: {observation.title}")
		lines.append(observation.detail)
	return "\n".join(lines)
