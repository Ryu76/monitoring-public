import pytest
import yaml
from pathlib import Path

def test_compose_structure():
    """Ensure docker-compose.yml has worker service and no duplicate worker in API."""
    compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml not found"

    with open(compose_path, 'r', encoding='utf-8') as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get('services', {})

    assert 'backend' in services, "Backend service must exist"
    assert 'worker' in services, "Worker service must exist"

    backend = services['backend']
    worker = services['worker']

    # Check commands
    assert worker.get('command') == "python -m app.worker_main"
    assert "worker" not in backend.get('command', "")

    # Check secrets parity
    backend_env = backend.get('environment', [])
    worker_env = worker.get('environment', [])

    assert sorted(backend_env) == sorted(worker_env), "Backend and Worker must have the same environment variables"
