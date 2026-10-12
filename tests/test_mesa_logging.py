"""Unit tests for mesa_logging."""

import ast
import logging
import pathlib

import pytest

from mesa import mesa_logging


@pytest.fixture(autouse=True)
def tear_down():
    """Pytest fixture to ensure all logging state is reset after testing."""
    yield
    mesa_logging._logger = None
    mesa_logging._rootlogger = None
    mesa_logger = logging.getLogger(mesa_logging.LOGGER_NAME)
    mesa_logger.handlers = []
    mesa_logger.propagate = True


def test_get_logger():
    """Test get_logger."""
    mesa_logging._rootlogger = None
    logger = mesa_logging.get_rootlogger()
    assert logger == logging.getLogger(mesa_logging.LOGGER_NAME)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)

    logger = mesa_logging.get_rootlogger()
    assert logger, logging.getLogger(mesa_logging.LOGGER_NAME)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)


def test_log_to_stderr():
    """Test log_to_stderr."""
    mesa_logging._rootlogger = None
    logger = mesa_logging.log_to_stderr(mesa_logging.DEBUG)
    assert len(logger.handlers) == 2
    assert logger.level == mesa_logging.DEBUG

    mesa_logging._rootlogger = None
    logger = mesa_logging.log_to_stderr()
    assert len(logger.handlers) == 2
    assert logger.level == mesa_logging.DEFAULT_LEVEL

    logger = mesa_logging.log_to_stderr()
    assert len(logger.handlers) == 2
    assert logger.level == mesa_logging.DEFAULT_LEVEL


def test_log_to_stderr_propagation():
    """Test log_to_stderr with propagate parameter."""
    mesa_logging._rootlogger = None
    logger = mesa_logging.log_to_stderr(propagate=True)
    assert logger.propagate is True

    mesa_logging._rootlogger = None
    logger = mesa_logging.log_to_stderr(propagate=False)
    assert logger.propagate is False


def test_caplog_capture_after_teardown(caplog):
    """Verify that logger propagation allows caplog to capture records."""
    logger = mesa_logging.get_module_logger("test_propagation")
    logger.setLevel(logging.INFO)
    logger.info("testing caplog propagation")
    assert "testing caplog propagation" in caplog.text


def test_examples_do_not_configure_logging_at_import():
    """No example module may configure logging at import time. See #3935.

    `log_to_stderr()` defaults to `propagate=False` and applies it to the MESA
    root logger, so calling it at module level leaks that setting into every
    later consumer in the same process. Anything that imports the module --
    `solara run`, a notebook, or the test suite -- silently loses log
    propagation, which is what broke `caplog` in unrelated tests.

    This is a static check so it stays fast and does not depend on import order.
    """
    configures_logging = {"log_to_stderr", "log_to_file", "basicConfig", "dictConfig"}
    examples = pathlib.Path(mesa_logging.__file__).parent / "examples"

    offenders = []
    for path in sorted(examples.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:  # module level only
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            if name in configures_logging:
                rel = path.relative_to(examples)
                offenders.append(f"{rel.as_posix()}:{node.lineno}: {name}()")

    assert not offenders, (
        "example modules must not configure logging at import time: "
        + ", ".join(offenders)
    )
