# SPDX-License-Identifier: LGPL-2.1-or-later
"""Système de Result unifié pour la gestion des erreurs et avertissements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Sequence, TypeVar, overload

T = TypeVar("T")
U = TypeVar("U")

@dataclass(frozen=True)
class Result(Generic[T]):
    """Résultat d'une opération avec gestion unifiée des erreurs et avertissements."""

    value: T | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    def map(self, func: Callable[[T], U]) -> Result[U]:
        if self.is_failure:
            return Result(value=None, errors=self.errors, warnings=self.warnings)  # type: ignore
        return Result(value=func(self.value), errors=self.errors, warnings=self.warnings)  # type: ignore

    def flat_map(self, func: Callable[[T], Result[U]]) -> Result[U]:
        if self.is_failure:
            return Result(value=None, errors=self.errors, warnings=self.warnings)  # type: ignore
        nested = func(self.value)  # type: ignore
        return Result(
            value=nested.value,
            errors=self.errors + nested.errors,
            warnings=self.warnings + nested.warnings,
        )

    def bind(self, func: Callable[[T], Result[U]]) -> Result[U]:
        return self.flat_map(func)

    def on_success(self, func: Callable[[T], None]) -> Result[T]:
        if self.is_success:
            func(self.value)  # type: ignore
        return self

    def on_failure(self, func: Callable[[Sequence[str]], None]) -> Result[T]:
        if self.is_failure:
            func(self.errors)
        return self

    def unwrap(self) -> T:
        if self.is_failure:
            raise ResultError(self.errors)
        return self.value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        return self.value if self.is_success else default

    def expect(self, message: str) -> T:
        if self.is_failure:
            raise ResultError([message, *self.errors])
        return self.value  # type: ignore

    @classmethod
    def from_optional(cls, value: T | None, error: str | None = None) -> Result[T]:
        if value is None:
            return Result(value=None, errors=[error or "Value is None"])  # type: ignore
        return Result(value=value)

    def __bool__(self) -> bool:
        return self.is_success

class ResultError(Exception):
    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if len(self.errors) == 1:
            return self.errors[0]
        return "Multiple errors:\n" + "\n".join(f"  - {err}" for err in self.errors)

def success(value: T, warnings: Sequence[str] | None = None) -> Result[T]:
    return Result(value=value, warnings=list(warnings or []))

def failure(*errors: str, warnings: Sequence[str] | None = None) -> Result[Any]:
    return Result(value=None, errors=list(errors), warnings=list(warnings or []))

def error(error: str, warnings: Sequence[str] | None = None) -> Result[Any]:
    return failure(error, warnings=warnings)

def validate(
    value: T,
    *validators: Callable[[T], list[str]],
    warnings: Sequence[str] | None = None,
) -> Result[T]:
    all_errors: list[str] = []
    for validator in validators:
        all_errors.extend(validator(value))
    return Result(value=value, errors=all_errors, warnings=list(warnings or []))

@overload
def combine(*results: Result[Any]) -> Result[tuple[()]]: ...

@overload
def combine(*results: Result[T]) -> Result[tuple[T, ...]]: ...

def combine(*results: Result[Any]) -> Result[tuple[Any, ...]]:
    if not results:
        return success(tuple())
    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_values: list[Any] = []
    for result in results:
        all_errors.extend(result.errors)
        all_warnings.extend(result.warnings)
        if result.is_success:
            all_values.append(result.value)
    if all_errors:
        return Result(value=None, errors=all_errors, warnings=all_warnings)  # type: ignore
    return Result(value=tuple(all_values), warnings=all_warnings)

__all__ = [
    "Result",
    "ResultError",
    "combine",
    "error",
    "failure",
    "success",
    "validate",
]