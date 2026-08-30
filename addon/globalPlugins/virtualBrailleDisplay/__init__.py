"""Punto de entrada del global plugin Virtual Braille Display."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import addonHandler
import globalPluginHandler
from scriptHandler import script

addonHandler.initTranslation()

if TYPE_CHECKING:
	import wx

	from .gui import ViewerFrame
	from .runtime import RuntimeState
	from .simpleView import SimpleViewFrame

SCRIPT_CATEGORY = _("Virtual Braille Display")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Integra el visor, la configuración y los hooks con el ciclo de vida de NVDA."""

	scriptCategory = SCRIPT_CATEGORY

	def __init__(self):
		"""Inicializa los servicios y añade el submenú al menú Herramientas."""
		super().__init__()
		import gui

		from .resourceUpdates import ResourceUpdateService
		from .runtime import runtime

		self._gui = gui
		self._runtime: RuntimeState = runtime
		self._viewer: ViewerFrame | None = None
		self._simpleView: SimpleViewFrame | None = None
		self._menuItems: list[wx.MenuItem] = []
		self._subMenu: wx.Menu | None = None
		self._subMenuItem: wx.MenuItem | None = None
		self._runtime.initialize()
		self._resourceUpdates = ResourceUpdateService()
		self._resourceUpdates.start()
		self._createToolsSubMenu()

	def _createToolsSubMenu(self) -> None:
		"""Agrupa todas las acciones del complemento en un único submenú de Herramientas."""
		import wx

		self._subMenu = wx.Menu()
		self._appendMenuItem(
			_("&Visor de frames y eventos…"),
			_("Abre el visor técnico con los historiales de la línea braille virtual."),
			self._onOpenViewer,
		)
		self._appendMenuItem(
			_("Explicación &sencilla…"),
			_("Explica en lenguaje llano qué está recibiendo ahora mismo la línea braille."),
			self._onOpenSimpleView,
		)
		self._subMenu.AppendSeparator()
		self._appendMenuItem(
			_("&Conectar la línea virtual"),
			_("Selecciona Virtual Braille Display como pantalla braille de NVDA."),
			self._onConnect,
		)
		self._appendMenuItem(
			_("&Desconectar la línea virtual"),
			_("Selecciona «sin braille» conservando los historiales capturados."),
			self._onDisconnect,
		)
		self._subMenu.AppendSeparator()
		self._appendMenuItem(
			_("&Filtrar por la aplicación que tenía el foco"),
			_("Limita el visor a los frames de la aplicación desde la que abrió este menú."),
			self._onFilterFocusedApplication,
		)
		self._appendMenuItem(
			_("&Quitar el filtro de aplicación"),
			_("Vuelve a mostrar los frames de todas las aplicaciones."),
			self._onClearApplicationFilter,
		)
		self._appendMenuItem(
			_("Anunciar el último &frame"),
			_("Dice el texto y la ocupación del último frame recibido."),
			self._onReportLastFrame,
		)
		self._subMenu.AppendSeparator()
		self._appendMenuItem(
			_("&Buscar traducciones y documentación nuevas"),
			_("Descarga las traducciones y la documentación publicadas desde la última versión."),
			self._onCheckResourceUpdates,
		)
		self._subMenu.AppendSeparator()
		self._appendMenuItem(
			_("Con&figuración…"),
			_("Abre la configuración con pestañas del complemento."),
			self._onConfiguration,
		)
		self._appendMenuItem(
			_("&Ayuda del complemento"),
			_("Abre la documentación instalada con el complemento."),
			self._onHelp,
		)
		self._subMenuItem = self._gui.mainFrame.sysTrayIcon.toolsMenu.AppendSubMenu(
			self._subMenu,
			_("&Virtual Braille Display"),
			_("Línea braille virtual para inspeccionar y depurar la salida braille de NVDA."),
		)

	def _appendMenuItem(self, label: str, helpText: str, handler: Callable[[wx.CommandEvent], None]) -> None:
		"""Añade un elemento al submenú y conecta su manejador al icono de la bandeja."""
		import wx

		menuItem = self._subMenu.Append(wx.ID_ANY, label, helpText)
		self._gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, handler, menuItem)
		self._menuItems.append(menuItem)

	def terminate(self) -> None:
		"""Cierra las interfaces, restaura el hook nativo y elimina el submenú."""
		import wx

		try:
			for window in (self._viewer, self._simpleView):
				if window is not None:
					window.Close()
			self._viewer = None
			self._simpleView = None
			sysTrayIcon = self._gui.mainFrame.sysTrayIcon
			for menuItem in self._menuItems:
				sysTrayIcon.Unbind(wx.EVT_MENU, source=menuItem)
			self._menuItems.clear()
			if self._subMenuItem is not None:
				sysTrayIcon.toolsMenu.Remove(self._subMenuItem.Id)
				self._subMenuItem.Destroy()
				self._subMenuItem = None
			self._subMenu = None
			self._resourceUpdates.stop()
			self._runtime.terminate()
		finally:
			super().terminate()

	# --- Scripts asignables a gestos -------------------------------------------------

	@script(
		description=_("Abre el visor de Virtual Braille Display"),
		category=SCRIPT_CATEGORY,
	)
	def script_openViewer(self, gesture) -> None:
		"""Abre el visor aplicando el filtro por aplicación enfocada si está configurado."""
		from . import config as addonConfig

		if addonConfig.getBoolean("filterFocusedApplication"):
			self._captureFocusedApplication(announceResult=False)
		if addonConfig.getBoolean("openSimpleViewFirst"):
			self.openSimpleView()
			return
		self.openViewer()

	@script(
		description=_("Abre el visor filtrado por la aplicación que tiene el foco"),
		category=SCRIPT_CATEGORY,
	)
	def script_openViewerForFocusedApplication(self, gesture) -> None:
		"""Captura el PID de la aplicación enfocada y abre el visor limitado a ella.

		El PID se consulta antes de mostrar cualquier ventana del complemento, de modo que
		el foco sigue siendo el de la aplicación del usuario. Es contexto elegido por el
		usuario, no una deducción sobre el origen de los frames.
		"""
		self._captureFocusedApplication(announceResult=True)
		self.openViewer()

	@script(
		description=_("Activa o desactiva el filtro por la aplicación que tiene el foco"),
		category=SCRIPT_CATEGORY,
	)
	def script_toggleApplicationFilter(self, gesture) -> None:
		"""Alterna entre limitar la captura a la aplicación enfocada y verlas todas."""
		self.toggleApplicationFilter(fromMenu=False)

	@script(
		description=_("Abre la explicación sencilla de la salida braille"),
		category=SCRIPT_CATEGORY,
	)
	def script_openSimpleView(self, gesture) -> None:
		"""Abre la ventana que explica en lenguaje humano el último frame capturado."""
		self.openSimpleView()

	@script(
		description=_("Anuncia el último frame recibido por la línea virtual"),
		category=SCRIPT_CATEGORY,
	)
	def script_reportLastFrame(self, gesture) -> None:
		"""Anuncia el contenido del último frame sin necesidad de abrir ninguna ventana."""
		self.reportLastFrame()

	@script(
		description=_("Busca traducciones y documentación nuevas del complemento"),
		category=SCRIPT_CATEGORY,
	)
	def script_checkResourceUpdates(self, gesture) -> None:
		"""Comprueba si hay recursos nuevos sin esperar a la comprobación automática."""
		self._resourceUpdates.checkNow(fromMenu=False)

	# --- Acciones compartidas por gestos y menú ---------------------------------------

	def reportLastFrame(self, fromMenu: bool = False) -> None:
		"""Anuncia el texto y la ocupación del último frame que cumple el filtro activo."""
		from .diagnostics import describeOccupancy
		from .frameText import readableTextForFrame
		from .messages import reportAction

		frame = self._runtime.frameStore.getLastFrame(self._runtime.applicationFilter.processId)
		if frame is None:
			reportAction(_("Todavía no se ha capturado ningún frame braille."), fromMenu)
			return
		readableText, _source = readableTextForFrame(frame)
		reportAction(
			_("Frame {frameId}. {text}. {occupancy}").format(
				frameId=frame.frameId,
				text=readableText,
				occupancy=describeOccupancy(frame),
			),
			fromMenu,
		)

	def toggleApplicationFilter(self, fromMenu: bool) -> None:
		"""Alterna el filtro por aplicación informando siempre del estado resultante."""
		from .messages import reportAction

		if self._runtime.applicationFilter.isActive:
			self._runtime.clearApplicationFilter()
			reportAction(_("Filtro por aplicación desactivado."), fromMenu)
			return
		self._captureFocusedApplication(announceResult=True, fromMenu=fromMenu)

	def connectDisplay(self, fromMenu: bool) -> None:
		"""Selecciona la línea virtual y comunica el resultado real de la operación."""
		from .messages import reportAction

		if self._runtime.connectDriver():
			reportAction(_("Línea braille virtual conectada."), fromMenu)
			return
		reportAction(_("NVDA no pudo conectar la línea braille virtual."), fromMenu)

	def disconnectDisplay(self, fromMenu: bool) -> None:
		"""Selecciona «sin braille» y comunica el resultado real de la operación."""
		from .messages import reportAction

		if self._runtime.disconnectDriver():
			reportAction(
				_("Línea braille virtual desconectada; se conservan los historiales."),
				fromMenu,
			)
			return
		reportAction(_("NVDA no pudo desconectar la línea braille virtual."), fromMenu)

	def showSettings(self) -> None:
		"""Abre la configuración desde el menú respetando el protocolo de ventanas de NVDA."""
		from .settingsDialog import showSettingsDialog

		mainFrame = self._gui.mainFrame
		mainFrame.prePopup()
		try:
			showSettingsDialog(mainFrame, self._runtime)
		finally:
			mainFrame.postPopup()

	def showHelp(self, fromMenu: bool = False) -> None:
		"""Abre la documentación instalada junto al complemento."""
		import os

		from .messages import reportAction

		try:
			documentationPath = addonHandler.getCodeAddon().getDocFilePath()
		except Exception:
			documentationPath = None
		if not documentationPath:
			reportAction(_("No se encontró la documentación del complemento."), fromMenu)
			return
		os.startfile(documentationPath)

	# --- Gestión de ventanas ---------------------------------------------------------

	def openViewer(self) -> None:
		"""Crea el visor una vez o lleva la instancia existente al frente."""
		from .gui import ViewerFrame

		if self._viewer is not None:
			self._viewer.Raise()
			self._viewer.Show()
			return
		self._viewer = ViewerFrame(self._runtime, self._onViewerClosed, self.openSimpleView)
		self._viewer.Show()

	def openSimpleView(self) -> None:
		"""Crea la vista sencilla una vez o lleva la instancia existente al frente."""
		from .simpleView import SimpleViewFrame

		if self._simpleView is not None:
			self._simpleView.Raise()
			self._simpleView.Show()
			return
		self._simpleView = SimpleViewFrame(self._runtime, self._onSimpleViewClosed, self.openViewer)
		self._simpleView.Show()

	def _captureFocusedApplication(self, announceResult: bool, fromMenu: bool = False) -> None:
		"""Consulta la aplicación enfocada y la fija como filtro del visor."""
		from .messages import reportAction

		processId, processName = self._runtime.getFocusedApplication()
		if processId is None:
			if announceResult:
				reportAction(
					_("No se pudo determinar la aplicación que tiene el foco."),
					fromMenu,
				)
			return
		self._runtime.setApplicationFilter(processId, processName)
		if announceResult:
			reportAction(
				_("Filtrando por {name}, con PID {pid}.").format(
					name=processName or _("aplicación sin nombre"),
					pid=processId,
				),
				fromMenu,
			)

	# --- Manejadores del submenú ------------------------------------------------------

	def _onOpenViewer(self, event: wx.CommandEvent) -> None:
		"""Abre el visor técnico desde el submenú."""
		self.openViewer()

	def _onOpenSimpleView(self, event: wx.CommandEvent) -> None:
		"""Abre la explicación sencilla desde el submenú."""
		self.openSimpleView()

	def _onConnect(self, event: wx.CommandEvent) -> None:
		"""Selecciona la línea virtual y anuncia el resultado."""
		self.connectDisplay(fromMenu=True)

	def _onDisconnect(self, event: wx.CommandEvent) -> None:
		"""Selecciona «sin braille» y anuncia el resultado."""
		self.disconnectDisplay(fromMenu=True)

	def _onFilterFocusedApplication(self, event: wx.CommandEvent) -> None:
		"""Filtra por la aplicación desde la que se abrió el menú."""
		self._captureFocusedApplication(announceResult=True, fromMenu=True)

	def _onClearApplicationFilter(self, event: wx.CommandEvent) -> None:
		"""Retira el filtro por aplicación desde el submenú."""
		from .messages import reportAction

		self._runtime.clearApplicationFilter()
		reportAction(_("Filtro por aplicación desactivado."), fromMenu=True)

	def _onReportLastFrame(self, event: wx.CommandEvent) -> None:
		"""Anuncia el último frame desde el submenú."""
		self.reportLastFrame(fromMenu=True)

	def _onCheckResourceUpdates(self, event: wx.CommandEvent) -> None:
		"""Comprueba si hay traducciones o documentación nuevas desde el submenú."""
		self._resourceUpdates.checkNow(fromMenu=True)

	def _onConfiguration(self, event: wx.CommandEvent) -> None:
		"""Abre la configuración desde el submenú."""
		self.showSettings()

	def _onHelp(self, event: wx.CommandEvent) -> None:
		"""Abre la documentación desde el submenú."""
		self.showHelp(fromMenu=True)

	def _onViewerClosed(self) -> None:
		"""Olvida la instancia destruida para permitir abrir otra."""
		self._viewer = None

	def _onSimpleViewClosed(self) -> None:
		"""Olvida la instancia destruida de la vista sencilla."""
		self._simpleView = None
