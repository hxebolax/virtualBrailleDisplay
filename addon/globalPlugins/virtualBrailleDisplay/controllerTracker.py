"""Hook reversible del callback nativo de NVDA Controller Client para braille."""

from __future__ import annotations

from collections.abc import Callable
from ctypes import WINFUNCTYPE, byref, c_long, c_wchar_p

import NVDAHelper
import appModuleHandler
import winBindings.rpcrt4
from logHandler import log

from .frameStore import FrameStore


class ControllerTracker:
	"""Intercepta exclusivamente ``nvdaController_brailleMessage`` antes de delegar en NVDA."""

	def __init__(self, frameStore: FrameStore):
		"""Conserva el almacén y prepara un hook inicialmente inactivo."""
		self._frameStore = frameStore
		self._installed = False
		self._originalCallback: Callable[[str], int] | None = None
		self._wrappedCallback: Callable[[str], int] | None = None

	@property
	def installed(self) -> bool:
		"""Indica si el puntero nativo está redirigido al wrapper."""
		return self._installed

	def install(self) -> bool:
		"""Instala una única vez el hook privado tras validar los símbolos requeridos."""
		if self._installed:
			return True
		originalCallback = getattr(NVDAHelper, "nvdaController_brailleMessage", None)
		setPointer = getattr(NVDAHelper, "_setDllFuncPointer", None)
		localLibrary = getattr(NVDAHelper, "localLib", None)
		if originalCallback is None or setPointer is None or localLibrary is None:
			log.warning("No se puede activar el seguimiento de NVDA Controller Client: API interna ausente")
			return False
		callbackType = WINFUNCTYPE(c_long, c_wchar_p)
		wrappedCallback = callbackType(self._handleBrailleMessage)
		try:
			setPointer(localLibrary.dll, "_nvdaController_brailleMessage", wrappedCallback)
		except Exception:
			log.error("No se pudo instalar el hook de NVDA Controller Client", exc_info=True)
			return False
		self._originalCallback = originalCallback
		self._wrappedCallback = wrappedCallback
		self._installed = True
		log.info("Seguimiento de mensajes braille de NVDA Controller Client activado")
		return True

	def uninstall(self) -> None:
		"""Restaura exactamente el callback que NVDA había registrado."""
		if not self._installed or self._originalCallback is None:
			return
		try:
			NVDAHelper._setDllFuncPointer(
				NVDAHelper.localLib.dll,
				"_nvdaController_brailleMessage",
				self._originalCallback,
			)
		except Exception:
			log.error("No se pudo restaurar el callback de NVDA Controller Client", exc_info=True)
		else:
			log.info("Seguimiento de mensajes braille de NVDA Controller Client desactivado")
		finally:
			self._installed = False
			self._wrappedCallback = None
			self._originalCallback = None

	def _handleBrailleMessage(self, text: str | None) -> int:
		"""Registra el nivel A sin interferir con el resultado devuelto por NVDA."""
		try:
			processId, processName = self._getCallingProcess()
			self._frameStore.addExternalEvent(
				text=text or "",
				sourceApi="NVDA Controller Client: nvdaController_brailleMessage",
				processId=processId,
				processName=processName,
			)
		except Exception:
			log.error("Error registrando una solicitud braille externa", exc_info=True)
		originalCallback = self._originalCallback
		if originalCallback is None:
			return 120
		return int(originalCallback(text))

	@staticmethod
	def _getCallingProcess() -> tuple[int | None, str | None]:
		"""Consulta PID y ejecutable mientras el hilo aún atiende la llamada RPC local."""
		processIdValue = c_long()
		try:
			status = winBindings.rpcrt4.I_RpcBindingInqLocalClientPID(
				None,
				byref(processIdValue),
			)
		except Exception:
			log.debugWarning("No se pudo consultar el PID del cliente RPC", exc_info=True)
			return None, None
		processId = int(processIdValue.value)
		if status != 0 or processId <= 0:
			return None, None
		try:
			processName = appModuleHandler.getAppNameFromProcessID(processId, includeExt=True) or None
		except Exception:
			log.debugWarning(
				f"No se pudo resolver el ejecutable del cliente RPC con PID {processId}",
				exc_info=True,
			)
			processName = None
		return processId, processName
