"""Estado compartido entre el global plugin, el driver y el visor."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable

import braille
from logHandler import log

from . import config as addonConfig
from .contextTracker import readCurrentContext, resetObjectCache
from .controllerTracker import ControllerTracker
from .frameStore import FrameStore
from .logWriter import ContinuousLogger
from .models import ApplicationFilter, BrailleFrame, ExternalBrailleEvent, FrameOrigin
from .nvdaCompat import preWriteCells
from .originTracker import OriginTracker

DRIVER_NAME = "virtualBraille"
NO_BRAILLE_DRIVER_NAME = "noBraille"
StatusListener = Callable[[bool], None]
FilterListener = Callable[[ApplicationFilter], None]


class RuntimeState:
	"""Coordina captura, correlación, estado lógico y ciclo de vida del complemento."""

	def __init__(self):
		"""Crea los servicios compartidos sin registrar todavía hooks de NVDA."""
		self.frameStore = FrameStore()
		self.originTracker = OriginTracker(self.frameStore)
		self.controllerTracker = ControllerTracker(self.frameStore)
		self.continuousLogger = ContinuousLogger()
		self._lock = threading.RLock()
		self._initialized = False
		self._driverConnected = False
		self._statusListeners: set[StatusListener] = set()
		self._filterListeners: set[FilterListener] = set()
		self._applicationFilter = ApplicationFilter()
		self._lastStoredCells: bytes | None = None

	@property
	def driverConnected(self) -> bool:
		"""Indica si hay una instancia activa del driver virtual."""
		with self._lock:
			return self._driverConnected

	@property
	def applicationFilter(self) -> ApplicationFilter:
		"""Devuelve el filtro de aplicación vigente en el visor."""
		with self._lock:
			return self._applicationFilter

	def initialize(self) -> None:
		"""Registra la configuración y los puntos de captura una sola vez."""
		with self._lock:
			if self._initialized:
				return
			addonConfig.initializeConfig()
			self.frameStore.setMaximumItems(addonConfig.getHistoryLimit())
			preWriteCells.register(self._onPreWriteCells)
			self.controllerTracker.install()
			self.frameStore.registerEventListener(self._onExternalEvent)
			self._initialized = True
		self.applyContinuousLoggingSettings()

	def terminate(self) -> None:
		"""Desregistra hooks y observadores temporales sin borrar el historial antes de cerrar."""
		with self._lock:
			if not self._initialized:
				return
			self._initialized = False
		try:
			preWriteCells.unregister(self._onPreWriteCells)
		except Exception:
			log.debugWarning("No se pudo retirar pre_writeCells", exc_info=True)
		self.frameStore.unregisterEventListener(self._onExternalEvent)
		self.controllerTracker.uninstall()
		self.originTracker.reset()
		resetObjectCache()
		self.continuousLogger.stop()

	def captureDisplay(self, cells: Iterable[int]) -> BrailleFrame | None:
		"""Captura la colección recibida por el driver como única fuente de verdad del frame."""
		try:
			origin = self.originTracker.consumeForDisplay(cells)
		except Exception:
			log.error("Error calculando el origen del frame", exc_info=True)
			origin = FrameOrigin()
		if not self._shouldStore(cells):
			return None
		frame = self.frameStore.captureFrame(cells, origin)
		if frame.correlatedEventId is not None and frame.correlationReason is not None:
			self.frameStore.markEventCorrelated(
				eventId=frame.correlatedEventId,
				frameId=frame.frameId,
				confidence=frame.originConfidence,
				reason=frame.correlationReason,
			)
		if self.continuousLogger.active:
			self.continuousLogger.logFrame(frame)
		return frame

	def setDriverConnected(self, connected: bool) -> None:
		"""Actualiza el estado lógico y notifica cambios reales de conexión."""
		with self._lock:
			if self._driverConnected == bool(connected):
				return
			self._driverConnected = bool(connected)
			listeners = tuple(self._statusListeners)
		for listener in listeners:
			try:
				listener(bool(connected))
			except Exception:
				log.error("Error notificando el estado del driver virtual", exc_info=True)

	def registerStatusListener(self, listener: StatusListener) -> None:
		"""Registra un observador del estado lógico del driver."""
		with self._lock:
			self._statusListeners.add(listener)

	def unregisterStatusListener(self, listener: StatusListener) -> None:
		"""Retira un observador del estado lógico del driver."""
		with self._lock:
			self._statusListeners.discard(listener)

	def registerFilterListener(self, listener: FilterListener) -> None:
		"""Registra un observador de los cambios del filtro por aplicación."""
		with self._lock:
			self._filterListeners.add(listener)

	def unregisterFilterListener(self, listener: FilterListener) -> None:
		"""Retira un observador del filtro por aplicación."""
		with self._lock:
			self._filterListeners.discard(listener)

	def setApplicationFilter(self, processId: int | None, processName: str | None = None) -> None:
		"""Fija o retira el proceso al que se limitan las vistas del visor."""
		newFilter = ApplicationFilter(processId=processId, processName=processName)
		with self._lock:
			if self._applicationFilter == newFilter:
				return
			self._applicationFilter = newFilter
			listeners = tuple(self._filterListeners)
		for listener in listeners:
			try:
				listener(newFilter)
			except Exception:
				log.error("Error notificando el filtro por aplicación", exc_info=True)

	def clearApplicationFilter(self) -> None:
		"""Vuelve a mostrar los frames de todas las aplicaciones."""
		self.setApplicationFilter(None, None)

	@staticmethod
	def getFocusedApplication() -> tuple[int | None, str | None]:
		"""Devuelve PID y nombre de la aplicación del usuario que tiene el foco.

		Se consulta en el momento en que el usuario pide el filtro, antes de abrir ninguna
		ventana del complemento. Nunca devuelve el propio proceso de NVDA: si el foco está
		en una ventana de NVDA, como su menú o el visor, se usa el objeto que NVDA guarda
		en ``gui.mainFrame.prevFocus`` al abrir un menú, que es exactamente la aplicación
		desde la que el usuario lo abrió. Esta información es contexto elegido por el
		usuario, no una atribución de origen del frame.
		"""
		for candidate in RuntimeState._focusCandidates():
			processId = getattr(candidate, "processID", None)
			if not isinstance(processId, int) or processId <= 0:
				continue
			if processId == RuntimeState._nvdaProcessId():
				continue
			appModule = getattr(candidate, "appModule", None)
			processName = getattr(appModule, "appName", None)
			return processId, str(processName) if processName else None
		return None, None

	@staticmethod
	def _focusCandidates() -> tuple[object, ...]:
		"""Enumera, en orden de preferencia, los objetos que pueden identificar la aplicación."""
		candidates: list[object] = []
		try:
			import api

			focusObject = api.getFocusObject()
		except Exception:
			log.debugWarning("No se pudo consultar el objeto con foco", exc_info=True)
			focusObject = None
		if focusObject is not None:
			candidates.append(focusObject)
		try:
			import gui as nvdaGui

			previousFocus = getattr(nvdaGui.mainFrame, "prevFocus", None)
		except Exception:
			previousFocus = None
		if previousFocus is not None:
			candidates.append(previousFocus)
		return tuple(candidates)

	@staticmethod
	def _nvdaProcessId() -> int | None:
		"""Devuelve el identificador del proceso de NVDA para poder descartarlo."""
		try:
			import globalVars

			return int(globalVars.appPid)
		except Exception:
			return None

	def connectDriver(self) -> bool:
		"""Selecciona Virtual Braille Display mediante el gestor real de drivers de NVDA."""
		if braille.handler is None:
			return False
		return bool(braille.handler.setDisplayByName(DRIVER_NAME))

	def disconnectDriver(self) -> bool:
		"""Selecciona «sin braille» para simular una desconexión lógica controlada."""
		if braille.handler is None:
			return False
		return bool(braille.handler.setDisplayByName(NO_BRAILLE_DRIVER_NAME))

	def applyDisplayGeometry(self, cellCount: int, rowCount: int) -> bool:
		"""Guarda tamaño y filas y reinicializa el driver para que NVDA vuelva a traducir."""
		oldCellCount = addonConfig.getCellCount()
		oldRowCount = addonConfig.getRowCount()
		addonConfig.setCellCount(cellCount)
		addonConfig.setRowCount(rowCount)
		if (oldCellCount, oldRowCount) == (cellCount, rowCount) or braille.handler is None:
			return True
		if braille.handler.display is None or braille.handler.display.name != DRIVER_NAME:
			return True
		if not braille.handler.setDisplayByName(NO_BRAILLE_DRIVER_NAME, isFallback=True):
			return False
		return bool(braille.handler.setDisplayByName(DRIVER_NAME))

	def applyCellCount(self, cellCount: int) -> bool:
		"""Cambia sólo el número de celdas conservando el número de filas configurado."""
		return self.applyDisplayGeometry(cellCount, addonConfig.getRowCount())

	def applyHistoryLimit(self, historyLimit: int) -> None:
		"""Actualiza a la vez la configuración y la capacidad del almacén."""
		addonConfig.setHistoryLimit(historyLimit)
		self.frameStore.setMaximumItems(historyLimit)

	def applyContinuousLoggingSettings(self) -> None:
		"""Arranca o detiene el registro continuo según la configuración persistida."""
		enabled = addonConfig.getBoolean("continuousLogging")
		path = addonConfig.getText("continuousLogPath")
		formatName = addonConfig.getText("continuousLogFormat") or "jsonl"
		if not enabled or not path:
			self.continuousLogger.stop()
			return
		try:
			self.continuousLogger.start(path, formatName)
		except Exception:
			log.error("No se pudo iniciar el registro continuo", exc_info=True)
			addonConfig.setBoolean("continuousLogging", False)
			self.continuousLogger.stop()

	def routeToCell(self, cellIndex: int) -> bool:
		"""Simula una tecla de encaminamiento sobre la celda indicada."""
		from .gestures import RouteToGesture, executeGesture

		if not self.driverConnected:
			return False
		return executeGesture(RouteToGesture(cellIndex))

	def sendBrailleDots(self, dots: int, space: bool = False) -> bool:
		"""Simula un acorde del teclado braille de la línea."""
		from .gestures import DotsInputGesture, executeGesture

		if not self.driverConnected:
			return False
		return executeGesture(DotsInputGesture(dots, space))

	@staticmethod
	def scrollForward() -> bool:
		"""Desplaza la ventana braille hacia adelante usando la API de NVDA."""
		if braille.handler is None:
			return False
		braille.handler.scrollForward()
		return True

	@staticmethod
	def scrollBack() -> bool:
		"""Desplaza la ventana braille hacia atrás usando la API de NVDA."""
		if braille.handler is None:
			return False
		braille.handler.scrollBack()
		return True

	def _shouldStore(self, cells: Iterable[int]) -> bool:
		"""Aplica los filtros de captura sin encarecer la ruta rápida del driver."""
		ignoreEmpty = addonConfig.getBoolean("ignoreEmptyFrames")
		ignoreRepeated = addonConfig.getBoolean("ignoreRepeatedFrames")
		if not ignoreEmpty and not ignoreRepeated:
			self._lastStoredCells = None
			return True
		rawCells = bytes(cells)
		if ignoreEmpty and not rawCells.rstrip(b"\x00"):
			return False
		if ignoreRepeated and rawCells == self._lastStoredCells:
			return False
		self._lastStoredCells = rawCells
		return True

	def _onExternalEvent(self, event: ExternalBrailleEvent) -> None:
		"""Envía también las solicitudes externas al registro continuo cuando está activo."""
		if event.correlatedFrameId is None and self.continuousLogger.active:
			self.continuousLogger.logEvent(event)

	def _onPreWriteCells(self, cells: list[int], rawText: str, currentCellCount: int) -> None:
		"""Adapta el punto de extensión público de NVDA al correlador interno."""
		try:
			context = readCurrentContext(currentCellCount)
			self.originTracker.notePreWrite(cells, rawText, currentCellCount, context)
		except Exception:
			log.error("Error capturando el contexto pre_writeCells", exc_info=True)


runtime = RuntimeState()
