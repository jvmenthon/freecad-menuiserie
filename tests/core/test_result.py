# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tests unitaires pour le système de Result."""

import pytest

from freecad.menuiserie.core.result import (
    Result,
    ResultError,
    combine,
    error,
    failure,
    success,
    validate,
)

class TestResultCreation:
    def test_success_with_value(self):
        result = success(42)
        assert result.is_success
        assert not result.is_failure
        assert result.value == 42
        assert result.errors == []
        assert result.warnings == []

    def test_success_with_warnings(self):
        result = success(42, warnings=["warning1", "warning2"])
        assert result.is_success
        assert result.value == 42
        assert result.warnings == ["warning1", "warning2"]

    def test_failure_with_errors(self):
        result = failure("error1", "error2")
        assert result.is_failure
        assert result.value is None
        assert result.errors == ["error1", "error2"]

    def test_failure_with_warnings(self):
        result = failure("error1", warnings=["warning1"])
        assert result.is_failure
        assert result.errors == ["error1"]
        assert result.warnings == ["warning1"]

    def test_error_single(self):
        result = error("single error")
        assert result.is_failure
        assert result.errors == ["single error"]

class TestResultMethods:
    def test_map_success(self):
        result = success(10)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_success
        assert mapped.value == 20

    def test_flat_map_success(self):
        result = success(10)
        flat_mapped = result.flat_map(lambda x: success(x * 2))
        assert flat_mapped.is_success
        assert flat_mapped.value == 20

    def test_unwrap_success(self):
        result = success(42)
        assert result.unwrap() == 42

    def test_unwrap_failure(self):
        result = failure("error")
        with pytest.raises(ResultError):
            result.unwrap()

    def test_combine_all_success(self):
        r1 = success(1)
        r2 = success(2)
        combined = combine(r1, r2)
        assert combined.is_success
        assert combined.value == (1, 2)

class TestValidate:
    def test_validate_success(self):
        result = validate(10, lambda x: [] if x > 0 else ["error"])
        assert result.is_success

    def test_validate_failure(self):
        result = validate(-5, lambda x: ["error"] if x <= 0 else [])
        assert result.is_failure

class TestResultBool:
    def test_bool_success(self):
        assert bool(success(1)) is True

    def test_bool_failure(self):
        assert bool(failure("error")) is False