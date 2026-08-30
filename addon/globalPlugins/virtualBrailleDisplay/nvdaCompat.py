"""Compatibilidad localizada entre el módulo braille clásico y el paquete moderno de NVDA."""

from __future__ import annotations

import braille

try:
	from braille.display.driver import BrailleDisplayDriver as BrailleDisplayDriverBase
	from braille.display.gesture import BrailleDisplayGesture
	from braille.extensions import pre_writeCells as preWriteCells
	from braille.input.gesture import BrailleInputGesture
except ImportError:
	# NVDA 2026.1 mantiene la clase y el punto de extensión en el módulo braille único.
	import brailleInput

	BrailleDisplayDriverBase = braille.BrailleDisplayDriver
	BrailleDisplayGesture = braille.BrailleDisplayGesture
	preWriteCells = braille.pre_writeCells
	BrailleInputGesture = brailleInput.BrailleInputGesture
