"""Tests pour la hiérarchie d'exceptions apicol."""

from __future__ import annotations

import pytest

from apicol._errors import (
    ApicolError,
    BackendError,
    BackendUnavailableError,
    ConfigError,
    NotSupportedError,
)


class TestHierarchy:
    def test_apicol_error_is_exception(self) -> None:
        assert issubclass(ApicolError, Exception)

    def test_config_error_inherits_apicol_error(self) -> None:
        assert issubclass(ConfigError, ApicolError)

    def test_backend_unavailable_inherits_apicol_error(self) -> None:
        assert issubclass(BackendUnavailableError, ApicolError)

    def test_backend_error_inherits_apicol_error(self) -> None:
        assert issubclass(BackendError, ApicolError)

    def test_not_supported_inherits_apicol_error(self) -> None:
        assert issubclass(NotSupportedError, ApicolError)


class TestCausePreservation:
    def test_backend_error_preserves_cause(self) -> None:
        original = ValueError("upstream failure")
        try:
            try:
                raise original
            except ValueError as e:
                raise BackendError("wrapped") from e
        except BackendError as wrapped:
            assert wrapped.__cause__ is original

    def test_config_error_preserves_cause(self) -> None:
        original = KeyError("APICOL_TYPE")
        try:
            try:
                raise original
            except KeyError as e:
                raise ConfigError("missing env var") from e
        except ConfigError as wrapped:
            assert wrapped.__cause__ is original


class TestUserCanCatchByBaseClass:
    def test_catch_all_via_apicol_error(self) -> None:
        with pytest.raises(ApicolError):
            raise ConfigError("oops")
        with pytest.raises(ApicolError):
            raise BackendError("oops")
        with pytest.raises(ApicolError):
            raise BackendUnavailableError("oops")
        with pytest.raises(ApicolError):
            raise NotSupportedError("oops")
