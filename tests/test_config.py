"""Pruebas de los accesores genéricos de configuración y de sus límites."""

from __future__ import annotations

import importlib
import unittest

from ._package import prepareCorePackage, resetConfiguration

PACKAGE_NAME = prepareCorePackage()
addonConfig = importlib.import_module(f"{PACKAGE_NAME}.config")


class ConfigurationTests(unittest.TestCase):
	"""Comprueba que toda opción declarada se lee, se valida y se guarda."""

	def setUp(self) -> None:
		"""Restaura los valores predeterminados antes de cada prueba."""
		resetConfiguration()

	def testEveryDeclaredOptionIsReadable(self) -> None:
		"""Cada clave de la especificación debe poder leerse sin errores."""
		for key in addonConfig.CONFIG_SPEC:
			with self.subTest(key=key):
				self.assertIsNotNone(addonConfig.getValue(key))

	def testBooleanOptionsRoundTrip(self) -> None:
		"""Las opciones booleanas deben conservar el valor asignado."""
		addonConfig.setBoolean("listWrapColumns", True)
		self.assertTrue(addonConfig.getBoolean("listWrapColumns"))
		addonConfig.setBoolean("listWrapColumns", False)
		self.assertFalse(addonConfig.getBoolean("listWrapColumns"))

	def testUnknownBooleanOptionIsRejected(self) -> None:
		"""Guardar una clave inexistente debe fallar en vez de crear basura."""
		with self.assertRaises(KeyError):
			addonConfig.setBoolean("opcionInexistente", True)

	def testIntegerLimitsAreEnforced(self) -> None:
		"""Los enteros fuera de rango deben rechazarse con un error explícito."""
		with self.assertRaises(ValueError):
			addonConfig.setInteger("historyLimit", 5)
		with self.assertRaises(ValueError):
			addonConfig.setInteger("rowCount", 0)

	def testCellCountValidation(self) -> None:
		"""El número de celdas debe respetar el intervalo admitido por el complemento."""
		addonConfig.setCellCount(20)
		self.assertEqual(addonConfig.getCellCount(), 20)
		with self.assertRaises(ValueError):
			addonConfig.setCellCount(0)
		with self.assertRaises(ValueError):
			addonConfig.setCellCount(257)

	def testRowCountRoundTrip(self) -> None:
		"""El número de filas simuladas debe conservarse."""
		addonConfig.setRowCount(4)
		self.assertEqual(addonConfig.getRowCount(), 4)

	def testListAnnouncementOptionsExposeEveryFlag(self) -> None:
		"""El resumen de opciones de lectura debe incluir todas las claves esperadas."""
		options = addonConfig.getListAnnouncementOptions()
		self.assertEqual(
			set(options),
			{
				"rowNumber",
				"columnHeader",
				"cellValue",
				"totalRows",
				"emptyCells",
				"wrapColumns",
				"speakOnly",
			},
		)

	def testTextOptionsRoundTrip(self) -> None:
		"""Las opciones de texto deben normalizar los valores vacíos."""
		addonConfig.setText("continuousLogPath", "")
		self.assertEqual(addonConfig.getText("continuousLogPath"), "")
		addonConfig.setText("continuousLogFormat", "txt")
		self.assertEqual(addonConfig.getText("continuousLogFormat"), "txt")

	def testAnnouncementModeRoundTrip(self) -> None:
		"""El modo de aviso debe conservar cualquiera de sus tres valores admitidos."""
		for mode in ("speech", "dialog", "both"):
			with self.subTest(mode=mode):
				addonConfig.setText("actionAnnouncementMode", mode)
				self.assertEqual(addonConfig.getText("actionAnnouncementMode"), mode)

	def testAnnouncementModeDefaultsToSpeech(self) -> None:
		"""De fábrica los avisos deben leerse, no abrir cuadros de mensaje."""
		self.assertEqual(addonConfig.getText("actionAnnouncementMode"), "speech")
