"""Selección del texto legible de un frame indicando siempre de dónde procede."""

from __future__ import annotations

import addonHandler

addonHandler.initTranslation()

from .brailleDecoder import backTranslateCells  # noqa: E402
from .models import BrailleFrame  # noqa: E402


def readableTextForFrame(frame: BrailleFrame) -> tuple[str, str]:
	"""Elige el texto más fiable y deja clara su procedencia o su carácter aproximado."""
	if frame.associatedText and frame.associatedText.strip():
		return frame.associatedText, _("Texto exacto asociado por NVDA a esta ventana braille")
	if frame.requestedText and frame.requestedText.strip():
		return frame.requestedText, _("Texto solicitado por una aplicación; asociación probable")
	if decodedText := backTranslateCells(frame.cellsRaw):
		return decodedText, _("Traducción inversa aproximada con la tabla braille activa")
	return (
		_("No hay texto legible disponible para este frame."),
		_("No disponible; consulte las celdas técnicas si necesita el patrón exacto"),
	)


def historyReadableText(frame: BrailleFrame) -> str:
	"""Devuelve texto barato para una fila sin traducir inversamente historiales completos."""
	return frame.associatedText or frame.requestedText or _("Sin texto legible")
