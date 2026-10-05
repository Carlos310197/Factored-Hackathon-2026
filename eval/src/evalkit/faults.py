"""Fault injection for tool-failure goals (spec §4.5). Faults replace a runtime's dependencies; the agent's code is
never changed. The graph's nodes read deps attributes at call time, so patching deps after build takes effect."""
import copy

FAULTS = ("jev_down", "serving_down", "dynamo_throttle")


class FailingProxy:
    """Every method call raises the error made by make_error."""

    def __init__(self, make_error):
        self._make_error = make_error

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise self._make_error()
        return fail


def throttling_error():
    from botocore.exceptions import ClientError
    return ClientError({"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "injected"}}, "PutItem")


def apply_fault(deps, fault: str | None) -> None:
    if fault is None or fault == "expire_after_turn_1":
        return
    if fault == "jev_down":
        from bankagent.decisions.jev import JevError
        deps.jev = FailingProxy(lambda: JevError("injected: jev unavailable"))
    elif fault == "serving_down":
        from bankagent.data.serving import ServingError
        deps.read = FailingProxy(lambda: ServingError("injected: serving data unreadable"))
    elif fault == "dynamo_throttle":
        from bankagent.tools.write import WriteTools
        store = copy.copy(deps.store)
        store.disputes = FailingProxy(throttling_error)
        deps.write = WriteTools(store, deps.policy)
    else:
        raise ValueError(f"unknown fault {fault!r}")
