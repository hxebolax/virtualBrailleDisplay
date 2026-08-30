"""Pruebas del cálculo de la etiqueta de la release de recursos.

Esta regla debe coincidir exactamente con la del flujo de trabajo de GitHub Actions. Si las dos
divergieran, la API de GitHub devolvería 404 y el complemento dejaría de buscar recursos sin
avisar, así que conviene fijarla con pruebas.
"""

from __future__ import annotations

import importlib
import re
import unittest

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
versioning = importlib.import_module(f"{PACKAGE_NAME}.versioning")


def workflowTag(version: str) -> str:
	"""Reproduce literalmente el cálculo del paso «Determinar etiqueta de recursos»."""
	partes = re.findall(r"\d+", str(version).strip())
	if len(partes) >= 2:
		return f"recursos_{partes[0]}.{partes[1]}"
	if partes:
		return f"recursos_{partes[0]}"
	return "recursos-latest"


class ResourceTagTests(unittest.TestCase):
	"""Comprueba la etiqueta para las versiones que el complemento puede publicar."""

	def testFirstPublishedVersion(self) -> None:
		"""La primera versión publicada debe apuntar a la release ya creada."""
		self.assertEqual(versioning.resourceTagForVersion("2026.08.30"), "recursos_2026.08")

	def testLeadingZeroIsPreserved(self) -> None:
		"""El cero inicial del mes forma parte de la etiqueta y no debe perderse."""
		self.assertEqual(versioning.resourceTagForVersion("2026.09.01"), "recursos_2026.09")

	def testThirdComponentDoesNotChangeTheTag(self) -> None:
		"""Una corrección menor debe seguir usando el mismo paquete de recursos."""
		self.assertEqual(
			versioning.resourceTagForVersion("2026.08.31"),
			versioning.resourceTagForVersion("2026.08.30"),
		)

	def testMatchesWorkflowRule(self) -> None:
		"""El cálculo local debe coincidir con el del flujo de trabajo."""
		for version in ("2026.08.30", "2026.1", "2026.12.01", "1.0.0", "0.2.0"):
			with self.subTest(version=version):
				self.assertEqual(versioning.resourceTagForVersion(version), workflowTag(version))

	def testUnknownVersionYieldsNoTag(self) -> None:
		"""Sin dígitos no se inventa una etiqueta: se devuelve vacío para poder avisar."""
		for version in ("", None, "sin numeros"):
			with self.subTest(version=version):
				self.assertEqual(versioning.resourceTagForVersion(version), "")

	def testVersionIsReadFromManifest(self) -> None:
		"""La versión de respaldo debe extraerse del manifest instalado."""
		manifest = 'name = virtualBrailleDisplay\nsummary = "x"\nversion = 2026.08.30\n'
		self.assertEqual(versioning.versionFromManifest(manifest), "2026.08.30")

	def testManifestWithoutVersionYieldsEmpty(self) -> None:
		"""Un manifest sin versión no debe producir una etiqueta inventada."""
		self.assertEqual(versioning.versionFromManifest("name = x\n"), "")
