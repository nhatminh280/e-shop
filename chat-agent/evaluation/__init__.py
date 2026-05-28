from typing import Any

__all__ = ["EvaluationResult", "evaluate_cases", "load_cases"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import runner

        return getattr(runner, name)
    raise AttributeError(name)
