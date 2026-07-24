import importlib

import dotenv

import main as main_module


def _reload_main(monkeypatch):
    # main.py calls load_dotenv() at import time, and importlib.reload() re-executes that
    # `from dotenv import load_dotenv` + call on every reload. Left alone, that silently repopulates
    # os.environ from the developer's real local .env file, undoing monkeypatch.delenv/setenv and
    # making these tests depend on whatever CORS_ALLOWED_ORIGINS (if any) happens to be in it. Since
    # `from dotenv import load_dotenv` re-binds to whatever dotenv.load_dotenv currently is, patching
    # it here is what actually isolates the reload from the local .env.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    return importlib.reload(main_module)


def test_default_allowed_origins_are_vite_dev_server(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    module = _reload_main(monkeypatch)

    assert module.ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]


def test_allowed_origins_configurable_for_deployment(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com, https://admin.example.com")

    module = _reload_main(monkeypatch)

    assert module.ALLOWED_ORIGINS == ["https://app.example.com", "https://admin.example.com"]
