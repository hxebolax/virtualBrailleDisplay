"""Pruebas del filtrado por aplicación y de las estadísticas del historial."""

from __future__ import annotations

import importlib
import unittest

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
frameStoreModule = importlib.import_module(f"{PACKAGE_NAME}.frameStore")
models = importlib.import_module(f"{PACKAGE_NAME}.models")


def originForProcess(processId: int | None, processName: str | None) -> object:
	"""Construye un origen con únicamente contexto de proceso, sin atribución externa."""
	return models.FrameOrigin(
		context=models.FrameContext(processId=processId, processName=processName),
	)


class ApplicationFilterTests(unittest.TestCase):
	"""Comprueba que el filtro nunca descarta ni inventa frames de otros procesos."""

	def setUp(self) -> None:
		"""Crea un historial con frames de dos aplicaciones distintas."""
		self.store = frameStoreModule.FrameStore()
		self.store.captureFrame(bytes([0x2D]), originForProcess(100, "uno.exe"))
		self.store.captureFrame(bytes([0x15]), originForProcess(200, "dos.exe"))
		self.store.captureFrame(bytes([0x00]), originForProcess(100, "uno.exe"))

	def testUnfilteredHistoryKeepsEveryFrame(self) -> None:
		"""Sin filtro deben verse todos los frames capturados."""
		self.assertEqual(len(self.store.getFrames()), 3)

	def testFilterKeepsOnlyRequestedProcess(self) -> None:
		"""Con filtro sólo deben verse los frames del proceso indicado."""
		frames = self.store.getFrames(100)
		self.assertEqual([frame.frameId for frame in frames], [1, 3])

	def testLastFrameRespectsFilter(self) -> None:
		"""El frame más reciente debe calcularse dentro del filtro activo."""
		self.assertEqual(self.store.getLastFrame(200).frameId, 2)

	def testKnownProcessesAreEnumerated(self) -> None:
		"""El almacén debe enumerar los procesos observados con su nombre."""
		self.assertEqual(self.store.getKnownProcesses(), ((100, "uno.exe"), (200, "dos.exe")))

	def testStatisticsCountBlankAndFilteredFrames(self) -> None:
		"""Las estadísticas deben contar frames en blanco respetando el filtro."""
		statistics = self.store.getStatistics(100)
		self.assertEqual(statistics["frames"], 2)
		self.assertEqual(statistics["blankFrames"], 1)

	def testApplicationFilterModelAcceptsMatchingFrames(self) -> None:
		"""El modelo de filtro debe aceptar sólo los frames del proceso elegido."""
		applicationFilter = models.ApplicationFilter(processId=200, processName="dos.exe")
		frames = self.store.getFrames()
		self.assertEqual(
			[frame.frameId for frame in frames if applicationFilter.accepts(frame)],
			[2],
		)

	def testInactiveFilterAcceptsEverything(self) -> None:
		"""Un filtro sin proceso no debe descartar ningún frame."""
		applicationFilter = models.ApplicationFilter()
		self.assertFalse(applicationFilter.isActive)
		self.assertTrue(all(applicationFilter.accepts(frame) for frame in self.store.getFrames()))

	def testExternalProcessAlsoMatches(self) -> None:
		"""Un frame atribuido a una solicitud externa debe coincidir por ese mismo PID."""
		origin = models.FrameOrigin(processId=999, applicationName="externa.exe")
		frame = self.store.captureFrame(bytes([0x01]), origin)
		self.assertTrue(frame.matchesProcess(999))
		self.assertFalse(frame.matchesProcess(100))
