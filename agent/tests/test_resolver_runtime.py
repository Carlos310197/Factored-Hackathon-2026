from bankagent.resolver.model import Resolver
from bankagent.runtime import load_resolver
from tests.resolver_data import write_logreg_artifact


def test_load_resolver_is_optional_and_never_raises(tmp_path):
    assert load_resolver(None) is None
    assert load_resolver(str(tmp_path / "missing")) is None
    write_logreg_artifact(tmp_path / "ok")
    assert isinstance(load_resolver(str(tmp_path / "ok")), Resolver)
