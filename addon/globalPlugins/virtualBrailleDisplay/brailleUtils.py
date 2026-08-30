"""Conversiones puras de celdas braille y comparación de frames."""

from __future__ import annotations

from collections.abc import Iterable

from .models import CellDifference

BRAILLE_UNICODE_BASE = 0x2800
MIN_CELL_COUNT = 1
MAX_CELL_COUNT = 256


def validateCellValue(value: int) -> int:
	"""Valida y devuelve un byte que representa una celda braille de ocho puntos."""
	if isinstance(value, bool) or not isinstance(value, int):
		raise TypeError("Cada celda braille debe ser un entero")
	if not 0 <= value <= 255:
		raise ValueError("Cada celda braille debe estar entre 0 y 255")
	return value


def validateCellCount(value: int) -> int:
	"""Valida un tamaño de línea dentro de los límites admitidos por el complemento."""
	if isinstance(value, bool) or not isinstance(value, int):
		raise TypeError("El número de celdas debe ser un entero")
	if not MIN_CELL_COUNT <= value <= MAX_CELL_COUNT:
		raise ValueError(f"El número de celdas debe estar entre {MIN_CELL_COUNT} y {MAX_CELL_COUNT}")
	return value


def normalizeCells(cells: Iterable[int]) -> bytes:
	"""Copia una colección de celdas en un objeto ``bytes`` inmutable y validado."""
	return bytes(validateCellValue(value) for value in cells)


def cellToUnicode(value: int) -> str:
	"""Convierte un byte al carácter Unicode Braille con el mismo patrón de bits."""
	return chr(BRAILLE_UNICODE_BASE + validateCellValue(value))


def cellsToUnicode(cells: Iterable[int]) -> str:
	"""Convierte una secuencia de bytes en patrones Unicode Braille."""
	return "".join(cellToUnicode(value) for value in cells)


def cellToDots(value: int) -> tuple[int, ...]:
	"""Devuelve los puntos activos usando el mapeo estándar bit 0->punto 1 hasta bit 7->punto 8."""
	validated = validateCellValue(value)
	return tuple(dot for dot in range(1, 9) if validated & (1 << (dot - 1)))


def cellsToActiveDots(cells: Iterable[int]) -> str:
	"""Formatea los puntos activos de todas las celdas con posiciones basadas en uno."""
	parts: list[str] = []
	for position, value in enumerate(cells, start=1):
		dots = cellToDots(value)
		dotText = "-".join(str(dot) for dot in dots) if dots else "ninguno"
		parts.append(f"{position}:{dotText}")
	return " | ".join(parts)


def cellsToDecimal(cells: Iterable[int]) -> str:
	"""Formatea una secuencia de celdas como enteros decimales."""
	return " ".join(str(validateCellValue(value)) for value in cells)


def cellsToHex(cells: Iterable[int]) -> str:
	"""Formatea una secuencia de celdas como bytes hexadecimales."""
	return " ".join(f"{validateCellValue(value):02X}" for value in cells)


def cellsToBinary(cells: Iterable[int]) -> str:
	"""Formatea una secuencia de celdas como bytes binarios."""
	return " ".join(f"{validateCellValue(value):08b}" for value in cells)


def trimTrailingBlanks(cells: Iterable[int]) -> bytes:
	"""Devuelve el buffer sin el relleno final de celdas vacías que añade NVDA."""
	return normalizeCells(cells).rstrip(b"\x00")


def countUsedCells(cells: Iterable[int]) -> int:
	"""Cuenta las celdas ocupadas hasta la última con puntos activos."""
	return len(trimTrailingBlanks(cells))


def splitIntoWindows(cells: Iterable[int], windowSize: int) -> tuple[bytes, ...]:
	"""Reparte un buffer en las ventanas sucesivas que mostraría una línea de otro tamaño.

	Sirve para responder «¿qué vería alguien con una línea de 20 celdas?» sin inventar
	traducción: se conservan exactamente los mismos bytes, sólo se agrupan distinto.
	"""
	validateCellCount(windowSize)
	rawCells = normalizeCells(cells)
	if not rawCells:
		return ()
	return tuple(rawCells[start : start + windowSize] for start in range(0, len(rawCells), windowSize))


def splitIntoRows(cells: Iterable[int], columns: int) -> tuple[bytes, ...]:
	"""Reparte un buffer en las filas de una línea braille multilínea."""
	return splitIntoWindows(cells, columns)


def compareCells(oldCells: Iterable[int], newCells: Iterable[int]) -> list[CellDifference]:
	"""Compara dos buffers y devuelve cambios, adiciones y eliminaciones por posición."""
	oldValues = normalizeCells(oldCells)
	newValues = normalizeCells(newCells)
	differences: list[CellDifference] = []
	maximumLength = max(len(oldValues), len(newValues))
	for index in range(maximumLength):
		oldValue = oldValues[index] if index < len(oldValues) else None
		newValue = newValues[index] if index < len(newValues) else None
		if oldValue == newValue:
			continue
		if oldValue is None:
			changeType = "ADDED"
		elif newValue is None:
			changeType = "REMOVED"
		else:
			changeType = "CHANGED"
		differences.append(
			CellDifference(
				position=index + 1,
				changeType=changeType,
				oldValue=oldValue,
				newValue=newValue,
			),
		)
	return differences


def formatDifferences(differences: Iterable[CellDifference]) -> str:
	"""Convierte una comparación en texto legible para el visor y los logs."""
	lines: list[str] = []
	for difference in differences:
		oldText = "—" if difference.oldValue is None else f"0x{difference.oldValue:02X}"
		newText = "—" if difference.newValue is None else f"0x{difference.newValue:02X}"
		lines.append(
			f"Celda {difference.position}: {difference.changeType} {oldText} -> {newText}",
		)
	return "\n".join(lines) if lines else "No hay diferencias."
