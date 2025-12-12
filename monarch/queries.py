"""GraphQL queries for Monarch Money API."""

ACCOUNTS_QUERY = """
query GetAccounts {
  accounts {
    id
    displayName
    syncDisabled
    deactivatedAt
    isHidden
    isAsset
    mask
    createdAt
    updatedAt
    displayLastUpdatedAt
    currentBalance
    displayBalance
    includeInNetWorth
    dataProvider
    isManual
    type { name display }
    subtype { name display }
    credential {
      id
      updateRequired
      disconnectedFromDataProviderAt
      institution { id name status }
    }
    institution { id name }
  }
}
"""

TRANSACTIONS_QUERY = """
query GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput) {
  allTransactions(filters: $filters) {
    totalCount
    results(offset: $offset, limit: $limit) {
      id
      amount
      pending
      date
      hideFromReports
      needsReview
      plaidName
      notes
      isRecurring
      reviewStatus
      isSplitTransaction
      account {
        id
        displayName
      }
      merchant {
        id
        name
        transactionsCount
      }
      category {
        id
        name
      }
      tags {
        id
        name
        color
      }
    }
  }
}
"""

TRANSACTION_CATEGORIES_QUERY = """
query GetTransactionCategories {
  categories {
    id
    name
    icon
    order
    group {
      id
      name
      type
    }
  }
}
"""

UPDATE_TRANSACTION_MUTATION = """
mutation UpdateTransaction($input: UpdateTransactionMutationInput!) {
  updateTransaction(input: $input) {
    transaction {
      id
      amount
      pending
      date
      hideFromReports
      needsReview
      plaidName
      notes
      isRecurring
      isSplitTransaction
      account {
        id
        displayName
      }
      category {
        id
        name
      }
      merchant {
        id
        name
      }
      tags {
        id
        name
        color
      }
    }
    errors {
      fieldErrors {
        field
        messages
      }
      message
      code
    }
  }
}
"""

GET_TRANSACTION_QUERY = """
query GetTransaction($id: UUID!) {
  getTransaction(id: $id) {
    id
    amount
    pending
    date
    hideFromReports
    needsReview
    plaidName
    notes
    isRecurring
    isSplitTransaction
    hasSplitTransactions
    splitTransactions {
      id
      amount
      merchant { id name }
      category { id name }
      notes
    }
    account {
      id
      displayName
    }
    category {
      id
      name
    }
    merchant {
      id
      name
    }
    tags {
      id
      name
      color
    }
  }
}
"""

BULK_UPDATE_TRANSACTIONS_MUTATION = """
mutation BulkUpdateTransactions(
    $selectedTransactionIds: [ID!]!,
    $excludedTransactionIds: [ID!],
    $allSelected: Boolean!,
    $expectedAffectedTransactionCount: Int!,
    $updates: TransactionUpdateParams!,
    $filters: TransactionFilterInput
) {
    bulkUpdateTransactions(
        selectedTransactionIds: $selectedTransactionIds,
        excludedTransactionIds: $excludedTransactionIds,
        updates: $updates,
        allSelected: $allSelected,
        expectedAffectedTransactionCount: $expectedAffectedTransactionCount,
        filters: $filters
    ) {
        success
        affectedCount
        errors {
            message
        }
    }
}
"""

SPLIT_TRANSACTION_MUTATION = """
mutation SplitTransaction($input: UpdateTransactionSplitMutationInput!) {
    updateTransactionSplit(input: $input) {
        transaction {
            id
            amount
            hasSplitTransactions
            splitTransactions {
                id
                amount
                merchant {
                    id
                    name
                }
                category {
                    id
                    name
                }
                notes
            }
        }
        errors {
            fieldErrors {
                field
                messages
            }
            message
            code
        }
    }
}
"""

CREATE_TRANSACTION_MUTATION = """
mutation Common_CreateTransactionMutation($input: CreateTransactionMutationInput!) {
    createTransaction(input: $input) {
        errors {
            fieldErrors {
                field
                messages
            }
            message
            code
        }
        transaction {
            id
            amount
            date
            notes
            account {
                id
                displayName
            }
            category {
                id
                name
            }
            merchant {
                id
                name
            }
        }
    }
}
"""

DELETE_TRANSACTION_MUTATION = """
mutation Common_DeleteTransactionMutation($input: DeleteTransactionMutationInput!) {
    deleteTransaction(input: $input) {
        deleted
        errors {
            fieldErrors {
                field
                messages
            }
            message
            code
        }
    }
}
"""
