"""Aplicación wxPython accesible para probar voz y braille mediante accessible-output2."""

from __future__ import annotations

import wx


class TestFrame(wx.Frame):
	"""Ventana accesible con un mensaje y dos acciones de envío."""

	def __init__(self):
		"""Construye la interfaz e intenta conectar con el backend NVDA."""
		super().__init__(None, title="Prueba de Virtual Braille Display")
		self.output = self._createOutput()
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)
		sizer.Add(wx.StaticText(panel, label="&Mensaje:"), flag=wx.ALL, border=5)
		self.message = wx.TextCtrl(panel, value="Conectado al servidor")
		self.message.SetName("Mensaje")
		sizer.Add(self.message, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.bothButton = wx.Button(panel, label="Enviar a &voz y braille")
		self.brailleButton = wx.Button(panel, label="Enviar sólo a &braille")
		buttonSizer.Add(self.bothButton, flag=wx.ALL, border=5)
		buttonSizer.Add(self.brailleButton, flag=wx.ALL, border=5)
		sizer.Add(buttonSizer, flag=wx.EXPAND)
		self.status = wx.StaticText(panel, label="Listo" if self.output is not None else "NVDA no disponible")
		sizer.Add(self.status, flag=wx.ALL, border=5)
		self.bothButton.Bind(wx.EVT_BUTTON, self._onSendBoth)
		self.brailleButton.Bind(wx.EVT_BUTTON, self._onSendBraille)
		self.SetSize((520, 190))
		self.Centre()
		self.message.SetFocus()

	@staticmethod
	def _createOutput():
		"""Carga el backend NVDA y devuelve ``None`` cuando no puede usarse."""
		try:
			from accessible_output2.outputs.nvda import NVDA

			output = NVDA()
			return output if output.is_active() else None
		except Exception:
			return None

	def _onSendBoth(self, event: wx.CommandEvent) -> None:
		"""Envía el mensaje a voz y braille con dos llamadas inequívocas."""
		if not self._ensureOutput():
			return
		text = self.message.GetValue()
		self.output.speak(text)
		self.output.braille(text)
		self.status.SetLabel("Enviado a voz y braille")

	def _onSendBraille(self, event: wx.CommandEvent) -> None:
		"""Envía el mensaje únicamente a braille."""
		if not self._ensureOutput():
			return
		self.output.braille(self.message.GetValue())
		self.status.SetLabel("Enviado sólo a braille")

	def _ensureOutput(self) -> bool:
		"""Muestra un error accesible si no se pudo comunicar con NVDA."""
		if self.output is not None:
			return True
		wx.MessageBox(
			"NVDA no está activo o accessible-output2 no está instalado.",
			"Salida no disponible",
			wx.OK | wx.ICON_ERROR,
			self,
		)
		return False


class TestApplication(wx.App):
	"""Aplicación mínima que muestra la ventana de prueba."""

	def OnInit(self) -> bool:
		"""Crea y muestra la ventana principal."""
		frame = TestFrame()
		frame.Show()
		return True


def main() -> None:
	"""Inicia el bucle de eventos de wxPython."""
	application = TestApplication(False)
	application.MainLoop()


if __name__ == "__main__":
	main()
