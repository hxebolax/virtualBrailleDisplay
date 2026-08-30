"""Aplicación de consola para probar NVDA Controller Client mediante accessible-output2."""

from __future__ import annotations

import sys


def createNvdaOutput():
	"""Crea el backend específico de NVDA o termina con una explicación clara."""
	try:
		from accessible_output2.outputs.nvda import NVDA

		output = NVDA()
	except Exception as error:
		raise RuntimeError(
			"No se pudo cargar el backend NVDA. Instale accessible-output2 en este Python: "
			"python -m pip install accessible-output2",
		) from error
	if not output.is_active():
		raise RuntimeError("NVDA no está activo o su Controller Client no responde.")
	return output


def sendBoth(output, text: str) -> None:
	"""Envía voz y braille de forma explícita para evitar ambigüedades de ``Auto.output``."""
	output.speak(text)
	output.braille(text)


def runInteractive(output) -> None:
	"""Permite escribir, repetir y escoger el canal de salida desde la consola."""
	lastText = "Prueba de Virtual Braille Display"
	print("NVDA detectado. Comandos: b=braille, a=voz+braille, r=repetir, q=salir.")
	while True:
		command = input("Comando [b/a/r/q] o texto para braille: ").strip()
		if command.lower() == "q":
			return
		if command.lower() == "r":
			output.braille(lastText)
			continue
		if command.lower() in ("b", "a"):
			text = input("Mensaje: ")
			lastText = text
			if command.lower() == "a":
				sendBoth(output, text)
			else:
				output.braille(text)
			continue
		if command:
			lastText = command
			output.braille(command)


def main() -> int:
	"""Comprueba NVDA, envía mensajes iniciales y abre el modo interactivo."""
	try:
		output = createNvdaOutput()
	except RuntimeError as error:
		print(f"Error: {error}", file=sys.stderr)
		return 1
	output.braille("Mensaje braille enviado desde accessible-output2")
	sendBoth(output, "Mensaje enviado a voz y braille")
	runInteractive(output)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
