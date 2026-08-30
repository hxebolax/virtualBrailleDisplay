"""Vista explicada en lenguaje humano para quien no conoce braille ni lectores de pantalla.

Esta ventana no sustituye al visor técnico: lo traduce. Responde en español llano a tres
preguntas: qué está recibiendo ahora mismo una persona con línea braille, de dónde sale esa
información y qué conviene revisar en la aplicación que se está desarrollando.
"""

from __future__ import annotations

from collections.abc import Callable

import addonHandler
import api
import gui as nvdaGui
import wx
from gui import guiHelper

addonHandler.initTranslation()

from .accessibleList import AccessibleListCtrl  # noqa: E402
from .diagnostics import analyzeFrame, buildPlainReport  # noqa: E402
from .frameText import readableTextForFrame  # noqa: E402
from .guiUtils import addExpandingControl, addLabel, addReadOnlyText  # noqa: E402
from .models import BrailleFrame  # noqa: E402
from .runtime import RuntimeState  # noqa: E402


def _observationColumns() -> tuple[tuple[str, int], ...]:
	"""Devuelve las columnas de la revisión automática ya traducidas."""
	return (
		(_("Tipo"), 120),
		(_("Asunto"), 330),
		(_("Explicación"), 620),
	)


class SimpleViewFrame(wx.Frame):
	"""Ventana sencilla que explica el último frame y lo que conviene revisar."""

	def __init__(
		self,
		runtimeState: RuntimeState,
		onClosed: Callable[[], None],
		openTechnicalViewer: Callable[[], None] | None = None,
	):
		"""Crea la ventana, se suscribe a los frames y muestra el estado actual."""
		super().__init__(
			nvdaGui.mainFrame,
			title=_("Virtual Braille Display: explicación sencilla"),
			style=wx.DEFAULT_FRAME_STYLE,
		)
		self._runtime = runtimeState
		self._onClosedCallback = onClosed
		self._openTechnicalViewer = openTechnicalViewer
		self._closed = False
		self._updateScheduled = False
		self._createControls()
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self._runtime.frameStore.registerFrameListener(self._queueUpdate)
		self._runtime.registerFilterListener(self._queueFilterUpdate)
		self.refresh()
		self.SetSize((960, 640))
		self.SetMinSize((720, 520))
		self.CentreOnScreen()

	def _createControls(self) -> None:
		"""Construye el informe, la lista de observaciones y la botonera."""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = guiHelper.BoxSizerHelper(panel, sizer=sizer)
		self.reportValue = addReadOnlyText(
			helper,
			panel,
			_("Qué está pasando &ahora mismo:"),
			proportion=1,
			lines=10,
		)
		addLabel(helper, panel, _("&Revisión automática:"))
		self.observationList = AccessibleListCtrl(
			panel,
			_observationColumns(),
			name=_("Revisión automática de la salida braille"),
			helpText=_(
				"Cada fila describe algo que conviene comprobar. Recorra las columnas con las "
				"flechas izquierda y derecha o con Ctrl más un número.",
			),
		)
		addExpandingControl(helper, self.observationList)
		buttonHelper = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.refreshButton = buttonHelper.addButton(panel, label=_("&Actualizar"))
		self.copyButton = buttonHelper.addButton(panel, label=_("&Copiar informe"))
		self.technicalButton = buttonHelper.addButton(panel, label=_("Ver &detalles técnicos"))
		self.closeButton = buttonHelper.addButton(panel, label=_("Ce&rrar"))
		helper.addItem(buttonHelper)
		panel.SetSizer(sizer)
		self.refreshButton.Bind(wx.EVT_BUTTON, lambda event: self.refresh())
		self.copyButton.Bind(wx.EVT_BUTTON, self._onCopy)
		self.technicalButton.Bind(wx.EVT_BUTTON, self._onTechnical)
		self.closeButton.Bind(wx.EVT_BUTTON, lambda event: self.Close())
		self.technicalButton.Enable(self._openTechnicalViewer is not None)

	def refresh(self) -> None:
		"""Carga el frame más reciente que cumpla el filtro activo."""
		frame = self._runtime.frameStore.getLastFrame(self._runtime.applicationFilter.processId)
		if frame is None:
			self.reportValue.ChangeValue(
				_(
					"Todavía no ha llegado ningún frame.\n\n"
					"Compruebe que Virtual Braille Display está seleccionado en las opciones de braille "
					"de NVDA y utilice la aplicación que quiere revisar.",
				),
			)
			self.observationList.clearRows()
			return
		self._renderFrame(frame)

	def _renderFrame(self, frame: BrailleFrame) -> None:
		"""Escribe el informe y la lista de observaciones del frame indicado."""
		readableText, readableSource = readableTextForFrame(frame)
		self.reportValue.ChangeValue(buildPlainReport(frame, readableText, readableSource))
		self.observationList.clearRows()
		for observation in analyzeFrame(frame, readableText):
			self.observationList.appendRow(
				(observation.severityLabel, observation.title, observation.detail),
			)

	def _queueUpdate(self, frame: BrailleFrame) -> None:
		"""Agrupa las notificaciones de frames en una única actualización de interfaz."""
		if self._closed or self._updateScheduled:
			return
		self._updateScheduled = True
		wx.CallAfter(self._flushUpdate)

	def _queueFilterUpdate(self, applicationFilter: object) -> None:
		"""Recarga la vista cuando cambia el filtro por aplicación."""
		self._queueUpdate(None)  # type: ignore[arg-type]

	def _flushUpdate(self) -> None:
		"""Refresca la vista salvo mientras el usuario la está inspeccionando."""
		self._updateScheduled = False
		if self._closed or self.IsActive():
			return
		self.refresh()

	def _onCopy(self, event: wx.CommandEvent) -> None:
		"""Copia el informe completo al portapapeles."""
		api.copyToClip(self.reportValue.GetValue(), notify=False)

	def _onTechnical(self, event: wx.CommandEvent) -> None:
		"""Abre el visor técnico completo sin cerrar esta ventana."""
		if self._openTechnicalViewer is not None:
			self._openTechnicalViewer()

	def _onClose(self, event: wx.CloseEvent) -> None:
		"""Retira los observadores antes de destruir la ventana."""
		if self._closed:
			event.Skip()
			return
		self._closed = True
		self._runtime.frameStore.unregisterFrameListener(self._queueUpdate)
		self._runtime.unregisterFilterListener(self._queueFilterUpdate)
		self._onClosedCallback()
		self.Destroy()
