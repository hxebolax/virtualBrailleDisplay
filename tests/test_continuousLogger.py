"""Pruebas del registro continuo en segundo plano."""

from __future__ import annotations

import importlib
import json
import tempfile
import time
import unittest
from pathlib import Path

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
logWriter = importlib.import_module(f"{PACKAGE_NAME}.logWriter")
frameStoreModule = importlib.import_module(f"{PACKAGE_NAME}.frameStore")
models = importlib.import_module(f"{PACKAGE_NAME}.models")


def waitForLines(path: Path, expected: int, timeoutSeconds: float = 2.0) -> list[str]:
	"""Espera a que el hilo escritor vuelque el número de líneas esperado."""
	deadline = time.monotonic() + timeoutSeconds
	while time.monotonic() < deadline:
		if path.exists():
			lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
			if len(lines) >= expected:
				return lines
		time.sleep(0.01)
	return [line for line in path.read_text(encoding="utf-8").splitlines() if line] if path.exists() else []


class ContinuousLoggerTests(unittest.TestCase):
	"""Comprueba el arranque, la escritura y la parada del registro continuo."""

	def setUp(self) -> None:
		"""Crea una carpeta temporal y un almacén con un frame de ejemplo."""
		self.directory = tempfile.TemporaryDirectory()
		self.path = Path(self.directory.name) / "registro.jsonl"
		self.store = frameStoreModule.FrameStore()
		self.logger = logWriter.ContinuousLogger()

	def tearDown(self) -> None:
		"""Detiene el registrador y elimina la carpeta temporal."""
		self.logger.stop()
		self.directory.cleanup()

	def testInactiveByDefault(self) -> None:
		"""Un registrador recién creado no debe estar activo."""
		self.assertFalse(self.logger.active)

	def testRejectsUnsupportedFormat(self) -> None:
		"""Sólo deben admitirse los formatos declarados para registro continuo."""
		with self.assertRaises(ValueError):
			self.logger.start(self.path, "json")

	def testRejectsMissingFolder(self) -> None:
		"""Una carpeta inexistente debe rechazarse antes de arrancar el hilo."""
		with self.assertRaises(ValueError):
			self.logger.start(Path(self.directory.name) / "inexistente" / "a.jsonl", "jsonl")

	def testFrameIsWrittenAsJsonLine(self) -> None:
		"""Cada frame registrado debe producir una línea JSON independiente."""
		self.logger.start(self.path, "jsonl")
		frame = self.store.captureFrame(bytes([0x2D, 0x15]), models.FrameOrigin())
		self.logger.logFrame(frame)
		lines = waitForLines(self.path, 1)
		self.assertEqual(len(lines), 1)
		record = json.loads(lines[0])
		self.assertEqual(record["type"], "frame")
		self.assertEqual(record["frameId"], frame.frameId)
		self.assertEqual(record["cellsRaw"], [0x2D, 0x15])

	def testEventIsWrittenAsJsonLine(self) -> None:
		"""Cada evento externo registrado debe producir su propia línea JSON."""
		self.logger.start(self.path, "jsonl")
		event = self.store.addExternalEvent("hola", "prueba", processId=7, processName="x.exe")
		self.logger.logEvent(event)
		lines = waitForLines(self.path, 1)
		record = json.loads(lines[0])
		self.assertEqual(record["type"], "externalEvent")
		self.assertEqual(record["text"], "hola")

	def testTextFormatProducesReadableLines(self) -> None:
		"""El formato de texto debe generar una línea legible por frame."""
		path = Path(self.directory.name) / "registro.txt"
		self.logger.start(path, "txt")
		frame = self.store.captureFrame(bytes([0x2D]), models.FrameOrigin())
		self.logger.logFrame(frame)
		lines = waitForLines(path, 1)
		self.assertIn("frame", lines[0])
		self.assertIn("2D", lines[0])

	def testStopDeactivatesLogger(self) -> None:
		"""Detener el registro debe dejarlo inactivo y sin archivo asociado."""
		self.logger.start(self.path, "jsonl")
		self.logger.stop()
		self.assertFalse(self.logger.active)

	def testLoggingWhileStoppedIsIgnored(self) -> None:
		"""Registrar sin haber arrancado no debe crear archivos ni lanzar errores."""
		frame = self.store.captureFrame(bytes([0x2D]), models.FrameOrigin())
		self.logger.logFrame(frame)
		self.assertFalse(self.path.exists())
