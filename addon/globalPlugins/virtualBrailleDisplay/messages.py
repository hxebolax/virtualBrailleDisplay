"""Presentación de avisos del complemento sin que se pierdan al cambiar el foco.

Un aviso emitido desde el menú de NVDA se pierde si se emite con ``ui.message``: al cerrarse
el menú, NVDA anuncia la ventana que recupera el foco y esa locución cancela la anterior.

NVDA ofrece ``ui.delayedMessage`` precisamente para ese caso: encola el aviso en la cola del
núcleo, de modo que se emite después de los eventos pendientes, y lo hace con prioridad
inmediata para que no quede descartado. Este módulo centraliza esa decisión y permite además
mostrar los avisos en un cuadro de mensaje para quien no quiera depender de la voz.
"""

from __future__ import annotations

import addonHandler
import gui as nvdaGui
import ui
import wx
from gui.message import DialogType, MessageDialog
from logHandler import log

addonHandler.initTranslation()

from . import config as addonConfig  # noqa: E402

SPEECH_MODE = "speech"
DIALOG_MODE = "dialog"
BOTH_MODE = "both"
ANNOUNCEMENT_MODES = (SPEECH_MODE, DIALOG_MODE, BOTH_MODE)


def reportAction(text: str, fromMenu: bool = False) -> None:
	"""Comunica el resultado de una acción respetando el modo de aviso configurado.

	:param text: Texto que debe recibir el usuario.
	:param fromMenu: Cierto cuando la acción se lanzó desde un menú de NVDA, en cuyo caso el
		aviso se retrasa para que no lo cancele el anuncio del foco que se restaura.
	"""
	if not text:
		return
	mode = addonConfig.getText("actionAnnouncementMode") or SPEECH_MODE
	if mode in (SPEECH_MODE, BOTH_MODE):
		_speak(text, fromMenu)
	if mode in (DIALOG_MODE, BOTH_MODE):
		_showDialog(text)


def _speak(text: str, fromMenu: bool) -> None:
	"""Emite el aviso por voz y braille eligiendo la función adecuada de NVDA."""
	if not fromMenu:
		ui.message(text)
		return
	delayedMessage = getattr(ui, "delayedMessage", None)
	if delayedMessage is None:
		# Compatibilidad defensiva: si una versión de NVDA no ofreciera la función,
		# se retrasa el aviso manualmente para no perderlo al cerrarse el menú.
		wx.CallLater(250, ui.message, text)
		return
	delayedMessage(text)


def _showDialog(text: str) -> None:
	"""Muestra el aviso en un cuadro de mensaje no modal, que nunca se puede perder.

	Se usa ``Show`` y no ``ShowModal`` porque el aviso puede provenir de un menú que todavía
	se está cerrando; un diálogo modal bloquearía el núcleo de NVDA.
	"""

	def present() -> None:
		try:
			dialog = MessageDialog(
				nvdaGui.mainFrame,
				text,
				_("Virtual Braille Display"),
				dialogType=DialogType.STANDARD,
			)
			dialog.Show()
		except Exception:
			log.error("No se pudo mostrar el aviso en un cuadro de mensaje", exc_info=True)

	wx.CallAfter(present)
