"""Cálculo de la etiqueta de la release de recursos a partir de la versión del complemento.

La regla debe ser exactamente la misma aquí y en el flujo de trabajo de GitHub Actions: se
toman los dos primeros grupos de dígitos de la versión, conservando los ceros a la izquierda.
Con ``2026.08.30`` la etiqueta es ``recursos_2026.08``.

Si las dos partes no coincidieran, la API de GitHub devolvería 404 y el complemento dejaría de
buscar recursos en silencio. Por eso el cálculo vive en un módulo puro y con pruebas.
"""

from __future__ import annotations

import re

RESOURCE_TAG_PREFIX = "recursos_"


def resourceTagForVersion(version: str | None) -> str:
	"""Devuelve la etiqueta de recursos de una versión, o una cadena vacía si no se puede."""
	groups = re.findall(r"\d+", str(version or "").strip())
	if len(groups) >= 2:
		return f"{RESOURCE_TAG_PREFIX}{groups[0]}.{groups[1]}"
	if groups:
		return f"{RESOURCE_TAG_PREFIX}{groups[0]}"
	return ""


def versionFromManifest(manifestText: str) -> str:
	"""Extrae el valor de ``version`` de un manifest.ini de complemento."""
	for line in manifestText.splitlines():
		stripped = line.strip()
		if not stripped.startswith("version"):
			continue
		parts = stripped.split("=", 1)
		if len(parts) == 2:
			return parts[1].strip().strip('"').strip("'")
	return ""
