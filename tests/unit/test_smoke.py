"""Smoke test : vérifie que le package apicol est importable.

Existe à partir de Task 0 pour que `make check` ne retourne pas exit 5
(no tests collected) avant que les vraies suites n'arrivent en Task 1+.
"""

from __future__ import annotations


def test_apicol_package_importable() -> None:
    import apicol  # noqa: F401
