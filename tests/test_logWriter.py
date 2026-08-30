"""Pruebas de los tres formatos de exportación manual."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
frameStoreModule = importlib.import_module(f"{PACKAGE_NAME}.frameStore")
logWriter = importlib.import_module(f"{PACKAGE_NAME}.logWriter")
models = importlib.import_module(f"{PACKAGE_NAME}.models")


class LogWriterTests(unittest.TestCase):
	"""Comprueba serialización y diferenciación entre frames y eventos."""

	def _records(self):
		"""Construye un frame y un evento reutilizables."""
		store = frameStoreModule.FrameStore()
		event = store.addExternalEvent("Secreto de prueba", "Controller Client")
		frame = store.captureFrame(
			(1, 2),
			models.FrameOrigin(associatedText="Conexión completada: áéíóú, ñ, €"),
		)
		return (frame,), (event,)

	def testJsonLinesHasExplicitTypes(self) -> None:
		"""Comprueba que JSONL diferencia ``externalEvent`` y ``frame``."""
		frames, events = self._records()
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "history.jsonl"
			logWriter.saveRecords(path, "jsonl", frames, events)
			items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
		self.assertEqual([item["type"] for item in items], ["externalEvent", "frame"])

	def testJsonPreservesRawCellsAsNumbers(self) -> None:
		"""Comprueba que bytes se conviertan en una lista JSON reversible."""
		frames, events = self._records()
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "history.json"
			logWriter.saveRecords(path, "json", frames, events)
			data = json.loads(path.read_text(encoding="utf-8"))
		self.assertEqual(data["frames"][0]["cellsRaw"], [1, 2])
		self.assertEqual(data["frames"][0]["associatedText"], "Conexión completada: áéíóú, ñ, €")

	def testTextExportIsUtf8(self) -> None:
		"""Comprueba que el texto legible se escribe como UTF-8 real en el formato humano."""
		frames, events = self._records()
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "history.txt"
			logWriter.saveRecords(path, "txt", frames, events)
			content = path.read_bytes()
		self.assertIn("Conexión completada: áéíóú, ñ, €".encode("utf-8"), content)

	def testUnknownFormatIsRejected(self) -> None:
		"""Comprueba que una extensión no admitida no produzca un archivo engañoso."""
		with self.assertRaises(ValueError):
			logWriter.saveRecords("unused.csv", "csv", (), ())
