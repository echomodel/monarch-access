"""create_rule sends every action Monarch's rule input accepts.

A rule can set the category, rename the merchant, add tags, and set the
review status in one input; these tests check the SDK forwards each one
and rejects a bad review status before any request is sent. The client
below records the mutation input (network I/O is the only stand-in).
"""

import asyncio

import pytest

from monarch.client import APIError
from monarch.rules import REVIEW_STATUS_VALUES, create_rule, format_rule


class RecordingClient:
    def __init__(self, errors=None):
        self.requests = []
        self.errors = errors

    async def _request(self, query, variables=None):
        self.requests.append((query, variables))
        assert "createTransactionRuleV2" in query
        return {"createTransactionRuleV2": {"errors": self.errors}}


def _input(client):
    assert len(client.requests) == 1
    return client.requests[0][1]["input"]


def test_review_status_and_merchant_are_sent_with_category():
    client = RecordingClient()
    result = asyncio.run(create_rule(
        client,
        merchant_criteria=[{"operator": "contains", "value": "shell"}],
        set_category_action="cat_002",
        set_merchant_action="Shell",
        review_status_action="reviewed",
    ))
    assert result == {"success": True}
    sent = _input(client)
    assert sent["setCategoryAction"] == "cat_002"
    assert sent["setMerchantAction"] == "Shell"
    assert sent["reviewStatusAction"] == "reviewed"
    assert sent["merchantCriteria"] == [{"operator": "contains", "value": "shell"}]


@pytest.mark.parametrize("status", REVIEW_STATUS_VALUES)
def test_each_accepted_review_status_is_forwarded(status):
    client = RecordingClient()
    asyncio.run(create_rule(
        client,
        merchant_criteria=[{"operator": "eq", "value": "x"}],
        review_status_action=status,
    ))
    assert _input(client)["reviewStatusAction"] == status


def test_omitted_review_status_is_sent_as_null():
    client = RecordingClient()
    asyncio.run(create_rule(
        client,
        merchant_criteria=[{"operator": "eq", "value": "x"}],
        set_category_action="cat_001",
    ))
    assert _input(client)["reviewStatusAction"] is None


def test_bad_review_status_is_rejected_before_any_request():
    client = RecordingClient()
    with pytest.raises(ValueError, match="review_status_action"):
        asyncio.run(create_rule(
            client,
            merchant_criteria=[{"operator": "eq", "value": "x"}],
            review_status_action="done",
        ))
    assert client.requests == []


def test_api_errors_raise():
    client = RecordingClient(errors={"message": "nope", "fieldErrors": []})
    with pytest.raises(APIError, match="nope"):
        asyncio.run(create_rule(
            client,
            merchant_criteria=[{"operator": "eq", "value": "x"}],
            review_status_action="reviewed",
        ))


def test_format_rule_reports_review_status_and_merchant():
    rule = {
        "id": "r1",
        "order": 0,
        "merchantCriteria": [{"operator": "eq", "value": "x"}],
        "setMerchantAction": {"id": "m1", "name": "Shell"},
        "reviewStatusAction": "needs_review",
    }
    actions = format_rule(rule)["actions"]
    assert actions["set_merchant"] == "Shell"
    assert actions["review_status"] == "needs_review"


class TestLocalProviderCreateRule:
    def test_review_status_and_merchant_are_stored(self, local_provider):
        result = local_provider.create_rule(
            merchant_criteria=[{"operator": "contains", "value": "shell"}],
            set_category_action="cat_002",
            set_merchant_action="Shell",
            review_status_action="reviewed",
        )
        rule = result["rule"]
        assert rule["reviewStatusAction"] == "reviewed"
        assert rule["setMerchantAction"]["name"] == "Shell"
        stored = [r for r in local_provider.get_rules() if r["id"] == rule["id"]]
        actions = format_rule(stored[0])["actions"]
        assert actions["review_status"] == "reviewed"
        assert actions["set_merchant"] == "Shell"
        assert actions["set_category"]["id"] == "cat_002"

    def test_bad_review_status_creates_nothing(self, local_provider):
        before = len(local_provider.get_rules())
        with pytest.raises(ValueError, match="review_status_action"):
            local_provider.create_rule(
                merchant_criteria=[{"operator": "contains", "value": "shell"}],
                review_status_action="done",
            )
        assert len(local_provider.get_rules()) == before
