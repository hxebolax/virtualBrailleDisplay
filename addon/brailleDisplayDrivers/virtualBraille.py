"""Driver seleccionable de la línea braille virtual."""

from __future__ import annotations

import addonHandler

addonHandler.initTranslation()

from globalPlugins.virtualBrailleDisplay import config as addonConfig  # noqa: E402
from globalPlugins.virtualBrailleDisplay.nvdaCompat import BrailleDisplayDriverBase  # noqa: E402
from globalPlugins.virtualBrailleDisplay.runtime import runtime  # noqa: E402


class BrailleDisplayDriver(BrailleDisplayDriverBase):
	"""Driver sin hardware que recibe y registra el buffer final producido por NVDA."""

	name = "virtualBraille"
	description = _("Virtual Braille Display")
	isThreadSafe = False
	supportsAutomaticDetection = False
	receivesAckPackets = False

	@classmethod
	def check(cls) -> bool:
		"""Indica que el driver virtual siempre está disponible para selección manual."""
		return True

	def __init__(self, port: str | None = None):
		"""Inicializa la geometría persistida, admitiendo líneas de varias filas."""
		super().__init__(port=port)
		# En líneas multilínea NVDA exige fijar numCols y numRows, nunca numCells.
		self.numRows = addonConfig.getRowCount()
		self.numCols = addonConfig.getCellCount()
		runtime.setDriverConnected(True)

	def display(self, cells: list[int]) -> None:
		"""Captura exactamente las celdas entregadas por NVDA y retorna sin realizar E/S."""
		runtime.captureDisplay(cells)

	def terminate(self) -> None:
		"""Finaliza el driver y conserva los historiales del complemento."""
		try:
			super().terminate()
		finally:
			runtime.setDriverConnected(False)
