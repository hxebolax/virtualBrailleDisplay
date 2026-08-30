"""Ayudantes de interfaz que garantizan el orden etiqueta-control que necesita NVDA.

Un lector de pantalla deduce el nombre de un campo a partir del texto estático anterior
en el orden de creación. Por eso todas las funciones de este módulo crean primero la
etiqueta y después el control, igual que hace ``gui.guiHelper`` de NVDA.
"""

from __future__ import annotations

import addonHandler
import wx
from gui import guiHelper
from gui.message import DefaultButton, DialogType, MessageDialog, ReturnCode

addonHandler.initTranslation()


def addLabel(helper: guiHelper.BoxSizerHelper, parent: wx.Window, label: str) -> wx.StaticText:
	"""Añade un texto estático que sirve de etiqueta al siguiente control creado."""
	return helper.addItem(wx.StaticText(parent, label=label))


def addReadOnlyText(
	helper: guiHelper.BoxSizerHelper,
	parent: wx.Window,
	label: str,
	proportion: int = 0,
	wrap: bool = True,
	lines: int = 3,
) -> wx.TextCtrl:
	"""Crea un campo multilínea de sólo lectura precedido de su etiqueta."""
	addLabel(helper, parent, label)
	style = wx.TE_READONLY | wx.TE_MULTILINE
	if not wrap:
		style |= wx.TE_DONTWRAP
	control = wx.TextCtrl(parent, style=style)
	control.SetMinSize((-1, max(1, lines) * 22))
	helper.addItem(control, flag=wx.EXPAND, proportion=proportion)
	return control


def addExpandingControl(
	helper: guiHelper.BoxSizerHelper,
	control: wx.Control,
	proportion: int = 1,
) -> wx.Control:
	"""Añade un control ya creado para que ocupe el espacio disponible.

	El control debe haberse construido después de llamar a :func:`addLabel` para que el
	orden de creación siga siendo etiqueta y luego control.
	"""
	helper.addItem(control, flag=wx.EXPAND, proportion=proportion)
	return control


def showMessage(
	parent: wx.Window,
	message: str,
	title: str,
	dialogType: DialogType = DialogType.STANDARD,
) -> ReturnCode:
	"""Muestra un diálogo modal con la API vigente de mensajes de NVDA."""
	dialog = MessageDialog(parent, message, title, dialogType=dialogType)
	try:
		return ReturnCode(dialog.ShowModal())
	finally:
		dialog.Destroy()


def confirm(
	parent: wx.Window,
	message: str,
	title: str,
	dialogType: DialogType = DialogType.WARNING,
) -> bool:
	"""Solicita confirmación dejando «No» como foco inicial y acción de escape."""
	buttons = (
		DefaultButton.YES,
		DefaultButton.NO.value._replace(defaultFocus=True, fallbackAction=True),
	)
	dialog = MessageDialog(parent, message, title, dialogType=dialogType, buttons=buttons)
	try:
		return dialog.ShowModal() == ReturnCode.YES
	finally:
		dialog.Destroy()


def setButtonLabel(button: wx.Button, label: str) -> None:
	"""Actualiza a la vez el texto visible y el nombre anunciado de un botón dinámico."""
	button.SetLabel(label)
	button.SetName(label.replace("&", ""))
