import os
import sys
import time
import subprocess
import signal
import pytest

from app.worker_main import acquire_local_lock, release_local_lock, handle_shutdown, running

def test_local_lock_prevents_duplicate():
    # Ensure lock is clear initially
    release_local_lock()

    # Try acquiring lock in this process
    acquired = acquire_local_lock()
    assert acquired is True

    # Try acquiring lock again in a subprocess (should fail)
    script = """
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.worker_main import acquire_local_lock
acquired = acquire_local_lock()
sys.exit(0 if not acquired else 1)
"""
    scratch_script = "scratch_lock_test.py"
    with open(scratch_script, "w") as f:
        f.write(script)

    try:
        # The subprocess should return 0 because acquire_local_lock returns False (not acquired)
        result = subprocess.run([sys.executable, scratch_script], capture_output=True)
        assert result.returncode == 0, "Subprocess should fail to acquire lock and exit 0"
    finally:
        os.remove(scratch_script)
        release_local_lock()

def test_api_worker_separation():
    # Make sure app.main does not import apscheduler
    import sys
    # Clear out apscheduler if loaded
    for mod in list(sys.modules.keys()):
        if 'apscheduler' in mod:
            del sys.modules[mod]
            
    import app.main
    assert 'apscheduler' not in sys.modules, "API main should not import apscheduler (Separation of concerns)"

def test_graceful_shutdown():
    import app.worker_main as wm
    wm.running = True
    assert wm.running is True
    wm.handle_shutdown(signal.SIGINT, None)
    assert wm.running is False
