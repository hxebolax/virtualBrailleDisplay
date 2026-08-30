"""Interfaz wx accesible para inspeccionar frames y eventos externos."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import addonHandler
import api
import gui as nvdaGui
import wx
from gui import guiHelper
from gui.message import DialogType

addonHandler.initTranslation()

from . import config as addonConfig  # noqa: E402
from .accessibleList import AccessibleListCtrl, announce  # noqa: E402
from .brailleUtils import compareCells, splitIntoWindows  # noqa: E402
from .diagnostics import (  # noqa: E402
	bufferLabel,
	confidenceLabel,
	describeApplication,
	describeCell,
	describeOccupancy,
	originLabel,
)
from .frameText import historyReadableText, readableTextForFrame  # noqa: E402
from .guiUtils import (  # noqa: E402
	addExpandingControl,
	addLabel,
	addReadOnlyText,
	confirm,
	setButtonLabel,
	showMessage,
)
from .logWriter import saveRecords  # noqa: E402
from .messages import reportAction  # noqa: E402
from .models import BrailleFrame, ExternalBrailleEvent  # noqa: E402
from .runtime import RuntimeState  # noqa: E402
from .settingsDialog import showSettingsDialog  # noqa: E402

# Tamaños ofrecidos en la simulación de otras líneas braille.
SIMULATION_SIZES = (14, 20, 32, 40, 64, 80)
# Número de frames ofrecidos en los desplegables de comparación.
COMPARISON_CHOICE_LIMIT = 100


def _frameColumns() -> tuple[tuple[str, int], ...]:
	"""Devuelve las columnas del historial de frames ya traducidas."""
	return (
		(_("ID"), 70),
		(_("Hora"), 190),
		(_("Origen"), 210),
		(_("Confianza"), 130),
		(_("Aplicación"), 170),
		(_("Celdas"), 90),
		(_("Texto legible"), 330),
		(_("Unicode"), 300),
		(_("Hex"), 360),
	)


def _eventColumns() -> tuple[tuple[str, int], ...]:
	"""Devuelve las columnas del historial de eventos externos ya traducidas."""
	return (
		(_("ID"), 70),
		(_("Hora"), 190),
		(_("API"), 320),
		(_("Texto solicitado"), 330),
		(_("PID"), 100),
		(_("Aplicación"), 170),
		(_("Frame"), 90),
		(_("Confianza"), 130),
	)


def _frameChoiceLabel(frame: BrailleFrame) -> str:
	"""Resume un frame en una línea apta para un cuadro combinado."""
	text = historyReadableText(frame)
	if len(text) > 60:
		text = text[:57] + "…"
	return _("#{frameId} — {time} — {text}").format(
		frameId=frame.frameId,
		time=frame.timestampIso[11:23] if len(frame.timestampIso) > 23 else frame.timestampIso,
		text=text,
	)


def friendlyComparison(previousFrame: BrailleFrame, currentFrame: BrailleFrame) -> str:
	"""Genera una comparación explicada en lenguaje natural y conserva los valores exactos."""
	differences = compareCells(previousFrame.cellsRaw, currentFrame.cellsRaw)
	previousText, previousSource = readableTextForFrame(previousFrame)
	currentText, currentSource = readableTextForFrame(currentFrame)
	lines = [
		_("Comparación del frame #{old} con el frame #{new}").format(
			old=previousFrame.frameId,
			new=currentFrame.frameId,
		),
		"",
		ngettext(
			"Resumen: {count} celda es diferente.",
			"Resumen: {count} celdas son diferentes.",
			len(differences),
		).format(count=len(differences)),
		_("Texto legible del frame #{frameId} ({source}): {text}").format(
			frameId=previousFrame.frameId,
			source=previousSource,
			text=previousText,
		),
		_("Texto legible del frame #{frameId} ({source}): {text}").format(
			frameId=currentFrame.frameId,
			source=currentSource,
			text=currentText,
		),
		"",
		_("Detalle de las celdas:"),
	]
	if not differences:
		lines.append(_("No cambió ninguna celda."))
		return "\n".join(lines)
	for difference in differences:
		if difference.changeType == "ADDED":
			lines.append(
				_("Celda {position}: se añadió {new}.").format(
					position=difference.position,
					new=describeCell(difference.newValue),
				),
			)
		elif difference.changeType == "REMOVED":
			lines.append(
				_("Celda {position}: se eliminó {old}.").format(
					position=difference.position,
					old=describeCell(difference.oldValue),
				),
			)
		else:
			lines.append(
				_("Celda {position}: cambió de {old} a {new}.").format(
					position=difference.position,
					old=describeCell(difference.oldValue),
					new=describeCell(difference.newValue),
				),
			)
	return "\n".join(lines)


class ViewerFrame(wx.Frame):
	"""Ventana principal que muestra sin alterar el foco las capturas ya almacenadas."""

	def __init__(
		self,
		runtimeState: RuntimeState,
		onClosed: Callable[[], None],
		openSimpleView: Callable[[], None] | None = None,
	):
		"""Crea todos los controles, registra observadores y carga el historial existente."""
		super().__init__(
			nvdaGui.mainFrame,
			title=_("Virtual Braille Display"),
			style=wx.DEFAULT_FRAME_STYLE,
		)
		self._runtime = runtimeState
		self._onClosedCallback = onClosed
		self._openSimpleView = openSimpleView
		self._updateLock = threading.Lock()
		self._updateScheduled = False
		self._paused = False
		self._frozen = not addonConfig.getBoolean("followLatestFrame")
		self._closed = False
		self._displayedFrameId: int | None = None
		self._frameIds: list[int] = []
		self._eventIds: list[int] = []
		self._comparisonFrameIds: list[int] = []
		self._knownProcesses: tuple[tuple[int, str], ...] = ()
		self._restoringSelection = False
		self._createControls()
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.Bind(wx.EVT_ACTIVATE, self._onActivate)
		self._runtime.frameStore.registerFrameListener(self._queueFrameUpdate)
		self._runtime.frameStore.registerEventListener(self._queueEventUpdate)
		self._runtime.registerStatusListener(self._queueStatusUpdate)
		self._runtime.registerFilterListener(self._queueFilterUpdate)
		self._synchronizeAll()
		self._showInitialFrame()
		self.SetSize((1080, 800))
		self.SetMinSize((820, 600))
		self.CentreOnScreen()

	# --- Construcción de la interfaz -------------------------------------------------

	def _createControls(self) -> None:
		"""Construye la cabecera, el cuaderno y la botonera accesible."""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		self.statusSummary = addReadOnlyText(helper, panel, _("Resumen de &estado:"), lines=2)
		self.notebook = wx.Notebook(panel, name=_("Secciones del visor"))
		helper.addItem(self.notebook, flag=wx.EXPAND, proportion=1)
		self._createCurrentFramePage()
		self._createTechnicalPage()
		self._createFrameHistoryPage()
		self._createEventHistoryPage()
		self._createComparisonPage()
		self._createSimulationPage()
		self._createInteractionPage()
		self._createButtons(panel, helper)
		panel.SetSizer(sizer)

	def _createButtons(self, panel: wx.Panel, helper: guiHelper.BoxSizerHelper) -> None:
		"""Crea la botonera principal en un contenedor que se ajusta al ancho disponible."""
		buttonSizer = wx.WrapSizer(wx.HORIZONTAL)
		definitions = (
			("connectButton", _("&Conectar"), self._onConnect),
			("disconnectButton", _("&Desconectar"), self._onDisconnect),
			("pauseButton", _("&Pausar actualizaciones"), self._onPause),
			("freezeButton", _("&Fijar frame mostrado"), self._onFreeze),
			("refreshButton", _("&Actualizar ahora"), self._onRefresh),
			("filterButton", _("Filtrar por aplicación en&focada"), self._onFilterFocused),
			("clearFilterButton", _("&Quitar filtro"), self._onClearFilter),
			("simpleViewButton", _("&Vista sencilla"), self._onSimpleView),
			("copyButton", _("Co&piar"), self._onCopy),
			("saveButton", _("&Guardar…"), self._onSave),
			("clearButton", _("&Limpiar"), self._onClear),
			("configurationButton", _("Con&figuración…"), self._onConfiguration),
			("closeButton", _("Ce&rrar"), self._onCloseButton),
		)
		for attribute, label, handler in definitions:
			button = wx.Button(panel, label=label)
			button.Bind(wx.EVT_BUTTON, handler)
			buttonSizer.Add(button, flag=wx.ALL, border=3)
			setattr(self, attribute, button)
		helper.addItem(buttonSizer, flag=wx.EXPAND)
		self.pauseButton.SetHelpText(
			_("Detiene o reanuda las actualizaciones automáticas de los controles; la captura continúa."),
		)
		self.freezeButton.SetHelpText(
			_("Fija el frame mostrado o vuelve a seguir el frame más reciente."),
		)
		self.filterButton.SetHelpText(
			_("Limita el visor a los frames de la aplicación que tenía el foco antes de abrirlo."),
		)
		if self._frozen:
			setButtonLabel(self.freezeButton, _("&Volver al frame más reciente"))
		self.simpleViewButton.Enable(self._openSimpleView is not None)

	def _createCurrentFramePage(self) -> None:
		"""Crea la vista detallada del frame actual."""
		page = wx.ScrolledWindow(self.notebook)
		page.SetScrollRate(10, 10)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		self.frameSummaryValue = addReadOnlyText(helper, page, _("Resumen del &frame:"), lines=3)
		self.originValue = addReadOnlyText(helper, page, _("&Origen del frame:"), lines=1)
		self.confidenceValue = addReadOnlyText(helper, page, _("&Confianza del origen:"), lines=1)
		self.bufferValue = addReadOnlyText(helper, page, _("Parte de NVDA que lo &generó:"), lines=1)
		self.contextApplicationValue = addReadOnlyText(
			helper,
			page,
			_("Aplicación cuyo contenido se re&presentaba:"),
			lines=1,
		)
		self.applicationValue = addReadOnlyText(helper, page, _("Aplicación &solicitante:"), lines=1)
		self.pidValue = addReadOnlyText(helper, page, _("&PID solicitante:"), lines=1)
		self.associatedTextValue = addReadOnlyText(
			helper,
			page,
			_("Texto &legible para el desarrollador:"),
			proportion=1,
			lines=3,
		)
		self.readableTextSourceValue = addReadOnlyText(
			helper,
			page,
			_("Procedencia y fia&bilidad del texto legible:"),
			lines=2,
		)
		self.requestedTextValue = addReadOnlyText(helper, page, _("Texto solicita&do:"), lines=2)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Resumen amigable"))

	def _createTechnicalPage(self) -> None:
		"""Crea una pestaña separada para los patrones exactos destinados a depuración avanzada."""
		page = wx.ScrolledWindow(self.notebook)
		page.SetScrollRate(10, 10)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		addLabel(
			helper,
			page,
			_(
				"Estos campos son la representación exacta recibida por la línea.\n"
				"No necesita entenderlos para usar el resumen amigable.",
			),
		)
		self.unicodeValue = addReadOnlyText(helper, page, _("&Unicode Braille:"), lines=2, wrap=False)
		self.hexValue = addReadOnlyText(helper, page, _("&Hexadecimal:"), lines=2, wrap=False)
		self.decimalValue = addReadOnlyText(helper, page, _("&Decimal:"), lines=2, wrap=False)
		self.binaryValue = addReadOnlyText(helper, page, _("&Binario:"), lines=2, wrap=False)
		self.dotsValue = addReadOnlyText(
			helper, page, _("&Puntos braille:"), proportion=1, lines=4, wrap=False
		)
		self.rowsValue = addReadOnlyText(
			helper,
			page,
			_("Reparto por &filas de la línea:"),
			lines=3,
			wrap=False,
		)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Datos técnicos exactos"))

	def _createFrameHistoryPage(self) -> None:
		"""Crea la tabla accesible del historial de frames con su filtro de texto."""
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		self.frameFilterText = helper.addLabeledControl(
			_("Filtrar por &texto:"),
			wx.TextCtrl,
			style=wx.TE_PROCESS_ENTER,
		)
		self.frameFilterText.Bind(wx.EVT_TEXT_ENTER, self._onApplyTextFilter)
		filterButton = helper.addItem(wx.Button(page, label=_("Aplicar &filtro de texto")))
		filterButton.Bind(wx.EVT_BUTTON, self._onApplyTextFilter)
		self.applicationChoice = helper.addLabeledControl(
			_("Mostrar sólo la a&plicación:"),
			wx.Choice,
			choices=[_("Todas las aplicaciones")],
		)
		self.applicationChoice.SetSelection(0)
		self.applicationChoice.Bind(wx.EVT_CHOICE, self._onApplicationChoice)
		addLabel(
			helper,
			page,
			_("Frames capturados. Seleccione una fila para fijarla y examinar sus detalles."),
		)
		self.frameHistory = AccessibleListCtrl(
			page,
			_frameColumns(),
			name=_("Lista de frames capturados"),
			helpText=_(
				"Cada fila contiene identificador, hora, origen, confianza, aplicación, celdas y "
				"texto. Recorra las columnas con las flechas izquierda y derecha o con Ctrl más un "
				"número del 1 al 9.",
			),
		)
		self.frameHistory.Bind(wx.EVT_LIST_ITEM_SELECTED, self._onFrameSelected)
		addExpandingControl(helper, self.frameHistory)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Historial de frames"))

	def _createEventHistoryPage(self) -> None:
		"""Crea la tabla separada de solicitudes externas de alto nivel."""
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		addLabel(
			helper,
			page,
			_("Solicitudes de braille recibidas desde aplicaciones mediante Controller Client."),
		)
		self.eventHistory = AccessibleListCtrl(
			page,
			_eventColumns(),
			name=_("Lista de solicitudes braille de aplicaciones externas"),
			helpText=_(
				"Cada fila muestra API, texto solicitado, PID, aplicación y frame correlacionado.",
			),
		)
		addExpandingControl(helper, self.eventHistory)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Eventos externos"))

	def _createComparisonPage(self) -> None:
		"""Crea la vista de diferencias entre dos frames elegidos libremente."""
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		self.comparisonFirstChoice = helper.addLabeledControl(
			_("Frame &A:"),
			wx.Choice,
			choices=[],
		)
		self.comparisonSecondChoice = helper.addLabeledControl(
			_("Frame &B:"),
			wx.Choice,
			choices=[],
		)
		buttonHelper = guiHelper.ButtonHelper(wx.HORIZONTAL)
		compareButton = buttonHelper.addButton(page, label=_("&Comparar A con B"))
		lastTwoButton = buttonHelper.addButton(page, label=_("Comparar los dos ú&ltimos"))
		lastThreeButton = buttonHelper.addButton(page, label=_("Comparar antepe&núltimo con último"))
		markShownButton = buttonHelper.addButton(page, label=_("Usar el frame &mostrado como B"))
		helper.addItem(buttonHelper)
		compareButton.Bind(wx.EVT_BUTTON, self._onCompare)
		lastTwoButton.Bind(wx.EVT_BUTTON, self._onCompareLastTwo)
		lastThreeButton.Bind(wx.EVT_BUTTON, self._onCompareLastThree)
		markShownButton.Bind(wx.EVT_BUTTON, self._onUseShownFrame)
		self.comparisonValue = addReadOnlyText(
			helper,
			page,
			_("Explicación amigable de los cam&bios:"),
			proportion=1,
			lines=10,
		)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Comparación"))

	def _createSimulationPage(self) -> None:
		"""Crea la vista que reparte el mismo buffer en líneas de otros tamaños."""
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		addLabel(
			helper,
			page,
			_(
				"El mismo contenido, repartido tal y como lo mostraría una línea de otro tamaño.\n"
				"No se vuelve a traducir nada: sólo se agrupan de otro modo las celdas capturadas.",
			),
		)
		self.simulationSizeChoice = helper.addLabeledControl(
			_("Tamaño de la línea &simulada:"),
			wx.Choice,
			choices=[str(size) for size in SIMULATION_SIZES],
		)
		self.simulationSizeChoice.SetSelection(SIMULATION_SIZES.index(20))
		self.simulationSizeChoice.Bind(wx.EVT_CHOICE, lambda event: self._updateSimulation())
		self.simulationValue = addReadOnlyText(
			helper,
			page,
			_("Ven&tanas resultantes:"),
			proportion=1,
			lines=10,
			wrap=False,
		)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Simulación de tamaño"))

	def _createInteractionPage(self) -> None:
		"""Crea los controles que simulan las acciones de una línea braille física."""
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(page, sizer=sizer)
		addLabel(
			helper,
			page,
			_(
				"Estas acciones se entregan a NVDA como gestos reales de línea braille, igual que\n"
				"si procedieran de un dispositivo físico. Requieren la línea virtual conectada.",
			),
		)
		self.routingCell = helper.addLabeledControl(
			_("Celda de en&caminamiento:"),
			wx.SpinCtrl,
			min=1,
			max=256,
			initial=1,
		)
		routingHelper = guiHelper.ButtonHelper(wx.HORIZONTAL)
		routeButton = routingHelper.addButton(page, label=_("Simular tecla de en&caminamiento"))
		scrollBackButton = routingHelper.addButton(page, label=_("Desplazar &atrás"))
		scrollForwardButton = routingHelper.addButton(page, label=_("Desplazar a&delante"))
		helper.addItem(routingHelper)
		routeButton.Bind(wx.EVT_BUTTON, self._onRouteToCell)
		scrollBackButton.Bind(wx.EVT_BUTTON, lambda event: self._runtime.scrollBack())
		scrollForwardButton.Bind(wx.EVT_BUTTON, lambda event: self._runtime.scrollForward())
		addLabel(helper, page, _("Acorde del teclado braille simulado:"))
		dotsSizer = wx.WrapSizer(wx.HORIZONTAL)
		self.dotCheckBoxes: list[wx.CheckBox] = []
		for dot in range(1, 9):
			checkBox = wx.CheckBox(page, label=_("Punto {dot}").format(dot=dot))
			dotsSizer.Add(checkBox, flag=wx.ALL, border=3)
			self.dotCheckBoxes.append(checkBox)
		self.spaceCheckBox = wx.CheckBox(page, label=_("Espacio"))
		dotsSizer.Add(self.spaceCheckBox, flag=wx.ALL, border=3)
		helper.addItem(dotsSizer, flag=wx.EXPAND)
		sendDotsButton = helper.addItem(wx.Button(page, label=_("&Enviar acorde a NVDA")))
		sendDotsButton.Bind(wx.EVT_BUTTON, self._onSendDots)
		self.interactionResult = addReadOnlyText(helper, page, _("Resultado de la ú&ltima acción:"), lines=2)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, _("Interacción con la línea"))

	# --- Sincronización --------------------------------------------------------------

	def _queueFrameUpdate(self, frame: BrailleFrame) -> None:
		"""Agrupa notificaciones de frames y sólo encola una actualización wx pendiente."""
		self._scheduleUpdate()

	def _queueEventUpdate(self, event: ExternalBrailleEvent) -> None:
		"""Agrupa notificaciones de eventos, incluidas sus correlaciones posteriores."""
		self._scheduleUpdate()

	def _queueStatusUpdate(self, connected: bool) -> None:
		"""Traslada los cambios de conexión al hilo de interfaz."""
		self._scheduleUpdate()

	def _queueFilterUpdate(self, applicationFilter: object) -> None:
		"""Recarga las vistas cuando cambia el filtro por aplicación."""
		wx.CallAfter(self._synchronizeAll)

	def _scheduleUpdate(self) -> None:
		"""Programa una actualización asíncrona sin acumular llamadas a ``wx.CallAfter``."""
		with self._updateLock:
			if self._closed or self._updateScheduled:
				return
			self._updateScheduled = True
		wx.CallAfter(self._flushScheduledUpdate)

	def _flushScheduledUpdate(self) -> None:
		"""Sincroniza controles sólo fuera del modo de pausa o inspección con foco."""
		with self._updateLock:
			self._updateScheduled = False
		if self._closed or self._paused or self.IsActive():
			return
		self._synchronizeAll()

	def _synchronizeAll(self) -> None:
		"""Actualiza estado, historiales y, si procede, el frame visible."""
		if self._closed:
			return
		processId = self._runtime.applicationFilter.processId
		frames = self._runtime.frameStore.getFrames(processId)
		events = self._runtime.frameStore.getEvents()
		self._synchronizeApplicationChoice(processId)
		self._rebuildFrameList(frames)
		self._synchronizeEventList(events)
		self._synchronizeComparisonChoices(frames)
		if not self._frozen and frames:
			self._renderFrame(frames[-1])
		self._updateStatus()

	def _showInitialFrame(self) -> None:
		"""Muestra el último frame al abrir, aunque el visor arranque sin seguimiento.

		Sin esto, con «Seguir automáticamente» desactivado el visor se abriría con todas las
		pestañas vacías hasta que el usuario seleccionase una fila.
		"""
		if self._displayedFrameId is not None:
			return
		frame = self._runtime.frameStore.getLastFrame(self._runtime.applicationFilter.processId)
		if frame is not None:
			self._renderFrame(frame)

	def _synchronizeApplicationChoice(self, processId: int | None) -> None:
		"""Ofrece en un desplegable los procesos ya observados en el historial completo."""
		processes = self._runtime.frameStore.getKnownProcesses()
		if processes == self._knownProcesses:
			self._selectApplicationChoice(processId)
			return
		self._knownProcesses = processes
		labels = [_("Todas las aplicaciones")]
		labels.extend(
			_("{name} (PID {pid})").format(name=name or _("aplicación sin nombre"), pid=pid)
			for pid, name in processes
		)
		self.applicationChoice.Set(labels)
		self._selectApplicationChoice(processId)

	def _selectApplicationChoice(self, processId: int | None) -> None:
		"""Sitúa el desplegable en el proceso filtrado sin disparar ningún evento."""
		identifiers = [pid for pid, _name in self._knownProcesses]
		if processId is not None and processId in identifiers:
			self.applicationChoice.SetSelection(identifiers.index(processId) + 1)
			return
		self.applicationChoice.SetSelection(0)

	def _onApplicationChoice(self, event: wx.CommandEvent) -> None:
		"""Aplica el filtro correspondiente al proceso elegido en el desplegable."""
		selection = self.applicationChoice.GetSelection()
		if selection <= 0:
			self._runtime.clearApplicationFilter()
			return
		processId, processName = self._knownProcesses[selection - 1]
		self._runtime.setApplicationFilter(processId, processName or None)

	def _updateStatus(self) -> None:
		"""Actualiza un resumen enfocable de conexión, tamaño, filtro y modo del visor."""
		connected = self._runtime.driverConnected
		if self._paused:
			viewMode = _("actualizaciones automáticas pausadas; la captura continúa")
		elif self._frozen:
			viewMode = _("frame fijado; los historiales continúan")
		elif self.IsActive():
			viewMode = _("modo de inspección; use Actualizar ahora para cargar una instantánea")
		else:
			viewMode = _("siguiendo automáticamente el frame más reciente")
		applicationFilter = self._runtime.applicationFilter
		if applicationFilter.isActive:
			filterText = _("Filtro: sólo {name} con PID {pid}.").format(
				name=applicationFilter.processName or _("aplicación sin nombre"),
				pid=applicationFilter.processId,
			)
		else:
			filterText = _("Filtro: todas las aplicaciones.")
		statistics = self._runtime.frameStore.getStatistics(applicationFilter.processId)
		self.statusSummary.ChangeValue(
			_(
				"Línea {connection}. {cells} celdas por fila y {rows} filas. Visor: {mode}.\n"
				"{filter} {frames} frames y {events} eventos conservados.",
			).format(
				connection=_("conectada") if connected else _("desconectada"),
				cells=addonConfig.getCellCount(),
				rows=addonConfig.getRowCount(),
				mode=viewMode,
				filter=filterText,
				frames=statistics["frames"],
				events=statistics["events"],
			),
		)
		self.connectButton.Enable(not connected)
		self.disconnectButton.Enable(connected)
		self.clearFilterButton.Enable(applicationFilter.isActive)

	def _visibleFrames(self, frames: tuple[BrailleFrame, ...]) -> tuple[BrailleFrame, ...]:
		"""Aplica el filtro de texto escrito por el usuario sobre los frames ya filtrados."""
		needle = self.frameFilterText.GetValue().strip().lower()
		if not needle:
			return frames
		return tuple(
			frame
			for frame in frames
			if needle in historyReadableText(frame).lower()
			or needle in frame.cellsHex.lower()
			or needle in (frame.context.processName or "").lower()
		)

	def _rebuildFrameList(self, frames: tuple[BrailleFrame, ...]) -> None:
		"""Reconstruye la lista conservando la selección por identificador de frame."""
		visible = self._visibleFrames(frames)
		selectedId = self._selectedFrameId()
		self.frameHistory.Freeze()
		try:
			self.frameHistory.clearRows()
			self._frameIds = []
			for frame in visible:
				self.frameHistory.appendRow(
					(
						str(frame.frameId),
						frame.timestampIso,
						originLabel(frame.originType),
						confidenceLabel(frame.originConfidence),
						describeApplication(frame),
						_("{used} de {total}").format(used=frame.usedCells, total=frame.numCells),
						historyReadableText(frame),
						frame.cellsUnicode,
						frame.cellsHex,
					),
				)
				self._frameIds.append(frame.frameId)
		finally:
			self.frameHistory.Thaw()
		if selectedId is not None and selectedId in self._frameIds:
			index = self._frameIds.index(selectedId)
			# Restaurar la selección dispara el evento de selección de wx; se marca para que
			# no se interprete como una elección nueva del usuario y vuelva a fijar el frame.
			self._restoringSelection = True
			try:
				self.frameHistory.Select(index)
				self.frameHistory.Focus(index)
			finally:
				self._restoringSelection = False

	def _selectedFrameId(self) -> int | None:
		"""Devuelve el identificador del frame seleccionado en el historial, si lo hay."""
		index = self.frameHistory.GetFirstSelected()
		if not 0 <= index < len(self._frameIds):
			return None
		return self._frameIds[index]

	def _synchronizeEventList(self, events: tuple[ExternalBrailleEvent, ...]) -> None:
		"""Sincroniza eventos y refresca filas cuya correlación haya cambiado."""
		currentSet = {event.eventId for event in events}
		while self._eventIds and self._eventIds[0] not in currentSet:
			self.eventHistory.removeFirstRow()
			self._eventIds.pop(0)
		eventById = {event.eventId: event for event in events}
		for row, eventId in enumerate(self._eventIds):
			self.eventHistory.setRow(row, self._eventRowValues(eventById[eventId]))
		knownIds = set(self._eventIds)
		for event in events:
			if event.eventId in knownIds:
				continue
			self.eventHistory.appendRow(self._eventRowValues(event))
			self._eventIds.append(event.eventId)

	@staticmethod
	def _eventRowValues(event: ExternalBrailleEvent) -> tuple[str, ...]:
		"""Devuelve el contenido de todas las columnas de una fila de evento."""
		return (
			str(event.eventId),
			event.timestampIso,
			event.sourceApi,
			event.text,
			str(event.processId) if event.processId is not None else _("No disponible"),
			event.processName or _("No disponible"),
			str(event.correlatedFrameId) if event.correlatedFrameId is not None else "—",
			confidenceLabel(event.correlationConfidence),
		)

	def _synchronizeComparisonChoices(self, frames: tuple[BrailleFrame, ...]) -> None:
		"""Rellena los desplegables de comparación con los últimos frames disponibles."""
		recent = frames[-COMPARISON_CHOICE_LIMIT:]
		newIds = [frame.frameId for frame in recent]
		if newIds == self._comparisonFrameIds:
			return
		firstSelection = self._choiceFrameId(self.comparisonFirstChoice)
		secondSelection = self._choiceFrameId(self.comparisonSecondChoice)
		labels = [_frameChoiceLabel(frame) for frame in recent]
		self._comparisonFrameIds = newIds
		for choice, previousId, defaultOffset in (
			(self.comparisonFirstChoice, firstSelection, 2),
			(self.comparisonSecondChoice, secondSelection, 1),
		):
			choice.Set(labels)
			if previousId in newIds:
				choice.SetSelection(newIds.index(previousId))
			elif len(newIds) >= defaultOffset:
				choice.SetSelection(len(newIds) - defaultOffset)
			elif newIds:
				choice.SetSelection(0)

	def _choiceFrameId(self, choice: wx.Choice) -> int | None:
		"""Traduce la selección de un desplegable al identificador de frame que representa."""
		selection = choice.GetSelection()
		if not 0 <= selection < len(self._comparisonFrameIds):
			return None
		return self._comparisonFrameIds[selection]

	def _renderFrame(self, frame: BrailleFrame) -> None:
		"""Muestra un frame sin cambiar el foco ni la selección del usuario."""
		self._displayedFrameId = frame.frameId
		readableText, readableTextSource = readableTextForFrame(frame)
		self.frameSummaryValue.ChangeValue(
			_("Frame #{frameId}. Capturado a las {timestamp}. {occupancy}").format(
				frameId=frame.frameId,
				timestamp=frame.timestampIso,
				occupancy=describeOccupancy(frame),
			),
		)
		self.originValue.ChangeValue(originLabel(frame.originType))
		self.confidenceValue.ChangeValue(confidenceLabel(frame.originConfidence))
		self.bufferValue.ChangeValue(bufferLabel(frame.context.bufferKind))
		self.contextApplicationValue.ChangeValue(describeApplication(frame))
		self.applicationValue.ChangeValue(
			frame.applicationName or _("No disponible mediante la API actual"),
		)
		self.pidValue.ChangeValue(
			str(frame.processId)
			if frame.processId is not None
			else _("No disponible mediante la API actual"),
		)
		self.associatedTextValue.ChangeValue(readableText)
		self.readableTextSourceValue.ChangeValue(readableTextSource)
		self.requestedTextValue.ChangeValue(
			frame.requestedText or _("No hubo solicitud externa correlacionada."),
		)
		self.unicodeValue.ChangeValue(frame.cellsUnicode)
		self.hexValue.ChangeValue(frame.cellsHex)
		self.decimalValue.ChangeValue(frame.cellsDecimal)
		self.binaryValue.ChangeValue(frame.cellsBinary)
		self.dotsValue.ChangeValue(frame.activeDots)
		self.rowsValue.ChangeValue(self._describeRows(frame))
		self.routingCell.SetRange(1, max(1, frame.numCells))
		self._updateSimulation()

	@staticmethod
	def _describeRows(frame: BrailleFrame) -> str:
		"""Reparte el buffer entre las filas declaradas por la línea virtual."""
		rowCount = addonConfig.getRowCount()
		if rowCount <= 1:
			return _("Línea de una sola fila.")
		columns = max(1, frame.numCells // rowCount)
		rows = splitIntoWindows(frame.cellsRaw, columns)
		return "\n".join(
			_("Fila {index}: {pattern}").format(
				index=index,
				pattern="".join(chr(0x2800 + value) for value in row),
			)
			for index, row in enumerate(rows, start=1)
		)

	def _updateSimulation(self) -> None:
		"""Recalcula el reparto del frame mostrado en una línea de otro tamaño."""
		frame = self._getDisplayedFrame()
		if frame is None:
			self.simulationValue.ChangeValue(_("No hay un frame mostrado."))
			return
		selection = self.simulationSizeChoice.GetSelection()
		size = SIMULATION_SIZES[selection] if 0 <= selection < len(SIMULATION_SIZES) else 20
		used = frame.cellsRaw.rstrip(b"\x00")
		if not used:
			self.simulationValue.ChangeValue(_("El frame está vacío: no hay nada que repartir."))
			return
		windows = splitIntoWindows(used, size)
		lines = [
			ngettext(
				"Con {size} celdas harían falta {count} ventana.",
				"Con {size} celdas harían falta {count} ventanas.",
				len(windows),
			).format(size=size, count=len(windows)),
			"",
		]
		for index, window in enumerate(windows, start=1):
			pattern = "".join(chr(0x2800 + value) for value in window)
			hexText = " ".join(f"{value:02X}" for value in window)
			lines.append(
				_("Ventana {index}: {pattern}   [{hex}]").format(index=index, pattern=pattern, hex=hexText),
			)
		self.simulationValue.ChangeValue("\n".join(lines))

	# --- Manejadores de eventos ------------------------------------------------------

	def _onFrameSelected(self, event: wx.ListEvent) -> None:
		"""Congela y muestra el frame elegido en el historial."""
		if self._restoringSelection:
			return
		index = event.GetIndex()
		if not 0 <= index < len(self._frameIds):
			return
		frame = self._runtime.frameStore.getFrame(self._frameIds[index])
		if frame is None:
			return
		self._frozen = True
		setButtonLabel(self.freezeButton, _("&Volver al frame más reciente"))
		self._renderFrame(frame)
		self._updateStatus()

	def _onApplyTextFilter(self, event: wx.CommandEvent) -> None:
		"""Vuelve a construir la lista de frames aplicando el filtro de texto."""
		self._synchronizeAll()

	def _onConnect(self, event: wx.CommandEvent) -> None:
		"""Selecciona el driver virtual desde el botón Conectar."""
		if self._runtime.connectDriver():
			reportAction(_("Línea braille virtual conectada."))
		else:
			showMessage(
				self,
				_("NVDA no pudo conectar Virtual Braille Display."),
				_("Error de conexión"),
				DialogType.ERROR,
			)
		self._synchronizeAll()

	def _onDisconnect(self, event: wx.CommandEvent) -> None:
		"""Selecciona el driver «sin braille» y conserva el historial."""
		if self._runtime.disconnectDriver():
			reportAction(_("Línea braille virtual desconectada; se conservan los historiales."))
		else:
			showMessage(
				self,
				_("NVDA no pudo desconectar la línea virtual."),
				_("Error de desconexión"),
				DialogType.ERROR,
			)
		self._synchronizeAll()

	def _onPause(self, event: wx.CommandEvent) -> None:
		"""Pausa o reanuda únicamente las actualizaciones del visor."""
		self._paused = not self._paused
		setButtonLabel(
			self.pauseButton,
			_("&Reanudar actualizaciones") if self._paused else _("&Pausar actualizaciones"),
		)
		if not self._paused:
			self._synchronizeAll()
		else:
			self._updateStatus()

	def _onFreeze(self, event: wx.CommandEvent) -> None:
		"""Mantiene un frame visible sin detener la captura ni los historiales."""
		self._frozen = not self._frozen
		setButtonLabel(
			self.freezeButton,
			_("&Volver al frame más reciente") if self._frozen else _("&Fijar frame mostrado"),
		)
		if not self._frozen:
			frame = self._runtime.frameStore.getLastFrame(self._runtime.applicationFilter.processId)
			if frame is not None:
				self._renderFrame(frame)
		self._updateStatus()

	def _onRefresh(self, event: wx.CommandEvent) -> None:
		"""Carga manualmente la instantánea más reciente durante la inspección."""
		self._synchronizeAll()

	def _onFilterFocused(self, event: wx.CommandEvent) -> None:
		"""Fija el filtro con la aplicación que tenía el foco antes de abrir el visor."""
		processId, processName = self._runtime.getFocusedApplication()
		if processId is None:
			showMessage(
				self,
				_(
					"NVDA no pudo determinar la aplicación enfocada. Recuerde que, con el visor "
					"abierto, la aplicación enfocada es el propio visor: use el gesto de teclado "
					"desde su aplicación para capturar su PID.",
				),
				_("Sin aplicación enfocada"),
				DialogType.WARNING,
			)
			return
		self._runtime.setApplicationFilter(processId, processName)

	def _onClearFilter(self, event: wx.CommandEvent) -> None:
		"""Vuelve a mostrar los frames de todas las aplicaciones."""
		self._runtime.clearApplicationFilter()

	def _onSimpleView(self, event: wx.CommandEvent) -> None:
		"""Abre la vista explicada en lenguaje humano."""
		if self._openSimpleView is not None:
			self._openSimpleView()

	def _onActivate(self, event: wx.ActivateEvent) -> None:
		"""Evita bucles al inspeccionar el visor y reanuda el seguimiento al salir de él."""
		event.Skip()
		if self._closed:
			return
		wx.CallAfter(self._updateStatus)
		if not event.GetActive() and not self._paused:
			self._scheduleUpdate()

	def _onCopy(self, event: wx.CommandEvent) -> None:
		"""Copia un informe completo del frame mostrado al portapapeles."""
		frame = self._getDisplayedFrame()
		if frame is None:
			return
		api.copyToClip(self._formatFrameReport(frame), notify=False)
		announce(_("Informe del frame copiado al portapapeles."))

	def _onSave(self, event: wx.CommandEvent) -> None:
		"""Solicita confirmación de privacidad y exporta una instantánea manual."""
		confirmed = confirm(
			self,
			_(
				"Los historiales pueden contener contraseñas, documentos, notificaciones y otros datos "
				"privados. No se guarda nada automáticamente. ¿Desea exportarlos ahora?",
			),
			_("Advertencia de privacidad"),
			DialogType.WARNING,
		)
		if not confirmed:
			return
		wildcard = _("Texto (*.txt)|*.txt|JSON (*.json)|*.json|JSON Lines (*.jsonl)|*.jsonl")
		with wx.FileDialog(
			self,
			message=_("Guardar historial"),
			wildcard=wildcard,
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return
			path = Path(dialog.GetPath())
			formats = ("txt", "json", "jsonl")
			formatName = path.suffix.lower().lstrip(".")
			if formatName not in formats:
				formatName = formats[dialog.GetFilterIndex()]
				path = path.with_suffix(f".{formatName}")
		try:
			saveRecords(
				path,
				formatName,
				self._runtime.frameStore.getFrames(self._runtime.applicationFilter.processId),
				self._runtime.frameStore.getEvents(),
			)
		except Exception as error:
			showMessage(self, str(error), _("Error al guardar"), DialogType.ERROR)

	def _onClear(self, event: wx.CommandEvent) -> None:
		"""Limpia los dos historiales después de una confirmación explícita."""
		confirmed = confirm(
			self,
			_("¿Desea limpiar los historiales de frames y eventos externos?"),
			_("Limpiar historiales"),
			DialogType.WARNING,
		)
		if not confirmed:
			return
		self._runtime.frameStore.clear()
		self.frameHistory.clearRows()
		self.eventHistory.clearRows()
		self._frameIds.clear()
		self._eventIds.clear()
		self._comparisonFrameIds.clear()
		self.comparisonFirstChoice.Set([])
		self.comparisonSecondChoice.Set([])
		self._displayedFrameId = None
		for control in (
			self.frameSummaryValue,
			self.originValue,
			self.confidenceValue,
			self.bufferValue,
			self.contextApplicationValue,
			self.applicationValue,
			self.pidValue,
			self.associatedTextValue,
			self.readableTextSourceValue,
			self.requestedTextValue,
			self.unicodeValue,
			self.hexValue,
			self.decimalValue,
			self.binaryValue,
			self.dotsValue,
			self.rowsValue,
			self.comparisonValue,
			self.simulationValue,
		):
			control.ChangeValue("")
		self._updateStatus()

	def _onConfiguration(self, event: wx.CommandEvent) -> None:
		"""Abre la configuración con pestañas y aplica los cambios validados."""
		showSettingsDialog(self, self._runtime)
		self._synchronizeAll()

	def _onCompare(self, event: wx.CommandEvent) -> None:
		"""Compara los dos frames elegidos en los desplegables."""
		self._compareFrameIds(
			self._choiceFrameId(self.comparisonFirstChoice),
			self._choiceFrameId(self.comparisonSecondChoice),
		)

	def _onCompareLastTwo(self, event: wx.CommandEvent) -> None:
		"""Compara el penúltimo frame con el último."""
		self._compareByOffsets(2, 1)

	def _onCompareLastThree(self, event: wx.CommandEvent) -> None:
		"""Compara el antepenúltimo frame con el último."""
		self._compareByOffsets(3, 1)

	def _onUseShownFrame(self, event: wx.CommandEvent) -> None:
		"""Coloca el frame mostrado como término B de la comparación."""
		if self._displayedFrameId is None or self._displayedFrameId not in self._comparisonFrameIds:
			self.comparisonValue.ChangeValue(_("El frame mostrado no está en la lista de comparación."))
			return
		self.comparisonSecondChoice.SetSelection(self._comparisonFrameIds.index(self._displayedFrameId))
		announce(_("Frame mostrado seleccionado como B."))

	def _compareByOffsets(self, firstOffset: int, secondOffset: int) -> None:
		"""Compara dos frames indicados por su distancia desde el final del historial."""
		frames = self._runtime.frameStore.getFrames(self._runtime.applicationFilter.processId)
		if len(frames) < firstOffset:
			self.comparisonValue.ChangeValue(
				_("No hay suficientes frames conservados para esa comparación."),
			)
			return
		self._showComparison(frames[-firstOffset], frames[-secondOffset])

	def _compareFrameIds(self, firstId: int | None, secondId: int | None) -> None:
		"""Compara dos frames identificados por su número, avisando si ya expiraron."""
		if firstId is None or secondId is None:
			self.comparisonValue.ChangeValue(_("Elija los dos frames que desea comparar."))
			return
		firstFrame = self._runtime.frameStore.getFrame(firstId)
		secondFrame = self._runtime.frameStore.getFrame(secondId)
		if firstFrame is None or secondFrame is None:
			self.comparisonValue.ChangeValue(_("Alguno de los frames ya no está en el historial."))
			return
		self._showComparison(firstFrame, secondFrame)

	def _showComparison(self, firstFrame: BrailleFrame, secondFrame: BrailleFrame) -> None:
		"""Escribe el resultado de una comparación en la pestaña correspondiente."""
		self.comparisonValue.ChangeValue(friendlyComparison(firstFrame, secondFrame))

	def _onRouteToCell(self, event: wx.CommandEvent) -> None:
		"""Simula la pulsación de una tecla de encaminamiento sobre la celda elegida."""
		cellIndex = self.routingCell.GetValue() - 1
		if self._runtime.routeToCell(cellIndex):
			self.interactionResult.ChangeValue(
				_("Se envió el encaminamiento a la celda {cell}.").format(cell=cellIndex + 1),
			)
			return
		self.interactionResult.ChangeValue(
			_("NVDA no aceptó el encaminamiento. Compruebe que la línea virtual está conectada."),
		)

	def _onSendDots(self, event: wx.CommandEvent) -> None:
		"""Envía a NVDA el acorde braille marcado en las casillas."""
		dots = 0
		for index, checkBox in enumerate(self.dotCheckBoxes):
			if checkBox.GetValue():
				dots |= 1 << index
		space = self.spaceCheckBox.GetValue()
		if not dots and not space:
			self.interactionResult.ChangeValue(_("Marque al menos un punto o la barra espaciadora."))
			return
		if self._runtime.sendBrailleDots(dots, space):
			self.interactionResult.ChangeValue(
				_("Se envió el acorde con valor de puntos {dots}.").format(dots=dots),
			)
			return
		self.interactionResult.ChangeValue(
			_("NVDA no aceptó el acorde. Compruebe que la línea virtual está conectada."),
		)

	def _getDisplayedFrame(self) -> BrailleFrame | None:
		"""Recupera el frame mostrado si todavía está conservado."""
		if self._displayedFrameId is None:
			return None
		return self._runtime.frameStore.getFrame(self._displayedFrameId)

	@staticmethod
	def _formatFrameReport(frame: BrailleFrame) -> str:
		"""Genera el texto copiable de un frame."""
		readableText, readableTextSource = readableTextForFrame(frame)
		return "\n".join(
			(
				f"Frame: #{frame.frameId}",
				f"Timestamp: {frame.timestampIso}",
				f"Celdas: {frame.usedCells} de {frame.numCells}",
				f"Origen: {originLabel(frame.originType)}",
				f"Confianza: {confidenceLabel(frame.originConfidence)}",
				f"Búfer de NVDA: {bufferLabel(frame.context.bufferKind)}",
				f"Aplicación representada: {describeApplication(frame)}",
				f"Aplicación solicitante: {frame.applicationName or 'No disponible mediante la API actual'}",
				f"PID solicitante: {frame.processId if frame.processId is not None else 'No disponible'}",
				f"Texto legible: {readableText}",
				f"Procedencia del texto: {readableTextSource}",
				f"Texto solicitado: {frame.requestedText or ''}",
				f"Unicode Braille: {frame.cellsUnicode}",
				f"Hexadecimal: {frame.cellsHex}",
				f"Decimal: {frame.cellsDecimal}",
				f"Binario: {frame.cellsBinary}",
				f"Puntos: {frame.activeDots}",
			),
		)

	def _onCloseButton(self, event: wx.CommandEvent) -> None:
		"""Cierra la ventana desde el botón accesible."""
		self.Close()

	def _onClose(self, event: wx.CloseEvent) -> None:
		"""Retira observadores antes de destruir la ventana."""
		if self._closed:
			event.Skip()
			return
		self._closed = True
		self._runtime.frameStore.unregisterFrameListener(self._queueFrameUpdate)
		self._runtime.frameStore.unregisterEventListener(self._queueEventUpdate)
		self._runtime.unregisterStatusListener(self._queueStatusUpdate)
		self._runtime.unregisterFilterListener(self._queueFilterUpdate)
		self._onClosedCallback()
		self.Destroy()
