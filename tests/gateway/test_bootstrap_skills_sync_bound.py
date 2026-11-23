"""Gateway startup does not wait on a stalled skills sync (slow network skills dir).

Regression for the startup hang when ``skills.external_dirs`` sits on a stalled share.
"""
import threading

from gateway import run_bootstrap


def test_stalled_skills_sync_does_not_block_startup(monkeypatch):
    from tools import skills_sync

    entered, release = threading.Event(), threading.Event()

    def stalled_sync(quiet=False):
        entered.set()
        release.wait(60)

    monkeypatch.setattr(skills_sync, "sync_skills", stalled_sync)
    monkeypatch.setattr(run_bootstrap, "_SKILLS_SYNC_TIMEOUT_S", 0.2, raising=False)
    monkeypatch.setattr("hermes_logging.setup_logging", lambda **_: None)
    monkeypatch.setattr(
        "hermes_cli.security_audit_startup.log_startup_security_warnings", lambda **_: None)

    finished = threading.Event()

    def configure():
        run_bootstrap._start_gateway_configure_logging(None)
        finished.set()

    threading.Thread(target=configure, daemon=True).start()
    try:
        assert entered.wait(10)
        assert finished.wait(10), "startup stayed blocked on the stalled skills sync"
    finally:
        release.set()


def test_fast_skills_sync_completes_before_startup_continues(monkeypatch):
    from tools import skills_sync

    done = threading.Event()
    monkeypatch.setattr(skills_sync, "sync_skills", lambda quiet=False: done.set())
    monkeypatch.setattr("hermes_logging.setup_logging", lambda **_: None)
    monkeypatch.setattr(
        "hermes_cli.security_audit_startup.log_startup_security_warnings", lambda **_: None)

    run_bootstrap._start_gateway_configure_logging(None)
    assert done.is_set()
