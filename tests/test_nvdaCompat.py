"""Pruebas de compatibilidad con las dos arquitecturas braille de NVDA."""

from __future__ import annotations

import importlib
import sys
import types
import unittest

from ._package import prepareCorePackage


class NvdaCompatibilityTests(unittest.TestCase):
	"""Comprueba la selección de clases y extensiones en NVDA 2026.1 y 2026.3."""

	def setUp(self) -> None:
		"""Conserva los módulos reales o simulados que puedan existir antes de cada prueba."""
		self.packageName = prepareCorePackage()
		self.compatibilityModuleName = f"{self.packageName}.nvdaCompat"
		self.savedModules = {
			name: module
			for name, module in sys.modules.items()
			if name in ("braille", "brailleInput") or name.startswith("braille.")
		}

	def tearDown(self) -> None:
		"""Restaura el estado global de imports después de cada arquitectura simulada."""
		for name in tuple(sys.modules):
			if name in ("braille", "brailleInput") or name.startswith("braille."):
				del sys.modules[name]
		sys.modules.update(self.savedModules)
		sys.modules.pop(self.compatibilityModuleName, None)

	def testLegacyMonolithicBrailleModule(self) -> None:
		"""Comprueba las APIs expuestas por el módulo único de NVDA 2026.1."""
		legacyBase = type("LegacyBrailleDisplayDriver", (), {})
		legacyGesture = type("LegacyBrailleDisplayGesture", (), {})
		legacyInputGesture = type("LegacyBrailleInputGesture", (), {})
		legacyExtension = object()
		brailleModule = types.ModuleType("braille")
		brailleModule.BrailleDisplayDriver = legacyBase
		brailleModule.BrailleDisplayGesture = legacyGesture
		brailleModule.pre_writeCells = legacyExtension
		brailleInputModule = types.ModuleType("brailleInput")
		brailleInputModule.BrailleInputGesture = legacyInputGesture
		sys.modules["braille"] = brailleModule
		sys.modules["brailleInput"] = brailleInputModule
		compatibility = importlib.import_module(self.compatibilityModuleName)
		self.assertIs(compatibility.BrailleDisplayDriverBase, legacyBase)
		self.assertIs(compatibility.BrailleDisplayGesture, legacyGesture)
		self.assertIs(compatibility.BrailleInputGesture, legacyInputGesture)
		self.assertIs(compatibility.preWriteCells, legacyExtension)

	def testModernBraillePackage(self) -> None:
		"""Comprueba las APIs reorganizadas como paquete en NVDA 2026.3."""
		modernBase = type("ModernBrailleDisplayDriver", (), {})
		modernGesture = type("ModernBrailleDisplayGesture", (), {})
		modernInputGesture = type("ModernBrailleInputGesture", (), {})
		modernExtension = object()
		braillePackage = types.ModuleType("braille")
		braillePackage.__path__ = []
		displayPackage = types.ModuleType("braille.display")
		displayPackage.__path__ = []
		driverModule = types.ModuleType("braille.display.driver")
		driverModule.BrailleDisplayDriver = modernBase
		displayGestureModule = types.ModuleType("braille.display.gesture")
		displayGestureModule.BrailleDisplayGesture = modernGesture
		inputPackage = types.ModuleType("braille.input")
		inputPackage.__path__ = []
		inputGestureModule = types.ModuleType("braille.input.gesture")
		inputGestureModule.BrailleInputGesture = modernInputGesture
		extensionsModule = types.ModuleType("braille.extensions")
		extensionsModule.pre_writeCells = modernExtension
		sys.modules["braille"] = braillePackage
		sys.modules["braille.display"] = displayPackage
		sys.modules["braille.display.driver"] = driverModule
		sys.modules["braille.display.gesture"] = displayGestureModule
		sys.modules["braille.input"] = inputPackage
		sys.modules["braille.input.gesture"] = inputGestureModule
		sys.modules["braille.extensions"] = extensionsModule
		compatibility = importlib.import_module(self.compatibilityModuleName)
		self.assertIs(compatibility.BrailleDisplayDriverBase, modernBase)
		self.assertIs(compatibility.BrailleDisplayGesture, modernGesture)
		self.assertIs(compatibility.BrailleInputGesture, modernInputGesture)
		self.assertIs(compatibility.preWriteCells, modernExtension)
