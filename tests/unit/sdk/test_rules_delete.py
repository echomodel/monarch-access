"""delete_rule decides success by re-reading the rules list.

Monarch's deleteTransactionRule returns ``deleted: false`` even when the rule
was deleted (observed live), so the flag is ignored. The client below
simulates that response (network I/O is the only stand-in).
"""

import asyncio

import pytest

from monarch.client import APIError
from monarch.rules import delete_rule


class SimulatedRules:
    def __init__(self, rule_ids, actually_deletes=True, errors=None):
        self.rules = set(rule_ids)
        self.actually_deletes = actually_deletes
        self.errors = errors

    async def _request(self, query, variables=None):
        if "deleteTransactionRule" in query:
            if self.actually_deletes and not self.errors:
                self.rules.discard(variables["id"])
            return {"deleteTransactionRule": {"deleted": False, "errors": self.errors}}
        if "transactionRules" in query:
            return {"transactionRules": [{"id": r} for r in sorted(self.rules)]}
        raise AssertionError(query[:60])


def test_deleted_rule_reports_success_despite_api_flag():
    client = SimulatedRules(["r1", "r2"])
    assert asyncio.run(delete_rule(client, "r1")) == {"success": True, "deleted": True}
    assert client.rules == {"r2"}


def test_rule_still_present_reports_not_deleted():
    client = SimulatedRules(["r1"], actually_deletes=False)
    assert asyncio.run(delete_rule(client, "r1")) == {"success": False, "deleted": False}


def test_api_errors_raise():
    client = SimulatedRules(["r1"], errors={"message": "nope", "fieldErrors": []})
    with pytest.raises(APIError, match="nope"):
        asyncio.run(delete_rule(client, "r1"))
