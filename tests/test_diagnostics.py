"""Pruebas de la explicación en lenguaje humano y de la revisión automática."""

from __future__ import annotations

import importlib
import unittest

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
diagnostics = importlib.import_module(f"{PACKAGE_NAME}.diagnostics")
frameStoreModule = importlib.import_module(f"{PACKAGE_NAME}.frameStore")
models = importlib.import_module(f"{PACKAGE_NAME}.models")


def buildFrame(cells: bytes, context: object | None = None) -> object:
	"""Crea un frame real a través del almacén para no duplicar la materialización."""
	store = frameStoreModule.FrameStore()
	origin = models.FrameOrigin(context=context or models.FrameContext())
	return store.captureFrame(cells, origin)


class DiagnosticsTests(unittest.TestCase):
	"""Comprueba las observaciones que se ofrecen a personas sin conocimientos de braille."""

	def testBlankFrameIsReportedAsWarning(self) -> None:
		"""Un frame sin puntos debe avisar de que la línea se queda en blanco."""
		frame = buildFrame(bytes(40))
		observations = diagnostics.analyzeFrame(frame, "")
		self.assertTrue(
			any(item.severity is diagnostics.Severity.WARNING for item in observations),
		)

	def testFullLineIsReportedAsPossiblyTruncated(self) -> None:
		"""Ocupar todas las celdas debe avisar de un posible recorte del texto."""
		frame = buildFrame(bytes([0x2D] * 40))
		titles = [item.title for item in diagnostics.analyzeFrame(frame, "texto")]
		self.assertIn(_("El contenido llena la línea completa"), titles)

	def testShortContentProducesNoWarning(self) -> None:
		"""Un contenido breve con texto legible no debe generar ningún aviso."""
		frame = buildFrame(bytes([0x2D, 0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
		severities = {item.severity for item in diagnostics.analyzeFrame(frame, "hola")}
		self.assertNotIn(diagnostics.Severity.WARNING, severities)

	def testOccupancyCountsOnlyUsedCells(self) -> None:
		"""La ocupación debe ignorar el relleno final de celdas vacías."""
		frame = buildFrame(bytes([0x2D, 0x15] + [0x00] * 38))
		self.assertEqual(frame.usedCells, 2)
		self.assertIn("2", diagnostics.describeOccupancy(frame))

	def testApplicationDescriptionNeverInvented(self) -> None:
		"""Sin contexto de proceso se debe indicar que el dato no está disponible."""
		frame = buildFrame(bytes([0x2D]))
		self.assertEqual(diagnostics.describeApplication(frame), _("No disponible"))

	def testApplicationDescriptionUsesRealContext(self) -> None:
		"""Con contexto de proceso se deben mostrar nombre y PID observados."""
		context = models.FrameContext(processId=4321, processName="miPrograma.exe")
		frame = buildFrame(bytes([0x2D]), context)
		description = diagnostics.describeApplication(frame)
		self.assertIn("miPrograma.exe", description)
		self.assertIn("4321", description)

	def testPlainReportContainsTextAndReview(self) -> None:
		"""El informe completo debe incluir el texto legible y la revisión automática."""
		frame = buildFrame(bytes([0x2D, 0x15]))
		report = diagnostics.buildPlainReport(frame, "hola", "origen de prueba")
		self.assertIn("hola", report)
		self.assertIn(_("Revisión automática:"), report)
