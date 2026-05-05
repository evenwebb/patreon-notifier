from unittest.mock import MagicMock

from patreon_notifier.health import HealthMonitor


def test_dry_run_skips_apprise_notify() -> None:
    hm = HealthMonitor(dry_run=True)
    hm.apobj = MagicMock()
    hm._notify_capable = True
    hm._send_alert("Test", "Body", "auth")
    hm.apobj.notify.assert_not_called()
