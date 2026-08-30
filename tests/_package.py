"""Carga aislada de los módulos puros sin requerir una instalación de NVDA."""

from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path

PACKAGE_NAME = "virtualBrailleDisplayTestCore"

# Valores equivalentes a los predeterminados declarados en config.CONFIG_SPEC.
DEFAULT_CONFIGURATION = {
	"cellCount": 40,
	"rowCount": 1,
	"historyLimit": 1000,
	"correlationWindowMs": 1500,
	"temporalFallbackMs": 250,
	"listAnnounceRowNumber": True,
	"listAnnounceColumnHeader": True,
	"listAnnounceCellValue": True,
	"listAnnounceTotalRows": False,
	"listAnnounceEmptyCells": True,
	"listWrapColumns": False,
	"listSpeakOnly": False,
	"actionAnnouncementMode": "speech",
	"followLatestFrame": True,
	"openSimpleViewFirst": False,
	"ignoreEmptyFrames": False,
	"ignoreRepeatedFrames": False,
	"filterFocusedApplication": False,
	"resourceUpdatesEnabled": True,
	"resourceUpdateIntervalHours": 24,
	"continuousLogging": False,
	"continuousLogFormat": "jsonl",
	"continuousLogPath": "",
}


class _FakeConfiguration(dict):
	"""Imita la parte mínima de ``config.conf`` usada por las pruebas."""

	def __init__(self):
		"""Crea valores equivalentes a los predeterminados del complemento."""
		super().__init__({"virtualBrailleDisplay": dict(DEFAULT_CONFIGURATION)})
		self.spec: dict[str, object] = {}


def _installTranslationBuiltins() -> None:
	"""Instala las funciones de traducción que NVDA proporciona globalmente."""
	if not hasattr(builtins, "_"):
		builtins._ = lambda text: text
	if not hasattr(builtins, "ngettext"):
		builtins.ngettext = lambda singular, plural, count: singular if count == 1 else plural


def _installAddonHandlerStub() -> None:
	"""Registra un ``addonHandler`` mínimo para los módulos que traducen sus textos."""
	if "addonHandler" in sys.modules:
		return
	addonHandlerModule = types.ModuleType("addonHandler")
	addonHandlerModule.initTranslation = lambda: None
	sys.modules["addonHandler"] = addonHandlerModule


def prepareCorePackage() -> str:
	"""Registra un paquete de prueba y los módulos mínimos que espera el complemento."""
	_installTranslationBuiltins()
	_installAddonHandlerStub()
	if "config" not in sys.modules:
		configModule = types.ModuleType("config")
		configModule.conf = _FakeConfiguration()
		sys.modules["config"] = configModule
	if PACKAGE_NAME not in sys.modules:
		package = types.ModuleType(PACKAGE_NAME)
		package.__path__ = [
			str(
				Path(__file__).resolve().parents[1] / "addon" / "globalPlugins" / "virtualBrailleDisplay",
			),
		]
		package.__package__ = PACKAGE_NAME
		sys.modules[PACKAGE_NAME] = package
	return PACKAGE_NAME


def resetConfiguration() -> None:
	"""Devuelve la configuración simulada a sus valores predeterminados."""
	import config as nvdaConfig

	nvdaConfig.conf["virtualBrailleDisplay"] = dict(DEFAULT_CONFIGURATION)
