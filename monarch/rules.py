"""Transaction rule operations."""

from typing import Any, Optional

from .queries import (
    TRANSACTION_RULES_QUERY,
    CREATE_TRANSACTION_RULE_MUTATION,
    DELETE_TRANSACTION_RULE_MUTATION,
)


async def get_rules(client) -> list[dict]:
    """Get all transaction rules."""
    data = await client._request(TRANSACTION_RULES_QUERY)
    return data.get("transactionRules", [])


def format_rule(rule: dict) -> dict:
    """Format a rule into a simplified representation."""
    result: dict[str, Any] = {
        "id": rule["id"],
        "order": rule.get("order"),
    }

    # Criteria (when to apply)
    criteria = {}

    merchant_criteria = rule.get("merchantCriteria")
    if merchant_criteria:
        criteria["merchant"] = [
            {"operator": c["operator"], "value": c["value"]}
            for c in merchant_criteria
        ]
        if rule.get("merchantCriteriaUseOriginalStatement"):
            criteria["merchant_uses_original_statement"] = True

    original_stmt = rule.get("originalStatementCriteria")
    if original_stmt:
        criteria["original_statement"] = [
            {"operator": c["operator"], "value": c["value"]}
            for c in original_stmt
        ]

    merchant_name = rule.get("merchantNameCriteria")
    if merchant_name:
        criteria["merchant_name"] = [
            {"operator": c["operator"], "value": c["value"]}
            for c in merchant_name
        ]

    amount = rule.get("amountCriteria")
    if amount:
        ac: dict[str, Any] = {
            "operator": amount["operator"],
            "is_expense": amount["isExpense"],
        }
        if amount.get("value") is not None:
            ac["value"] = amount["value"]
        if amount.get("valueRange"):
            ac["range"] = {
                "lower": amount["valueRange"]["lower"],
                "upper": amount["valueRange"]["upper"],
            }
        criteria["amount"] = ac

    if rule.get("accountIds"):
        criteria["account_ids"] = rule["accountIds"]
        accounts = rule.get("accounts") or []
        if accounts:
            criteria["accounts"] = [
                {"id": a["id"], "name": a["displayName"]} for a in accounts
            ]

    if rule.get("categoryIds"):
        criteria["category_ids"] = rule["categoryIds"]
        categories = rule.get("categories") or []
        if categories:
            criteria["categories"] = [
                {"id": c["id"], "name": c["name"]} for c in categories
            ]

    result["criteria"] = criteria

    # Actions (what to do)
    actions = {}

    set_merchant = rule.get("setMerchantAction")
    if set_merchant:
        actions["set_merchant"] = set_merchant["name"]

    set_category = rule.get("setCategoryAction")
    if set_category:
        actions["set_category"] = {
            "id": set_category["id"],
            "name": set_category["name"],
        }

    tags = rule.get("addTagsAction")
    if tags:
        actions["add_tags"] = [{"id": t["id"], "name": t["name"]} for t in tags]

    goal = rule.get("linkGoalAction")
    if goal:
        actions["link_goal"] = {"id": goal["id"], "name": goal["name"]}

    if rule.get("reviewStatusAction"):
        actions["review_status"] = rule["reviewStatusAction"]

    if rule.get("setHideFromReportsAction"):
        actions["hide_from_reports"] = True

    if rule.get("sendNotificationAction"):
        actions["send_notification"] = True

    split = rule.get("splitTransactionsAction")
    if split:
        actions["split"] = {
            "amount_type": split.get("amountType"),
            "splits": split.get("splitsInfo", []),
        }

    result["actions"] = actions

    # Stats
    result["recent_application_count"] = rule.get("recentApplicationCount", 0)
    result["last_applied_at"] = rule.get("lastAppliedAt")

    return result


async def create_rule(
    client,
    *,
    merchant_criteria: Optional[list[dict]] = None,
    original_statement_criteria: Optional[list[dict]] = None,
    merchant_name_criteria: Optional[list[dict]] = None,
    amount_criteria: Optional[dict] = None,
    account_ids: Optional[list[str]] = None,
    category_ids: Optional[list[str]] = None,
    set_merchant_action: Optional[str] = None,
    set_category_action: Optional[str] = None,
    add_tags_action: Optional[list[str]] = None,
    review_status_action: Optional[str] = None,
    set_hide_from_reports: Optional[bool] = None,
    apply_to_existing: bool = False,
) -> dict:
    """Create a new transaction rule.

    Args:
        merchant_criteria: List of {operator, value} for merchant matching.
            Operators: "contains", "eq".
        original_statement_criteria: List of {operator, value} for original
            statement matching. Operators: "contains", "eq".
        merchant_name_criteria: List of {operator, value} for merchant name.
        amount_criteria: {operator, is_expense, value} or
            {operator, is_expense, range: {lower, upper}}.
            Operators: "gt", "lt", "eq".
        account_ids: Limit rule to specific accounts.
        category_ids: Limit rule to specific categories.
        set_merchant_action: Merchant name to set (string, not ID).
        set_category_action: Category ID to set.
        add_tags_action: List of tag IDs to add.
        review_status_action: Review status to set.
        set_hide_from_reports: Hide matching transactions from reports.
        apply_to_existing: Apply rule to existing transactions.
    """
    input_data: dict[str, Any] = {
        "merchantCriteria": merchant_criteria,
        "originalStatementCriteria": original_statement_criteria,
        "merchantNameCriteria": merchant_name_criteria,
        "merchantCriteriaUseOriginalStatement": False,
        "accountIds": account_ids,
        "categoryIds": category_ids,
        "setMerchantAction": set_merchant_action,
        "setCategoryAction": set_category_action,
        "addTagsAction": add_tags_action,
        "reviewStatusAction": review_status_action,
        "linkGoalAction": None,
        "linkSavingsGoalAction": None,
        "splitTransactionsAction": None,
        "actionSetBusinessEntity": None,
        "actionSetBusinessEntityIsUnassigned": False,
        "applyToExistingTransactions": apply_to_existing,
    }

    if amount_criteria:
        ac: dict[str, Any] = {
            "operator": amount_criteria["operator"],
            "isExpense": amount_criteria["is_expense"],
        }
        if "value" in amount_criteria:
            ac["value"] = amount_criteria["value"]
        if "range" in amount_criteria:
            ac["valueRange"] = amount_criteria["range"]
        input_data["amountCriteria"] = ac
    else:
        input_data["amountCriteria"] = None

    if set_hide_from_reports is not None:
        input_data["setHideFromReportsAction"] = set_hide_from_reports

    data = await client._request(
        CREATE_TRANSACTION_RULE_MUTATION, {"input": input_data}
    )
    result = data.get("createTransactionRuleV2", {})
    if result.get("errors"):
        errors = result["errors"]
        msg = errors.get("message") or str(errors.get("fieldErrors", []))
        from .client import APIError
        raise APIError(f"Create rule failed: {msg}")
    return {"success": True}


async def delete_rule(client, rule_id: str) -> dict:
    """Delete a transaction rule by ID."""
    data = await client._request(
        DELETE_TRANSACTION_RULE_MUTATION, {"id": rule_id}
    )
    result = data.get("deleteTransactionRule", {})
    if result.get("errors"):
        errors = result["errors"]
        msg = errors[0].get("message") if isinstance(errors, list) and errors else str(errors)
        from .client import APIError
        raise APIError(f"Delete rule failed: {msg}")
    return {"success": result.get("success", False)}
