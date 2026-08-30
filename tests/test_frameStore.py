"""Pruebas del historial y la materialización de frames."""

from __future__ import annotations

import importlib
import unittest

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
frameStoreModule = importlib.import_module(f"{PACKAGE_NAME}.frameStore")
models = importlib.import_module(f"{PACKAGE_NAME}.models")


class FrameStoreTests(unittest.TestCase):
	"""Verifica límites, identificadores, serialización y correlaciones."""

	def testHistoryKeepsNewestFrames(self) -> None:
		"""Comprueba que un historial lleno expulsa el frame más antiguo."""
		store = frameStoreModule.FrameStore(maximumItems=2)
		origin = models.FrameOrigin()
		store.captureFrame((1,), origin)
		store.captureFrame((2,), origin)
		store.captureFrame((3,), origin)
		self.assertEqual([frame.frameId for frame in store.getFrames()], [2, 3])

	def testCapturedFrameContainsAllRepresentations(self) -> None:
		"""Comprueba que el nivel B conserva bytes y formatos derivados coherentes."""
		store = frameStoreModule.FrameStore()
		frame = store.captureFrame(
			(1, 255),
			models.FrameOrigin(associatedText="Información legible ñ"),
		)
		self.assertEqual(frame.cellsRaw, b"\x01\xff")
		self.assertEqual(frame.cellsHex, "01 FF")
		self.assertEqual(frame.cellsDecimal, "1 255")
		self.assertEqual(frame.cellsBinary, "00000001 11111111")
		self.assertEqual(frame.cellsUnicode, "⠁⣿")
		self.assertEqual(frame.associatedText, "Información legible ñ")
		self.assertEqual(frame.toDictionary()["associatedText"], "Información legible ñ")
		self.assertGreater(frame.monotonicNanoseconds, 0)

	def testEventCorrelationIsRecorded(self) -> None:
		"""Comprueba que el evento conserva frame, confianza y motivo."""
		store = frameStoreModule.FrameStore()
		event = store.addExternalEvent("Hola", "Controller Client")
		store.markEventCorrelated(
			event.eventId,
			7,
			models.OriginConfidence.PROBABLE,
			"prueba",
		)
		updated = store.getEvents()[0]
		self.assertEqual(updated.correlatedFrameId, 7)
		self.assertEqual(updated.correlationConfidence, models.OriginConfidence.PROBABLE)

	def testClearDoesNotReuseIdentifiers(self) -> None:
		"""Comprueba que limpiar no vuelve ambiguos los identificadores de una sesión."""
		store = frameStoreModule.FrameStore()
		first = store.captureFrame((1,), models.FrameOrigin())
		store.clear()
		second = store.captureFrame((2,), models.FrameOrigin())
		self.assertGreater(second.frameId, first.frameId)
