"""Gestos simulados de la línea braille virtual: teclas de encaminamiento y entrada de puntos.

Se usan las clases reales de gestos braille de NVDA para que el complemento no invente
ningún camino alternativo: NVDA procesa estos gestos igual que los de una línea física.
"""

from __future__ import annotations

from logHandler import log

from .nvdaCompat import BrailleDisplayGesture, BrailleInputGesture

DRIVER_NAME = "virtualBraille"


class RouteToGesture(BrailleDisplayGesture):
	"""Reproduce la pulsación de una tecla de encaminamiento sobre una celda concreta."""

	source = DRIVER_NAME
	id = "route"

	def __init__(self, cellIndex: int):
		"""Asocia el gesto a la celda indicada y al script estándar de encaminamiento."""
		super().__init__()
		self.cellIndexes = [int(cellIndex)]
		import globalCommands

		self.script = globalCommands.commands.script_braille_routeTo


class DotsInputGesture(BrailleDisplayGesture, BrailleInputGesture):
	"""Reproduce la pulsación de un acorde del teclado braille de una línea física."""

	source = DRIVER_NAME

	def __init__(self, dots: int, space: bool = False):
		"""Construye el acorde con la máscara de puntos 1 a 8 y la barra espaciadora."""
		super().__init__()
		self.dots = int(dots)
		self.space = bool(space)
		self.id = self._makeDotsId()


def executeGesture(gesture: BrailleDisplayGesture) -> bool:
	"""Entrega el gesto a NVDA informando de si pudo procesarse."""
	import inputCore

	try:
		inputCore.manager.executeGesture(gesture)
	except Exception:
		log.debugWarning("NVDA no aceptó el gesto simulado de la línea virtual", exc_info=True)
		return False
	return True
