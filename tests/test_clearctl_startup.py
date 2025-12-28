from pathlib import Path

import clearctl


def test_cleanup_existing_processes_removes_pidfiles(monkeypatch, tmp_path: Path) -> None:
    api_pid = tmp_path / "api.pid"
    web_pid = tmp_path / "web.pid"
    api_pid.write_text("123", encoding="ascii")
    web_pid.write_text("456", encoding="ascii")

    monkeypatch.setattr(clearctl, "API_PID", api_pid)
    monkeypatch.setattr(clearctl, "WEB_PID", web_pid)

    called = []

    def fake_alive(pid: int) -> bool:
        return True

    def fake_terminate(pid: int) -> bool:
        called.append(pid)
        return True

    monkeypatch.setattr(clearctl, "process_alive", fake_alive)
    monkeypatch.setattr(clearctl, "terminate_pid", fake_terminate)

    clearctl._cleanup_existing_processes()

    assert called == [123, 456]
    assert not api_pid.exists()
    assert not web_pid.exists()


def test_terminate_port_processes_auto_yes(monkeypatch) -> None:
    killed: list[int] = []

    def fake_port_in_use(port: int) -> bool:
        return True

    def fake_find_pids(port: int) -> list[int]:
        return [222, 333]

    def fake_terminate(pid: int) -> bool:
        killed.append(pid)
        return True

    monkeypatch.setattr(clearctl, "port_in_use", fake_port_in_use)
    monkeypatch.setattr(clearctl, "find_pids_by_port", fake_find_pids)
    monkeypatch.setattr(clearctl, "filter_matching_pids", lambda pids, tokens: pids)
    monkeypatch.setattr(clearctl, "terminate_pid", fake_terminate)

    assert clearctl._terminate_port_processes(8000, "API", True) is True
    assert killed == [222, 333]
