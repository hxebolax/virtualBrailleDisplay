"""Pruebas de correlación temporal y textual sin atribuciones excesivas."""

from __future__ import annotations

import importlib
import unittest

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
frameStoreModule = importlib.import_module(f"{PACKAGE_NAME}.frameStore")
models = importlib.import_module(f"{PACKAGE_NAME}.models")
originTrackerModule = importlib.import_module(f"{PACKAGE_NAME}.originTracker")


class OriginTrackerTests(unittest.TestCase):
	"""Verifica coincidencias útiles y casos en los que el origen debe quedar desconocido."""

	def testExactTextProducesProbableCorrelation(self) -> None:
		"""Comprueba la correlación probable cuando texto, tiempo y celdas son compatibles."""
		store = frameStoreModule.FrameStore()
		event = store.addExternalEvent("Hola", "Controller Client")
		tracker = originTrackerModule.OriginTracker(store)
		tracker.notePreWrite((1, 2), "Hola", 4)
		origin = tracker.consumeForDisplay((1, 2, 0, 0))
		self.assertEqual(origin.correlatedEventId, event.eventId)
		self.assertEqual(origin.originConfidence, models.OriginConfidence.PROBABLE)
		self.assertEqual(origin.originType, models.OriginType.CORRELATED_EXTERNAL_MESSAGE)
		self.assertEqual(origin.associatedText, "Hola")

	def testReadableTextIsPreservedWithoutExternalEvent(self) -> None:
		"""Comprueba que la navegación normal también conserva el texto de ventana de NVDA."""
		store = frameStoreModule.FrameStore()
		tracker = originTrackerModule.OriginTracker(store)
		tracker.notePreWrite((1, 2, 3), "Conexión completada", 3)
		origin = tracker.consumeForDisplay((1, 2, 3))
		self.assertEqual(origin.originType, models.OriginType.UNKNOWN)
		self.assertEqual(origin.associatedText, "Conexión completada")

	def testAmbiguousTemporalEventsStayUnknown(self) -> None:
		"""Comprueba que dos candidatos sin texto coincidente no se atribuyan por orden."""
		store = frameStoreModule.FrameStore()
		store.addExternalEvent("Uno", "Controller Client")
		store.addExternalEvent("Dos", "Controller Client")
		tracker = originTrackerModule.OriginTracker(store)
		tracker.notePreWrite((1,), "Otro", 1)
		origin = tracker.consumeForDisplay((1,))
		self.assertEqual(origin.originType, models.OriginType.UNKNOWN)
		self.assertIsNone(origin.correlatedEventId)

	def testMismatchedCellsDoNotKeepEventAttribution(self) -> None:
		"""Comprueba que un contexto textual no sustituya al buffer real de otro frame."""
		store = frameStoreModule.FrameStore()
		store.addExternalEvent("Hola", "Controller Client")
		tracker = originTrackerModule.OriginTracker(store)
		tracker.notePreWrite((1,), "Hola", 1)
		origin = tracker.consumeForDisplay((2,))
		self.assertEqual(origin.originType, models.OriginType.UNKNOWN)
		self.assertIsNone(origin.correlatedEventId)
		self.assertIsNone(origin.associatedText)

	def testPaddingAndTruncationAreCompatible(self) -> None:
		"""Comprueba las dos normalizaciones que NVDA puede aplicar antes del driver."""
		checker = originTrackerModule.OriginTracker._cellsAreCompatible
		self.assertTrue(checker(b"\x01\x02", b"\x01\x02\x00\x00"))
		self.assertTrue(checker(b"\x01\x02\x03", b"\x01\x02"))
		self.assertFalse(checker(b"\x01", b"\x02"))
