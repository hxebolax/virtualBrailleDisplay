"""Pruebas exhaustivas de conversión y comparación de celdas."""

from __future__ import annotations

import importlib
import unittest

from ._package import prepareCorePackage

PACKAGE_NAME = prepareCorePackage()
brailleUtils = importlib.import_module(f"{PACKAGE_NAME}.brailleUtils")


class BrailleUtilsTests(unittest.TestCase):
	"""Verifica el mapeo braille de los 256 patrones y los formatos derivados."""

	def testEveryByteMapsToItsUnicodeOffset(self) -> None:
		"""Comprueba que cada byte conserva exactamente sus bits en Unicode Braille."""
		for value in range(256):
			with self.subTest(value=value):
				self.assertEqual(ord(brailleUtils.cellToUnicode(value)), 0x2800 + value)

	def testEveryDotUsesItsStandardBit(self) -> None:
		"""Comprueba el mapeo bit cero a punto uno hasta bit siete a punto ocho."""
		for dot in range(1, 9):
			with self.subTest(dot=dot):
				self.assertEqual(brailleUtils.cellToDots(1 << (dot - 1)), (dot,))

	def testAllDotsAndBlank(self) -> None:
		"""Comprueba los extremos vacío y ocho puntos."""
		self.assertEqual(brailleUtils.cellToDots(0), ())
		self.assertEqual(brailleUtils.cellToDots(255), tuple(range(1, 9)))

	def testFormatting(self) -> None:
		"""Comprueba hexadecimal, decimal, binario y Unicode en un buffer pequeño."""
		cells = (0, 1, 128, 255)
		self.assertEqual(brailleUtils.cellsToDecimal(cells), "0 1 128 255")
		self.assertEqual(brailleUtils.cellsToHex(cells), "00 01 80 FF")
		self.assertEqual(
			brailleUtils.cellsToBinary(cells),
			"00000000 00000001 10000000 11111111",
		)
		self.assertEqual(brailleUtils.cellsToUnicode(cells), "⠀⠁⢀⣿")

	def testComparisonFindsChangedAddedAndRemoved(self) -> None:
		"""Comprueba los tres tipos de diferencia solicitados."""
		changed = brailleUtils.compareCells((1, 2), (1, 3, 4))
		self.assertEqual(
			[(item.position, item.changeType) for item in changed], [(2, "CHANGED"), (3, "ADDED")]
		)
		removed = brailleUtils.compareCells((1, 2), (1,))
		self.assertEqual([(item.position, item.changeType) for item in removed], [(2, "REMOVED")])

	def testCellValidationRejectsInvalidValues(self) -> None:
		"""Comprueba que no se silencien bytes corruptos ni booleanos."""
		for value in (-1, 256):
			with self.subTest(value=value):
				with self.assertRaises(ValueError):
					brailleUtils.validateCellValue(value)
		with self.assertRaises(TypeError):
			brailleUtils.validateCellValue(True)

	def testCellCountLimits(self) -> None:
		"""Comprueba los límites de una a 256 celdas."""
		self.assertEqual(brailleUtils.validateCellCount(1), 1)
		self.assertEqual(brailleUtils.validateCellCount(256), 256)
		for value in (0, 257):
			with self.subTest(value=value):
				with self.assertRaises(ValueError):
					brailleUtils.validateCellCount(value)

	def testTrailingBlanksAreTrimmed(self) -> None:
		"""Comprueba que el relleno final de NVDA no cuenta como contenido."""
		self.assertEqual(brailleUtils.trimTrailingBlanks((1, 2, 0, 0)), bytes((1, 2)))
		self.assertEqual(brailleUtils.countUsedCells((1, 2, 0, 0)), 2)
		self.assertEqual(brailleUtils.countUsedCells((0, 0)), 0)

	def testInternalBlanksAreNotTrimmed(self) -> None:
		"""Comprueba que un espacio intermedio sigue formando parte del contenido."""
		self.assertEqual(brailleUtils.countUsedCells((1, 0, 2, 0)), 3)

	def testWindowSplitPreservesEveryByte(self) -> None:
		"""Comprueba que repartir en ventanas no altera ni pierde ninguna celda."""
		cells = tuple(range(10))
		windows = brailleUtils.splitIntoWindows(cells, 4)
		self.assertEqual(len(windows), 3)
		self.assertEqual(b"".join(windows), bytes(cells))
		self.assertEqual(windows[-1], bytes((8, 9)))

	def testWindowSplitOfEmptyBufferIsEmpty(self) -> None:
		"""Comprueba que un buffer vacío no genera ninguna ventana."""
		self.assertEqual(brailleUtils.splitIntoWindows((), 20), ())

	def testWindowSplitValidatesSize(self) -> None:
		"""Comprueba que el tamaño de ventana respeta los límites del complemento."""
		with self.assertRaises(ValueError):
			brailleUtils.splitIntoWindows((1, 2), 0)

	def testRowSplitMatchesWindowSplit(self) -> None:
		"""Comprueba que el reparto por filas reutiliza exactamente el mismo cálculo."""
		cells = tuple(range(6))
		self.assertEqual(
			brailleUtils.splitIntoRows(cells, 3),
			brailleUtils.splitIntoWindows(cells, 3),
		)
