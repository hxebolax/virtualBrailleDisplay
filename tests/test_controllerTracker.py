"""Pruebas del hook nativo reversible con símbolos NVDA simulados."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from ctypes import WINFUNCTYPE, c_long, c_wchar_p

from ._package import prepareCorePackage


class _FakeLog:
	"""Acepta los niveles de log usados por el componente bajo prueba."""

	def warning(self, message: str) -> None:
		"""Ignora una advertencia esperada durante pruebas."""

	def error(self, message: str, exc_info: bool = False) -> None:
		"""Ignora un error simulado durante pruebas."""

	def info(self, message: str) -> None:
		"""Ignora un mensaje informativo durante pruebas."""

	def debugWarning(self, message: str, exc_info: bool = False) -> None:
		"""Ignora un diagnóstico detallado durante pruebas."""


class ControllerTrackerTests(unittest.TestCase):
	"""Verifica instalación única, captura, delegación y restauración."""

	def setUp(self) -> None:
		"""Registra sustitutos mínimos antes de importar el componente."""
		self.packageName = prepareCorePackage()
		self.originalCalls: list[str | None] = []
		self.pointerAssignments: list[object] = []
		callbackType = WINFUNCTYPE(c_long, c_wchar_p)

		def originalCallback(text: str | None) -> int:
			"""Simula el callback original de NVDA y conserva sus argumentos."""
			self.originalCalls.append(text)
			return 0

		self.originalCallback = callbackType(originalCallback)
		nvdaHelper = types.ModuleType("NVDAHelper")
		nvdaHelper.nvdaController_brailleMessage = self.originalCallback
		nvdaHelper.localLib = types.SimpleNamespace(dll=object())

		def setPointer(dll: object, name: str, callback: object) -> None:
			"""Conserva cada callback que el componente intenta registrar."""
			self.pointerAssignments.append(callback)

		nvdaHelper._setDllFuncPointer = setPointer
		sys.modules["NVDAHelper"] = nvdaHelper
		logHandler = types.ModuleType("logHandler")
		logHandler.log = _FakeLog()
		sys.modules["logHandler"] = logHandler
		appModuleHandler = types.ModuleType("appModuleHandler")

		def getAppNameFromProcessID(processId: int, includeExt: bool = False) -> str:
			"""Devuelve un ejecutable conocido para el PID simulado."""
			return "cliente-prueba.exe" if includeExt else "cliente-prueba"

		appModuleHandler.getAppNameFromProcessID = getAppNameFromProcessID
		sys.modules["appModuleHandler"] = appModuleHandler
		winBindings = types.ModuleType("winBindings")
		winBindings.__path__ = []
		rpcrt4 = types.ModuleType("winBindings.rpcrt4")

		def getLocalClientPid(binding: object, processIdPointer: object) -> int:
			"""Escribe un PID simulado en el puntero de salida de ctypes."""
			processIdPointer._obj.value = 4242
			return 0

		rpcrt4.I_RpcBindingInqLocalClientPID = getLocalClientPid
		winBindings.rpcrt4 = rpcrt4
		sys.modules["winBindings"] = winBindings
		sys.modules["winBindings.rpcrt4"] = rpcrt4
		sys.modules.pop(f"{self.packageName}.controllerTracker", None)
		self.module = importlib.import_module(f"{self.packageName}.controllerTracker")
		self.frameStoreModule = importlib.import_module(f"{self.packageName}.frameStore")

	def testHookCapturesDelegatesAndRestores(self) -> None:
		"""Comprueba el ciclo completo sin alterar el código original simulado."""
		store = self.frameStoreModule.FrameStore()
		tracker = self.module.ControllerTracker(store)
		self.assertTrue(tracker.install())
		self.assertTrue(tracker.install())
		self.assertEqual(len(self.pointerAssignments), 1)
		result = self.pointerAssignments[0]("Hola externa")
		self.assertEqual(result, 0)
		self.assertEqual(self.originalCalls, ["Hola externa"])
		self.assertEqual(store.getEvents()[0].text, "Hola externa")
		self.assertEqual(store.getEvents()[0].processId, 4242)
		self.assertEqual(store.getEvents()[0].processName, "cliente-prueba.exe")
		tracker.uninstall()
		self.assertIs(self.pointerAssignments[-1], self.originalCallback)
		self.assertFalse(tracker.installed)
