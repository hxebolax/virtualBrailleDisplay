"""Variables de compilación para Virtual Braille Display."""

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="virtualBrailleDisplay",
	addon_summary=_("Virtual Braille Display"),
	addon_description=_(
		"""Línea braille virtual para inspeccionar y depurar la salida braille de NVDA,
incluidos mensajes enviados por aplicaciones externas mediante NVDA Controller
Client y bibliotecas como accessible-output2.""",
	),
	addon_version="2026.08.30",
	addon_changelog=_(
		"""Añade filtro por aplicación, contexto real de origen, listas con navegación por
columnas, configuración con pestañas, explicación en lenguaje humano, comparación
libre de frames, simulación de otros tamaños, encaminamiento y entrada braille
simulados y registro continuo opcional.""",
	),
	addon_author="Héctor J. Benítez Corredera",
	addon_url=None,
	addon_sourceURL=None,
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2026.1.0",
	addon_lastTestedNVDAVersion="2026.3.0",
	addon_updateChannel=None,
	addon_license="GNU General Public License version 2.0 or later",
	addon_licenseURL="https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
)

pythonSources: list[str] = ["addon/**/*.py"]
i18nSources: list[str] = pythonSources + ["buildVars.py"]
documentationSources: list[str] = [
	"docs/architecture.md",
	"docs/origin-tracking.md",
	"docs/traducciones.md",
	"docs/testing.md",
]
excludedFiles: list[str] = ["**/__pycache__/**", "**/*.pyc"]
baseLanguage: str = "es"
# Los encabezados no reciben identificadores al convertirse a HTML, así que los índices usan
# anclas explícitas escritas en el propio Markdown. Con ellas los enlaces funcionan tanto en el
# HTML generado como al leer el archivo Markdown en cualquier visor.
markdownExtensions: list[str] = ["markdown.extensions.tables"]
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
