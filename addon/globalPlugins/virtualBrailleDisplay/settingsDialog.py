"""Diálogo de configuración con pestañas, construido con los ayudantes accesibles de NVDA.

Todos los controles se crean con ``guiHelper``, que sitúa la etiqueta estática antes del
control. Ése es el orden que necesitan los lectores de pantalla para anunciar el nombre
del campo además de su valor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import addonHandler
import wx
from gui import guiHelper
from gui.message import DialogType, MessageDialog

addonHandler.initTranslation()

from . import config as addonConfig  # noqa: E402
from .logWriter import CONTINUOUS_FORMATS  # noqa: E402
from .messages import ANNOUNCEMENT_MODES  # noqa: E402

if TYPE_CHECKING:
	from .runtime import RuntimeState

CELL_COUNT_CHOICES = (14, 20, 32, 40, 64, 80)


def showError(parent: wx.Window, message: str, title: str) -> None:
	"""Muestra un error con la API vigente de mensajes de NVDA."""
	dialog = MessageDialog(parent, message, title, dialogType=DialogType.ERROR)
	try:
		dialog.ShowModal()
	finally:
		dialog.Destroy()


class SettingsDialog(wx.Dialog):
	"""Reúne en pestañas todas las opciones persistentes del complemento."""

	def __init__(self, parent: wx.Window):
		"""Construye las pestañas con los valores guardados actualmente."""
		super().__init__(
			parent,
			title=_("Configuración de Virtual Braille Display"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
			name=_("Configuración de Virtual Braille Display"),
		)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		contentHelper = guiHelper.BoxSizerHelper(self, sizer=mainSizer)
		self.notebook = wx.Notebook(self, name=_("Secciones de configuración"))
		contentHelper.addItem(self.notebook, flag=wx.EXPAND, proportion=1)
		self._createDisplayPage()
		self._createCapturePage()
		self._createCorrelationPage()
		self._createListsPage()
		self._createUpdatesPage()
		self._createLoggingPage()
		contentHelper.addDialogDismissButtons(wx.OK | wx.CANCEL, separated=True)
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self.SetMinSize(self.GetSize())
		self.CentreOnScreen()
		self.Bind(wx.EVT_SHOW, self._onShow)
		self._initialFocusSet = False

	def _createDisplayPage(self) -> None:
		"""Crea la pestaña con la geometría de la línea braille virtual."""
		panel = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		currentCount = addonConfig.getCellCount()
		choices = [str(value) for value in CELL_COUNT_CHOICES] + [_("Personalizado")]
		self.cellCountChoice = helper.addLabeledControl(
			_("&Celdas por fila:"),
			wx.Choice,
			choices=choices,
		)
		self.cellCountChoice.SetSelection(
			CELL_COUNT_CHOICES.index(currentCount)
			if currentCount in CELL_COUNT_CHOICES
			else len(choices) - 1,
		)
		self.customCellCount = helper.addLabeledControl(
			_("Celdas &personalizadas, de 1 a 256:"),
			wx.SpinCtrl,
			min=1,
			max=256,
			initial=currentCount,
		)
		self.rowCount = helper.addLabeledControl(
			_("&Filas de la línea, de 1 a 40:"),
			wx.SpinCtrl,
			min=1,
			max=40,
			initial=addonConfig.getRowCount(),
		)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"Con más de una fila se simula una línea multilínea. Al cambiar la geometría,\n"
					"NVDA reinicializa el driver y vuelve a calcular realmente la salida braille.",
				),
			),
		)
		panel.SetSizerAndFit(sizer)
		self.notebook.AddPage(panel, _("Línea braille"))
		self.cellCountChoice.Bind(wx.EVT_CHOICE, self._onCellCountChoice)
		self._updateCustomCellState()

	def _createCapturePage(self) -> None:
		"""Crea la pestaña con el historial y el comportamiento del visor."""
		panel = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		self.historyLimit = helper.addLabeledControl(
			_("Frames y eventos &conservados:"),
			wx.SpinCtrl,
			min=10,
			max=10000,
			initial=addonConfig.getHistoryLimit(),
		)
		self.ignoreEmptyFrames = helper.addItem(
			wx.CheckBox(panel, label=_("No guardar los frames &vacíos, sin ningún punto activo")),
		)
		self.ignoreEmptyFrames.SetValue(addonConfig.getBoolean("ignoreEmptyFrames"))
		self.ignoreRepeatedFrames = helper.addItem(
			wx.CheckBox(panel, label=_("No guardar frames &repetidos idénticos al anterior")),
		)
		self.ignoreRepeatedFrames.SetValue(addonConfig.getBoolean("ignoreRepeatedFrames"))
		self.followLatestFrame = helper.addItem(
			wx.CheckBox(panel, label=_("&Seguir automáticamente el frame más reciente al abrir el visor")),
		)
		self.followLatestFrame.SetValue(addonConfig.getBoolean("followLatestFrame"))
		self.openSimpleViewFirst = helper.addItem(
			wx.CheckBox(panel, label=_("Abrir primero la vista &explicada en lenguaje humano")),
		)
		self.openSimpleViewFirst.SetValue(addonConfig.getBoolean("openSimpleViewFirst"))
		self.filterFocusedApplication = helper.addItem(
			wx.CheckBox(
				panel,
				label=_("Al abrir el visor con un gesto, filtrar por la &aplicación que tenga el foco"),
			),
		)
		self.filterFocusedApplication.SetValue(addonConfig.getBoolean("filterFocusedApplication"))
		panel.SetSizerAndFit(sizer)
		self.notebook.AddPage(panel, _("Captura e historial"))

	def _createCorrelationPage(self) -> None:
		"""Crea la pestaña con las ventanas usadas para correlacionar eventos externos."""
		panel = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		self.correlationWindow = helper.addLabeledControl(
			_("Ventana de &correlación, en milisegundos:"),
			wx.SpinCtrl,
			min=50,
			max=10000,
			initial=addonConfig.getCorrelationWindowMilliseconds(),
		)
		self.temporalFallback = helper.addLabeledControl(
			_("Ventana sólo &temporal, en milisegundos:"),
			wx.SpinCtrl,
			min=0,
			max=2000,
			initial=addonConfig.getTemporalFallbackMilliseconds(),
		)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"La primera ventana limita cuánto tiempo puede pasar entre la solicitud de una\n"
					"aplicación y el frame que se le atribuye. La segunda sólo se usa cuando no hay\n"
					"coincidencia de texto y únicamente si hay un candidato. La correlación nunca se\n"
					"presenta como confirmada.",
				),
			),
		)
		panel.SetSizerAndFit(sizer)
		self.notebook.AddPage(panel, _("Correlación de orígenes"))

	def _createListsPage(self) -> None:
		"""Crea la pestaña que decide qué se anuncia al recorrer las columnas de las listas."""
		panel = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"En las listas del visor puede recorrer las columnas de la fila enfocada con las\n"
					"flechas izquierda y derecha, o saltar a una columna con Ctrl más un número del 1\n"
					"al 9. Elija qué desea escuchar de cada celda:",
				),
			),
		)
		self.listAnnounceRowNumber = self._addCheckBox(
			helper,
			panel,
			_("Decir el número de &fila"),
			"listAnnounceRowNumber",
		)
		self.listAnnounceTotalRows = self._addCheckBox(
			helper,
			panel,
			_("Decir también el &total de filas"),
			"listAnnounceTotalRows",
		)
		self.listAnnounceColumnHeader = self._addCheckBox(
			helper,
			panel,
			_("Decir el nombre de la &columna"),
			"listAnnounceColumnHeader",
		)
		self.listAnnounceCellValue = self._addCheckBox(
			helper,
			panel,
			_("Decir el &contenido de la celda"),
			"listAnnounceCellValue",
		)
		self.listAnnounceEmptyCells = self._addCheckBox(
			helper,
			panel,
			_("Avisar cuando la celda está &vacía"),
			"listAnnounceEmptyCells",
		)
		self.listWrapColumns = self._addCheckBox(
			helper,
			panel,
			_("Dar la vuelta al llegar a la &última columna"),
			"listWrapColumns",
		)
		self.listSpeakOnly = self._addCheckBox(
			helper,
			panel,
			_("Anunciar sólo por vo&z, sin ocupar la línea braille"),
			"listSpeakOnly",
		)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"Si desactiva todas las opciones se seguirá diciendo el contenido de la celda.\n"
					"Con Ctrl+Mayús+C se copia la celda enfocada al portapapeles.",
				),
			),
		)
		self.actionAnnouncementMode = helper.addLabeledControl(
			_("Avisos con el &resultado de una acción:"),
			wx.Choice,
			choices=[
				_("Leerlos por voz y braille"),
				_("Mostrarlos en un cuadro de mensaje"),
				_("Las dos cosas"),
			],
		)
		currentMode = addonConfig.getText("actionAnnouncementMode") or ANNOUNCEMENT_MODES[0]
		self.actionAnnouncementMode.SetSelection(
			ANNOUNCEMENT_MODES.index(currentMode) if currentMode in ANNOUNCEMENT_MODES else 0,
		)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"Los avisos lanzados desde el menú se retrasan hasta que NVDA termina de anunciar\n"
					"la ventana que recupera el foco, para que no se pierdan. Si aun así prefiere no\n"
					"depender de la voz, elija el cuadro de mensaje.",
				),
			),
		)
		panel.SetSizerAndFit(sizer)
		self.notebook.AddPage(panel, _("Listas y avisos"))

	def _createUpdatesPage(self) -> None:
		"""Crea la pestaña que controla la descarga de traducciones y documentación."""
		panel = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"Las traducciones y la documentación se publican en una release aparte del\n"
					"repositorio, de modo que llegan sin tener que instalar una versión nueva del\n"
					"complemento. Sólo se descargan esos recursos: nunca código.",
				),
			),
		)
		self.resourceUpdatesEnabled = helper.addItem(
			wx.CheckBox(panel, label=_("&Comprobar automáticamente al iniciar NVDA")),
		)
		self.resourceUpdatesEnabled.SetValue(addonConfig.getBoolean("resourceUpdatesEnabled"))
		self.resourceUpdateIntervalHours = helper.addLabeledControl(
			_("&Horas entre comprobaciones:"),
			wx.SpinCtrl,
			min=1,
			max=168,
			initial=addonConfig.getInteger("resourceUpdateIntervalHours"),
		)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"Los cambios se aplican al reiniciar NVDA. Puede comprobarlo cuando quiera desde\n"
					"Herramientas, Virtual Braille Display, Buscar traducciones y documentación nuevas.",
				),
			),
		)
		panel.SetSizerAndFit(sizer)
		self.notebook.AddPage(panel, _("Actualizaciones"))

	def _createLoggingPage(self) -> None:
		"""Crea la pestaña del registro continuo, siempre desactivado de fábrica."""
		panel = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		helper.addItem(
			wx.StaticText(
				panel,
				label=_(
					"Aviso de privacidad: el braille que recibe la línea puede contener contraseñas,\n"
					"documentos, mensajes y notificaciones. El registro continuo escribe todo eso en\n"
					"un archivo sin cifrar. Actívelo sólo mientras depure y desactívelo después.",
				),
			),
		)
		self.continuousLogging = helper.addItem(
			wx.CheckBox(panel, label=_("&Registrar continuamente frames y eventos en un archivo")),
		)
		self.continuousLogging.SetValue(addonConfig.getBoolean("continuousLogging"))
		self.continuousLogFormat = helper.addLabeledControl(
			_("&Formato del registro:"),
			wx.Choice,
			choices=[_("JSON Lines (recomendado)"), _("Texto")],
		)
		currentFormat = addonConfig.getText("continuousLogFormat") or "jsonl"
		self.continuousLogFormat.SetSelection(
			CONTINUOUS_FORMATS.index(currentFormat) if currentFormat in CONTINUOUS_FORMATS else 0,
		)
		self.continuousLogPath = helper.addLabeledControl(
			_("&Archivo de destino:"),
			wx.TextCtrl,
			value=addonConfig.getText("continuousLogPath"),
		)
		browseButton = helper.addItem(wx.Button(panel, label=_("&Examinar…")))
		browseButton.Bind(wx.EVT_BUTTON, self._onBrowseLogPath)
		panel.SetSizerAndFit(sizer)
		self.notebook.AddPage(panel, _("Registro y privacidad"))

	@staticmethod
	def _addCheckBox(
		helper: guiHelper.BoxSizerHelper,
		panel: wx.Panel,
		label: str,
		key: str,
	) -> wx.CheckBox:
		"""Añade una casilla ya sincronizada con su opción persistida."""
		checkBox = helper.addItem(wx.CheckBox(panel, label=label))
		checkBox.SetValue(addonConfig.getBoolean(key))
		return checkBox

	def _onBrowseLogPath(self, event: wx.CommandEvent) -> None:
		"""Permite elegir el archivo de registro con el explorador estándar."""
		wildcard = _("JSON Lines (*.jsonl)|*.jsonl|Texto (*.txt)|*.txt")
		with wx.FileDialog(
			self,
			message=_("Archivo de registro continuo"),
			wildcard=wildcard,
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		) as dialog:
			if dialog.ShowModal() == wx.ID_OK:
				self.continuousLogPath.SetValue(dialog.GetPath())

	def _onCellCountChoice(self, event: wx.CommandEvent) -> None:
		"""Activa el campo personalizado sólo cuando corresponde."""
		self._updateCustomCellState()
		event.Skip()

	def _updateCustomCellState(self) -> None:
		"""Sincroniza la disponibilidad del control de tamaño personalizado."""
		self.customCellCount.Enable(self.cellCountChoice.GetSelection() == len(CELL_COUNT_CHOICES))

	def _onShow(self, event: wx.ShowEvent) -> None:
		"""Sitúa el foco inicial en el cuaderno para poder recorrer las pestañas."""
		event.Skip()
		if not event.IsShown() or self._initialFocusSet:
			return
		self._initialFocusSet = True
		wx.CallAfter(self.notebook.SetFocus)

	def getCellCount(self) -> int:
		"""Devuelve el tamaño elegido, incluido el valor personalizado."""
		selection = self.cellCountChoice.GetSelection()
		if 0 <= selection < len(CELL_COUNT_CHOICES):
			return CELL_COUNT_CHOICES[selection]
		return self.customCellCount.GetValue()

	def applySettings(self, runtimeState: RuntimeState) -> bool:
		"""Guarda todas las opciones y devuelve si la operación se completó por entero."""
		try:
			# La ruta se valida antes de guardar nada para no dejar el registro continuo
			# activado apuntando a una carpeta inexistente.
			logPath = self._validatedLogPath()
			runtimeState.applyHistoryLimit(self.historyLimit.GetValue())
			addonConfig.setCorrelationWindowMilliseconds(self.correlationWindow.GetValue())
			addonConfig.setTemporalFallbackMilliseconds(self.temporalFallback.GetValue())
			for control, key in self._booleanControls():
				addonConfig.setBoolean(key, control.GetValue())
			addonConfig.setInteger(
				"resourceUpdateIntervalHours",
				self.resourceUpdateIntervalHours.GetValue(),
			)
			addonConfig.setText(
				"actionAnnouncementMode",
				ANNOUNCEMENT_MODES[max(0, self.actionAnnouncementMode.GetSelection())],
			)
			addonConfig.setText(
				"continuousLogFormat",
				CONTINUOUS_FORMATS[max(0, self.continuousLogFormat.GetSelection())],
			)
			addonConfig.setText("continuousLogPath", logPath)
			runtimeState.applyContinuousLoggingSettings()
			if not runtimeState.applyDisplayGeometry(self.getCellCount(), self.rowCount.GetValue()):
				raise RuntimeError(_("NVDA no pudo reinicializar el driver con la nueva geometría."))
		except Exception as error:
			showError(self, str(error), _("Error de configuración"))
			return False
		return True

	def _booleanControls(self) -> tuple[tuple[wx.CheckBox, str], ...]:
		"""Empareja cada casilla con la clave de configuración que representa."""
		return (
			(self.ignoreEmptyFrames, "ignoreEmptyFrames"),
			(self.ignoreRepeatedFrames, "ignoreRepeatedFrames"),
			(self.followLatestFrame, "followLatestFrame"),
			(self.openSimpleViewFirst, "openSimpleViewFirst"),
			(self.filterFocusedApplication, "filterFocusedApplication"),
			(self.listAnnounceRowNumber, "listAnnounceRowNumber"),
			(self.listAnnounceTotalRows, "listAnnounceTotalRows"),
			(self.listAnnounceColumnHeader, "listAnnounceColumnHeader"),
			(self.listAnnounceCellValue, "listAnnounceCellValue"),
			(self.listAnnounceEmptyCells, "listAnnounceEmptyCells"),
			(self.listWrapColumns, "listWrapColumns"),
			(self.listSpeakOnly, "listSpeakOnly"),
			(self.continuousLogging, "continuousLogging"),
			(self.resourceUpdatesEnabled, "resourceUpdatesEnabled"),
		)

	def _validatedLogPath(self) -> str:
		"""Comprueba que la carpeta del registro existe antes de guardarla."""
		path = self.continuousLogPath.GetValue().strip()
		if not path:
			return ""
		parent = Path(path).parent
		if not parent.exists():
			raise ValueError(
				_("La carpeta del archivo de registro no existe: {folder}").format(folder=parent)
			)
		return path


def showSettingsDialog(parent: wx.Window, runtimeState: RuntimeState) -> bool:
	"""Muestra el diálogo y aplica los cambios si el usuario acepta."""
	with SettingsDialog(parent) as dialog:
		if dialog.ShowModal() != wx.ID_OK:
			return False
		return dialog.applySettings(runtimeState)
