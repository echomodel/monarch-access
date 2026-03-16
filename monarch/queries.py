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

UPDATE_MERCHANT_MUTATION = """
mutation Common_UpdateMerchant($input: UpdateMerchantInput!) {
    updateMerchant(input: $input) {
        merchant {
            id
            name
            recurringTransactionStream {
                id
                frequency
                amount
                baseDate
                isActive
            }
        }
    }
}
"""

# =============================================================================
# Merchant Queries & Mutations
# =============================================================================

MERCHANT_SEARCH_QUERY = """
query($search: String) {
    merchants(search: $search) {
        id
        name
        logoUrl
        transactionsCount
        canBeDeleted
        createdAt
        recurringTransactionStream {
            id
            frequency
            amount
            baseDate
            isActive
        }
    }
}
"""

GET_MERCHANT_QUERY = """
query Common_GetEditMerchant($merchantId: ID!) {
    merchant(id: $merchantId) {
        id
        name
        logoUrl
        transactionCount
        ruleCount
        canBeDeleted
        hasActiveRecurringStreams
        recurringTransactionStream {
            id
            frequency
            amount
            baseDate
            isActive
        }
    }
}
"""

GET_CLOUDINARY_UPLOAD_INFO_MUTATION = """
mutation Common_GetCloudinaryUploadInfo($input: GetLogoCloudinaryUploadInfoMutationInput!) {
    getCloudinaryUploadInfo(input: $input) {
        info {
            path
            requestParams {
                timestamp
                folder
                signature
                api_key
                upload_preset
            }
        }
    }
}
"""

SET_MERCHANT_LOGO_MUTATION = """
mutation Common_SetMerchantLogo($input: SetMerchantLogoInput!) {
    setMerchantLogo(input: $input) {
        merchant {
            id
            name
            logoUrl
        }
    }
}
"""

# =============================================================================
# Recurring Streams — Full Catalog (includes inactive + credit report liabilities)
# =============================================================================

RECURRING_STREAMS_QUERY = """
query Common_GetRecurringStreams($includeLiabilities: Boolean) {
    recurringTransactionStreams(includePending: true, includeLiabilities: $includeLiabilities) {
        stream {
            id
            name
            frequency
            amount
            isApproximate
            isActive
            recurringType
            reviewStatus
            baseDate
            dayOfTheMonth
            merchant {
                id
                name
            }
            creditReportLiabilityAccount {
                id
                status
                accountType
                reportedDate
                account {
                    id
                    displayName
                    currentBalance
                    displayBalance
                }
            }
        }
    }
}
"""

# =============================================================================
# Aggregated Recurring Items — What the Monarch UI uses for Upcoming/Complete
# Includes both merchant-based AND credit report liability items with
# liabilityStatement (minimumPaymentAmount, paymentsInformation)
# =============================================================================

AGGREGATED_RECURRING_ITEMS_QUERY = """
query Common_GetAggregatedRecurringItems($startDate: Date!, $endDate: Date!, $filters: RecurringTransactionFilter) {
    aggregatedRecurringItems(
        startDate: $startDate
        endDate: $endDate
        groupBy: "status"
        filters: $filters
    ) {
        groups {
            groupBy {
                status
            }
            results {
                stream {
                    id
                    frequency
                    isActive
                    amount
                    isApproximate
                    name
                    logoUrl
                    merchant {
                        id
                        name
                        logoUrl
                    }
                    creditReportLiabilityAccount {
                        id
                        liabilityType
                        account {
                            id
                            displayName
                        }
                    }
                }
                date
                isPast
                isLate
                markedPaidAt
                isCompleted
                transactionId
                amount
                amountDiff
                isAmountDifferentThanOriginal
                creditReportLiabilityStatementId
                category {
                    id
                    name
                }
                account {
                    id
                    displayName
                }
                liabilityStatement {
                    id
                    minimumPaymentAmount
                    paymentsInformation {
                        status
                        remainingBalance
                        transactions {
                            id
                            amount
                            date
                            category {
                                id
                                name
                            }
                        }
                    }
                }
            }
            summary {
                expense {
                    total
                }
                creditCard {
                    total
                }
                income {
                    total
                }
            }
        }
        aggregatedSummary {
            expense {
                completed
                remaining
                total
                count
                pendingAmountCount
            }
            creditCard {
                completed
                remaining
                total
                count
                pendingAmountCount
            }
            income {
                completed
                remaining
                total
            }
        }
    }
}
"""

# =============================================================================
# Recurring Stream Mutations
# =============================================================================

MARK_AS_NOT_RECURRING_MUTATION = """
mutation Common_MarkAsNotRecurring($streamId: ID!) {
    markStreamAsNotRecurring(streamId: $streamId) {
        success
    }
}
"""

RECURRING_TRANSACTION_ITEMS_QUERY = """
query Web_GetUpcomingRecurringTransactionItems($startDate: Date!, $endDate: Date!, $filters: RecurringTransactionFilter) {
  recurringTransactionItems(
    startDate: $startDate
    endDate: $endDate
    filters: $filters
  ) {
    stream {
      id
      frequency
      amount
      isApproximate
      merchant {
        id
        name
        logoUrl
      }
    }
    date
    isPast
    transactionId
    amount
    amountDiff
    category {
      id
      name
    }
    account {
      id
      displayName
      logoUrl
    }
  }
}
"""
