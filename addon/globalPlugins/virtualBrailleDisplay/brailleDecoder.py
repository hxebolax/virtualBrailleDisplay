"""Traducción inversa aproximada para presentar una ayuda legible fuera de ``display``."""

from __future__ import annotations

from collections.abc import Iterable

import braille
from logHandler import log

from .brailleUtils import normalizeCells


def backTranslateCells(cells: Iterable[int]) -> str | None:
	"""Intenta convertir celdas a texto con la tabla activa sin prometer reversibilidad exacta."""
	rawCells = normalizeCells(cells).rstrip(b"\x00")
	if not rawCells or braille.handler is None:
		return None
	table = getattr(braille.handler, "table", None)
	tableName = getattr(table, "fileName", None)
	if not tableName:
		return None
	try:
		import louisHelper

		if helper := getattr(louisHelper, "backTranslate", None):
			text = helper([tableName, "braille-patterns.cti"], list(rawCells))
		else:
			text = _backTranslateLegacy([tableName, "braille-patterns.cti"], rawCells)
	except Exception:
		log.debugWarning("No se pudo obtener una traducción inversa aproximada", exc_info=True)
		return None
	return text if text and text.strip() else None


def _backTranslateLegacy(tableList: list[str], cells: bytes) -> str:
	"""Usa directamente liblouis en NVDA 2026.1, que aún no ofrece el helper moderno."""
	import louis

	dotsIoStart = 0x8000
	inputBuffer = "".join(chr(value | dotsIoStart) for value in cells)
	return louis.backTranslate(
		tableList,
		inputBuffer,
		mode=louis.dotsIO | louis.noUndefinedDots,
	)[0]
