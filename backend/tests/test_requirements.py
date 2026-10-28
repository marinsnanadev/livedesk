from pathlib import Path

REQUIREMENTS = Path(__file__).parent.parent / "requirements.txt"


def _requirements():
    lines = (line.strip() for line in REQUIREMENTS.read_text().splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def test_every_requirement_is_pinned_to_an_exact_version():
    # Regression test: sqlalchemy>=2.0.35 let a fresh install pick 2.1, which
    # changed the default Postgres driver, and the app died on import in a
    # deploy that had passed every test locally.
    loose = [line for line in _requirements() if "==" not in line]
    assert loose == []
