"""Lista accesible con navegación por columnas mediante los anuncios propios de NVDA.

No se emplea ninguna biblioteca externa de voz: al ser un complemento de NVDA se usa
``ui.message``, que habla y envía el texto a la línea braille a la vez, o
``speech.speakMessage`` cuando el usuario prefiere no ocupar la línea.
"""

from __future__ import annotations

import addonHandler
import api
import speech
import ui
import wx

addonHandler.initTranslation()

from . import config as addonConfig  # noqa: E402

# Número máximo de columnas accesibles con los atajos directos Ctrl+1 a Ctrl+9.
DIRECT_COLUMN_SHORTCUTS = 9


def announce(text: str) -> None:
	"""Anuncia un texto respetando la preferencia de usar o no la línea braille."""
	if not text:
		return
	if addonConfig.getBoolean("listSpeakOnly"):
		speech.speakMessage(text)
		return
	ui.message(text)


class AccessibleListCtrl(wx.ListCtrl):
	"""Lista en modo informe que permite recorrer las columnas de la fila enfocada.

	NVDA ya lee la fila completa al moverse con las flechas arriba y abajo. Esta clase
	añade lo que NVDA no puede saber por sí mismo: recorrer columna a columna con las
	flechas izquierda y derecha, saltar a una columna concreta con Ctrl+1 a Ctrl+9 y
	leer el texto íntegro de la celda, que Windows recorta en el control nativo.
	"""

	def __init__(
		self,
		parent: wx.Window,
		columns: tuple[tuple[str, int], ...],
		name: str,
		helpText: str = "",
	):
		"""Crea la lista, sus columnas y el estado de navegación por celdas."""
		super().__init__(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.SetName(name)
		if helpText:
			self.SetHelpText(helpText)
		self._columnLabels: list[str] = []
		for index, (label, width) in enumerate(columns):
			self.InsertColumn(index, label, width=width)
			self._columnLabels.append(label)
		# Texto íntegro de cada celda: el control nativo de Windows recorta a unos 511 caracteres.
		self._cellText: dict[int, dict[int, str]] = {}
		self._focusedColumn = 0
		self.Bind(wx.EVT_KEY_DOWN, self._onKeyDown)

	@property
	def focusedColumn(self) -> int:
		"""Devuelve la columna sobre la que está situada la navegación por celdas."""
		return self._focusedColumn

	def resetFocusedColumn(self) -> None:
		"""Vuelve a la primera columna, por ejemplo tras recargar la lista."""
		self._focusedColumn = 0

	def appendRow(self, values: tuple[str, ...]) -> int:
		"""Añade una fila al final devolviendo su índice."""
		row = self.InsertItem(self.GetItemCount(), values[0] if values else "")
		self.setRow(row, values)
		return row

	def setRow(self, row: int, values: tuple[str, ...]) -> None:
		"""Escribe todas las columnas de una fila conservando el texto íntegro."""
		storage = self._cellText.setdefault(row, {})
		for column, value in enumerate(values):
			text = value or ""
			self.SetItem(row, column, text)
			storage[column] = text

	def removeFirstRow(self) -> None:
		"""Elimina la fila más antigua reindexando el texto íntegro almacenado."""
		if not self.GetItemCount():
			return
		self.DeleteItem(0)
		self._cellText = {row - 1: values for row, values in self._cellText.items() if row > 0}

	def clearRows(self) -> None:
		"""Vacía la lista y el texto íntegro asociado."""
		self.DeleteAllItems()
		self._cellText.clear()
		self.resetFocusedColumn()

	def cellText(self, row: int, column: int) -> str:
		"""Devuelve el texto completo de una celda, no la versión recortada por Windows."""
		stored = self._cellText.get(row, {}).get(column)
		if stored is not None:
			return stored
		return self.GetItemText(row, column)

	def rowText(self, row: int) -> str:
		"""Devuelve el contenido completo de una fila con sus columnas separadas."""
		parts = [self.cellText(row, column) for column in range(self.GetColumnCount())]
		return ", ".join(part for part in parts if part)

	def focusedRow(self) -> int:
		"""Devuelve la fila enfocada o, si no hay foco de rectángulo, la seleccionada."""
		row = self.GetFocusedItem()
		if row == wx.NOT_FOUND:
			row = self.GetFirstSelected()
		return row

	def _onKeyDown(self, event: wx.KeyEvent) -> None:
		"""Gestiona la navegación por columnas sin interferir con el resto de teclas."""
		key = event.GetKeyCode()
		modifiers = event.GetModifiers()
		row = self.focusedRow()
		if modifiers == wx.MOD_NONE and key in (wx.WXK_LEFT, wx.WXK_RIGHT):
			if row == wx.NOT_FOUND:
				event.Skip()
				return
			self._moveColumn(row, forward=key == wx.WXK_RIGHT)
			return
		if modifiers == wx.MOD_CONTROL and ord("1") <= key <= ord("9"):
			if row == wx.NOT_FOUND:
				event.Skip()
				return
			self._selectColumn(row, key - ord("1"))
			return
		if modifiers == (wx.MOD_CONTROL | wx.MOD_SHIFT) and key == ord("C"):
			if row == wx.NOT_FOUND:
				event.Skip()
				return
			self._copyFocusedCell(row)
			return
		event.Skip()

	def _moveColumn(self, row: int, forward: bool) -> None:
		"""Avanza o retrocede una columna respetando la preferencia de dar la vuelta."""
		columnCount = self.GetColumnCount()
		if not columnCount:
			return
		step = 1 if forward else -1
		target = self._focusedColumn + step
		if addonConfig.getBoolean("listWrapColumns"):
			target %= columnCount
		elif not 0 <= target < columnCount:
			edge = _("Última columna.") if forward else _("Primera columna.")
			announce(edge)
			return
		self._focusedColumn = target
		self._announceCell(row, target)

	def _selectColumn(self, row: int, column: int) -> None:
		"""Salta directamente a una columna indicada con Ctrl más un número."""
		if not 0 <= column < self.GetColumnCount():
			announce(
				_("Sólo hay {count} columnas.").format(
					count=min(self.GetColumnCount(), DIRECT_COLUMN_SHORTCUTS)
				),
			)
			return
		self._focusedColumn = column
		self._announceCell(row, column)

	def _copyFocusedCell(self, row: int) -> None:
		"""Copia al portapapeles el contenido íntegro de la celda enfocada."""
		text = self.cellText(row, self._focusedColumn)
		if not text:
			announce(_("La celda está vacía; no se ha copiado nada."))
			return
		api.copyToClip(text, notify=False)
		announce(_("Celda copiada al portapapeles."))

	def _announceCell(self, row: int, column: int) -> None:
		"""Anuncia la celda con las partes que el usuario haya elegido en la configuración."""
		options = addonConfig.getListAnnouncementOptions()
		parts: list[str] = []
		if options["rowNumber"]:
			if options["totalRows"]:
				parts.append(
					_("Fila {row} de {total}").format(row=row + 1, total=self.GetItemCount()),
				)
			else:
				parts.append(_("Fila {row}").format(row=row + 1))
		if options["columnHeader"] and column < len(self._columnLabels):
			parts.append(self._columnLabels[column].replace("&", ""))
		if options["cellValue"] or not parts:
			text = self.cellText(row, column)
			if text:
				parts.append(text)
			elif options["emptyCells"]:
				parts.append(_("vacío"))
		announce(", ".join(part for part in parts if part))
