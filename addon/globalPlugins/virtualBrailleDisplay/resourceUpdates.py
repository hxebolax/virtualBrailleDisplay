"""Actualización de traducciones y documentación desde las releases del repositorio.

Envuelve el módulo reutilizable ``actualizadorRecursos`` para que el resto del complemento
no dependa de su API directamente. Aquí se decide qué se anuncia y cuándo, de modo que los
avisos usen el mismo canal que el resto del complemento y no se pierdan al cerrarse un menú.

El paquete de recursos se publica en una release aparte, etiquetada automáticamente a partir
de la versión del complemento. Con la versión ``2026.08.30`` la etiqueta es ``recursos_2026.08``,
tanto en el flujo de trabajo de GitHub como aquí, sin necesidad de configurarla en los dos sitios.
"""

from __future__ import annotations

from pathlib import Path

import addonHandler
import wx
from logHandler import log

addonHandler.initTranslation()

from . import config as addonConfig  # noqa: E402
from .messages import reportAction  # noqa: E402
from .versioning import resourceTagForVersion, versionFromManifest  # noqa: E402

# Repositorio del que se descargan las traducciones y la documentación.
GITHUB_USER = "hxebolax"
GITHUB_REPOSITORY = "virtualBrailleDisplay"


def installedVersion() -> str:
	"""Devuelve la versión instalada del complemento consultando primero a NVDA."""
	try:
		return str(addonHandler.getCodeAddon().version)
	except Exception:
		log.debugWarning("No se pudo consultar la versión con addonHandler", exc_info=True)
	# Respaldo: leer el manifest instalado, que siempre acompaña al complemento.
	try:
		manifestPath = Path(__file__).resolve().parents[2] / "manifest.ini"
		return versionFromManifest(manifestPath.read_text(encoding="utf-8"))
	except Exception:
		log.debugWarning("No se pudo leer la versión del manifest instalado", exc_info=True)
		return ""


class ResourceUpdateService:
	"""Comprueba e instala traducciones y documentación sin publicar una versión nueva."""

	def __init__(self):
		"""Crea el servicio sin contactar todavía con GitHub."""
		self._updater: object | None = None
		self._announceNextResult = False

	@property
	def available(self) -> bool:
		"""Indica si el actualizador pudo inicializarse."""
		return self._updater is not None

	def start(self) -> None:
		"""Instancia el actualizador con la configuración persistida del usuario.

		Se instancia siempre, incluso con la comprobación automática desactivada, para que la
		comprobación manual desde el menú o desde un gesto siga estando disponible.
		"""
		if self._updater is not None:
			return
		automatic = addonConfig.getBoolean("resourceUpdatesEnabled")
		# La etiqueta se calcula aquí, a partir de la versión instalada, y se pasa explícita.
		# El módulo la deduciría por su cuenta, pero si esa deducción fallara caería en
		# «recursos-latest», que no existe: la API devolvería 404 y el complemento dejaría de
		# buscar recursos en silencio. Calcularla con la misma regla del flujo de trabajo
		# elimina ese riesgo sin desincronizar nada.
		options: dict[str, object] = {}
		tag = resourceTagForVersion(installedVersion())
		if tag:
			options["tag_release"] = tag
		else:
			log.warning("No se pudo determinar la etiqueta de recursos; se usará la automática")
		try:
			from .actualizadorRecursos import ActualizadorRecursos

			self._updater = ActualizadorRecursos(
				GITHUB_USER,
				GITHUB_REPOSITORY,
				modo_comprobacion="inicio" if automatic else "manual",
				**options,
				intervalo_horas=addonConfig.getInteger("resourceUpdateIntervalHours"),
				# El complemento se encarga de los avisos para que también se oigan
				# cuando la acción se pide desde el menú de NVDA.
				notificar_usuario=False,
				notificar_sin_cambios=False,
				menuHerramientas=False,
				callback_finalizado=self._onFinished,
				callback_error=self._onError,
			)
		except Exception:
			log.error("No se pudo inicializar la actualización de recursos", exc_info=True)
			self._updater = None

	def stop(self) -> None:
		"""Detiene el actualizador y sus hilos al descargar el complemento."""
		updater = self._updater
		self._updater = None
		if updater is None:
			return
		try:
			updater.detener()
		except Exception:
			log.debugWarning("Error al detener la actualización de recursos", exc_info=True)

	def checkNow(self, fromMenu: bool = False) -> None:
		"""Comprueba inmediatamente si hay recursos nuevos, ignorando el intervalo."""
		if self._updater is None:
			reportAction(_("La actualización de recursos no está disponible."), fromMenu)
			return
		self._announceNextResult = True
		reportAction(_("Comprobando traducciones y documentación nuevas…"), fromMenu)
		try:
			self._updater.forzarActualizacion()
		except Exception:
			log.error("Error al comprobar los recursos del complemento", exc_info=True)
			self._announceNextResult = False
			reportAction(_("No se pudo comprobar si hay recursos nuevos."), fromMenu)

	def _onFinished(self, success: bool, result: dict[str, object]) -> None:
		"""Recibe el resultado desde el hilo del actualizador y lo lleva a la interfaz."""
		wx.CallAfter(self._presentResult, bool(success), dict(result or {}))

	def _onError(self, error: Exception) -> None:
		"""Recibe un error desde el hilo del actualizador."""
		log.debugWarning(f"Actualización de recursos: {error}")
		wx.CallAfter(self._presentResult, False, {})

	def _presentResult(self, success: bool, result: dict[str, object]) -> None:
		"""Anuncia el resultado sólo cuando aporta algo al usuario."""
		announceAlways = self._announceNextResult
		self._announceNextResult = False
		installed = int(result.get("instalados") or 0)
		if not success:
			if announceAlways:
				reportAction(_("No se pudieron comprobar los recursos. Inténtelo más tarde."))
			return
		if installed:
			reportAction(
				_(
					"Se han instalado recursos nuevos: {count} archivos. "
					"Reinicie NVDA para aplicarlos por completo.",
				).format(count=installed),
			)
			return
		if announceAlways:
			reportAction(_("Las traducciones y la documentación ya están al día."))
