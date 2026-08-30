"""Pruebas de traducción inversa aproximada en NVDA antiguo y moderno."""

from __future__ import annotations

import importlib
import sys
import types
import unittest

from ._package import prepareCorePackage


class _FakeLog:
	"""Acepta diagnósticos esperados del decodificador durante las pruebas."""

	def debugWarning(self, message: str, exc_info: bool = False) -> None:
		"""Ignora un diagnóstico detallado simulado."""


class BrailleDecoderTests(unittest.TestCase):
	"""Comprueba las rutas moderna y clásica sin ejecutar liblouis real."""

	def setUp(self) -> None:
		"""Registra un manejador braille y conserva los módulos globales sustituidos."""
		self.packageName = prepareCorePackage()
		self.moduleName = f"{self.packageName}.brailleDecoder"
		self.moduleNames = ("braille", "logHandler", "louisHelper", "louis")
		self.savedModules = {name: sys.modules.get(name) for name in self.moduleNames}
		brailleModule = types.ModuleType("braille")
		brailleModule.handler = types.SimpleNamespace(
			table=types.SimpleNamespace(fileName="tabla-prueba.ctb"),
		)
		sys.modules["braille"] = brailleModule
		logHandler = types.ModuleType("logHandler")
		logHandler.log = _FakeLog()
		sys.modules["logHandler"] = logHandler

	def tearDown(self) -> None:
		"""Restaura los módulos sustituidos y fuerza una importación limpia posterior."""
		for name, module in self.savedModules.items():
			if module is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = module
		sys.modules.pop(self.moduleName, None)

	def testModernHelperBackTranslation(self) -> None:
		"""Comprueba que NVDA moderno use louisHelper y elimine el relleno final."""
		calls: list[tuple[list[str], list[int]]] = []
		louisHelper = types.ModuleType("louisHelper")

		def backTranslate(tables: list[str], cells: list[int]) -> str:
			"""Conserva los argumentos y devuelve un texto conocido."""
			calls.append((tables, cells))
			return "texto moderno"

		louisHelper.backTranslate = backTranslate
		sys.modules["louisHelper"] = louisHelper
		decoder = importlib.import_module(self.moduleName)
		self.assertEqual(decoder.backTranslateCells((1, 2, 0, 0)), "texto moderno")
		self.assertEqual(calls[0][1], [1, 2])

	def testLegacyDirectLibLouisBackTranslation(self) -> None:
		"""Comprueba la llamada directa necesaria en NVDA 2026.1."""
		louisHelper = types.ModuleType("louisHelper")
		sys.modules["louisHelper"] = louisHelper
		louis = types.ModuleType("louis")
		louis.dotsIO = 1
		louis.noUndefinedDots = 2

		def backTranslate(tables: list[str], inputBuffer: str, mode: int):
			"""Devuelve un texto conocido para el buffer de puntos simulado."""
			return "texto clásico", (), (), 0

		louis.backTranslate = backTranslate
		sys.modules["louis"] = louis
		decoder = importlib.import_module(self.moduleName)
		self.assertEqual(decoder.backTranslateCells((1, 2)), "texto clásico")
