"""update_recurring / mark_as_not_recurring against Monarch's stream model.

Verified live: recurrence settings are edited only through the merchant
(`updateMerchant`), and when a merchant has several streams the edit can land
on a different stream than the one the merchant reports or the mutation
returns. Removal (`markStreamAsNotRecurring`) is per-stream. These tests drive
the real SDK functions with a client that simulates that behavior (network
I/O is the only stand-in).
"""

import asyncio

import pytest

from monarch.recurring import StreamNotEditableError, mark_as_not_recurring, update_recurring

MERCHANT = {"id": "m1", "name": "Streaming Co"}


class SimulatedMonarch:
    """Answers GraphQL calls from in-memory streams and records what was sent.

    ``reported`` is the stream merchant(id) and the mutation response report;
    ``edit_lands_on`` is the stream updateMerchant actually changes.
    """

    def __init__(self, stream_ids, reported, edit_lands_on=None):
        self.streams = {
            sid: {"id": sid, "amount": -10.0, "frequency": "monthly", "baseDate": "2026-01-01",
                  "merchant": dict(MERCHANT)}
            for sid in stream_ids
        }
        self.reported = reported
        self.edit_lands_on = edit_lands_on or reported
        self.calls = []

    async def _request(self, query, variables=None):
        self.calls.append((query, variables or {}))
        if "recurringTransactionStreams" in query:
            return {"recurringTransactionStreams": [{"stream": dict(s)} for s in self.streams.values()]}
        if "merchant(id:" in query:
            return {"merchant": {**MERCHANT, "recurringTransactionStream": {
                **self._public(self.reported), "isActive": True}}}
        if "updateMerchant" in query:
            rec = variables["input"]["recurrence"]
            if self.edit_lands_on in self.streams:
                self.streams[self.edit_lands_on].update(amount=rec["amount"], frequency=rec["frequency"])
            return {"updateMerchant": {"merchant": {**MERCHANT, "recurringTransactionStream": {
                **self._public(self.reported), "isActive": rec["isActive"]}}}}
        if "markStreamAsNotRecurring" in query:
            self.streams.pop(variables["streamId"], None)
            return {"markStreamAsNotRecurring": {"success": True}}
        raise AssertionError(f"unexpected query: {query[:60]}")

    def _public(self, sid):
        s = self.streams.get(sid, {"id": sid, "amount": -10.0, "frequency": "monthly", "baseDate": "2026-01-01"})
        return {k: s[k] for k in ("id", "amount", "frequency", "baseDate")}

    def mutations(self):
        return [q for q, _ in self.calls if q.lstrip().startswith("mutation")]


def run(coro):
    return asyncio.run(coro)


def test_single_stream_merchant_updates_and_verifies_the_stream():
    monarch = SimulatedMonarch(["s1"], reported="s1")
    result = run(update_recurring(monarch, "s1", status="inactive", amount=-12.0, frequency="biweekly"))
    assert result["recurringTransactionStream"]["isActive"] is False
    assert monarch.streams["s1"]["amount"] == -12.0 and monarch.streams["s1"]["frequency"] == "biweekly"
    assert len(monarch.mutations()) == 1


@pytest.mark.parametrize("requested", ["s1", "s2"], ids=["reported-stream", "other-stream"])
def test_multi_stream_merchant_refuses_edits_and_sends_nothing(requested):
    monarch = SimulatedMonarch(["s1", "s2", "s3"], reported="s1")
    with pytest.raises(StreamNotEditableError) as exc:
        run(update_recurring(monarch, requested, status="inactive"))
    assert "3 recurring streams" in str(exc.value) and "status='removed'" in str(exc.value)
    assert monarch.mutations() == []


def test_edit_landing_on_another_stream_is_detected_not_reported_as_success():
    # The live case: merchant reports s1 (and the response says s1) but the
    # edit changes s9. With a single listed stream s1 the re-read catches it.
    monarch = SimulatedMonarch(["s1"], reported="s1", edit_lands_on="s9")
    with pytest.raises(StreamNotEditableError, match="does not show the new amount"):
        run(update_recurring(monarch, "s1", amount=-5.0))


def test_merchant_reporting_a_different_stream_is_refused():
    monarch = SimulatedMonarch(["s1"], reported="s7")
    with pytest.raises(StreamNotEditableError, match="reports stream s7"):
        run(update_recurring(monarch, "s1", amount=-5.0))
    assert monarch.mutations() == []


def test_removing_duplicates_then_editing_the_last_stream():
    monarch = SimulatedMonarch(["s1", "s2"], reported="s1")
    assert run(update_recurring(monarch, "s2", status="removed")) == {"success": True}
    assert set(monarch.streams) == {"s1"}  # only the requested stream removed
    run(update_recurring(monarch, "s1", amount=-11.0))
    assert monarch.streams["s1"]["amount"] == -11.0


def test_removed_targets_exactly_the_requested_stream():
    monarch = SimulatedMonarch(["s1", "s2"], reported="s1")
    run(update_recurring(monarch, "s2", status="removed"))
    [(_, variables)] = [c for c in monarch.calls if "markStreamAsNotRecurring" in c[0]]
    assert variables == {"streamId": "s2"}
    assert not any("updateMerchant" in q for q, _ in monarch.calls)


def test_mark_as_not_recurring_sends_the_stream_id():
    monarch = SimulatedMonarch(["s5"], reported="s5")
    assert run(mark_as_not_recurring(monarch, "s5")) == {"success": True}
    assert monarch.calls[-1][1] == {"streamId": "s5"}


def test_unknown_or_liability_stream_raises():
    monarch = SimulatedMonarch(["s1"], reported="s1")
    monarch.streams["liab"] = {"id": "liab", "amount": 0, "frequency": "monthly", "baseDate": None, "merchant": None}
    for sid in ("nope", "liab"):
        with pytest.raises(ValueError, match="not found or has no merchant"):
            run(update_recurring(monarch, sid, amount=-1.0))
