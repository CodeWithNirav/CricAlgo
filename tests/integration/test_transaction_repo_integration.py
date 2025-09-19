"""
Integration tests for transaction repository operations

These tests verify the transaction repository's CRUD operations,
querying capabilities, and integration with the database layer.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.repos.transaction_repo import (
    create_transaction,
    get_transaction_by_id,
    get_transactions_by_user,
    get_transactions_by_type,
    update_transaction_metadata
)
from app.repos.user_repo import create_user
from app.models.enums import UserStatus
from tests.fixtures.database import create_test_user_with_wallet


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_creation_and_retrieval(async_session):
    """Test transaction creation and retrieval operations."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="txuser",
        status=UserStatus.ACTIVE
    )
    
    # Create transaction
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        related_entity="deposit_request",
        related_id=uuid4(),
        tx_metadata={"tx_hash": "0x1234567890abcdef", "confirmations": 12}
    )
    
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.user_id == user.id
    assert transaction.tx_type == "deposit"
    assert transaction.amount == Decimal('100.00')
    assert transaction.currency == "USDT"
    assert transaction.related_entity == "deposit_request"
    assert transaction.tx_metadata["tx_hash"] == "0x1234567890abcdef"
    assert transaction.tx_metadata["confirmations"] == 12
    
    # Retrieve transaction by ID
    retrieved_tx = await get_transaction_by_id(async_session, transaction.id)
    assert retrieved_tx is not None
    assert retrieved_tx.id == transaction.id
    assert retrieved_tx.user_id == user.id
    assert retrieved_tx.tx_type == "deposit"
    assert retrieved_tx.amount == Decimal('100.00')


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_queries_by_user(async_session):
    """Test querying transactions by user."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=67890,
        username="queryuser",
        status=UserStatus.ACTIVE
    )
    
    # Create multiple transactions for user
    transactions = []
    for i in range(5):
        tx = await create_transaction(
            session=async_session,
            user_id=user.id,
            tx_type="deposit",
            amount=Decimal(f'{100 + i * 10}.00'),
            currency="USDT",
            tx_metadata={"tx_hash": f"0x{i:064x}"}
        )
        transactions.append(tx)
    
    # Query transactions by user
    user_transactions = await get_transactions_by_user(
        async_session,
        user.id,
        limit=10
    )
    
    assert len(user_transactions) == 5
    assert all(tx.user_id == user.id for tx in user_transactions)
    
    # Verify transactions are ordered by created_at desc
    amounts = [tx.amount for tx in user_transactions]
    assert amounts == sorted(amounts, reverse=True)
    
    # Test pagination
    first_page = await get_transactions_by_user(
        async_session,
        user.id,
        limit=3,
        offset=0
    )
    
    second_page = await get_transactions_by_user(
        async_session,
        user.id,
        limit=3,
        offset=3
    )
    
    assert len(first_page) == 3
    assert len(second_page) == 2
    assert first_page[0].id != second_page[0].id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_queries_by_type(async_session):
    """Test querying transactions by type."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=11111,
        username="typeuser",
        status=UserStatus.ACTIVE
    )
    
    # Create different types of transactions
    deposit_tx = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT"
    )
    
    withdrawal_tx = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="withdrawal",
        amount=Decimal('50.00'),
        currency="USDT"
    )
    
    contest_entry_tx = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="contest_entry",
        amount=Decimal('10.00'),
        currency="USDT"
    )
    
    # Query deposits only
    deposit_transactions = await get_transactions_by_type(
        async_session,
        "deposit",
        limit=10
    )
    
    assert len(deposit_transactions) == 1
    assert deposit_transactions[0].id == deposit_tx.id
    assert deposit_transactions[0].tx_type == "deposit"
    
    # Query withdrawals only
    withdrawal_transactions = await get_transactions_by_type(
        async_session,
        "withdrawal",
        limit=10
    )
    
    assert len(withdrawal_transactions) == 1
    assert withdrawal_transactions[0].id == withdrawal_tx.id
    assert withdrawal_transactions[0].tx_type == "withdrawal"
    
    # Query contest entries only
    contest_transactions = await get_transactions_by_type(
        async_session,
        "contest_entry",
        limit=10
    )
    
    assert len(contest_transactions) == 1
    assert contest_transactions[0].id == contest_entry_tx.id
    assert contest_transactions[0].tx_type == "contest_entry"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_metadata_update(async_session):
    """Test updating transaction metadata."""
    # Create user and transaction
    user = await create_user(
        session=async_session,
        telegram_id=22222,
        username="metadatauser",
        status=UserStatus.ACTIVE
    )
    
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        tx_metadata={"tx_hash": "0x1234567890abcdef", "confirmations": 0}
    )
    
    # Update metadata
    new_metadata = {
        "tx_hash": "0x1234567890abcdef",
        "confirmations": 12,
        "block_number": 12345678,
        "gas_used": 21000
    }
    
    updated_tx = await update_transaction_metadata(
        async_session,
        transaction.id,
        new_metadata
    )
    
    assert updated_tx is not None
    assert updated_tx.id == transaction.id
    assert updated_tx.tx_metadata == new_metadata
    assert updated_tx.tx_metadata["confirmations"] == 12
    assert updated_tx.tx_metadata["block_number"] == 12345678
    
    # Verify update persisted
    retrieved_tx = await get_transaction_by_id(async_session, transaction.id)
    assert retrieved_tx.tx_metadata == new_metadata


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_with_related_entity(async_session):
    """Test transaction creation with related entity."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=33333,
        username="relateduser",
        status=UserStatus.ACTIVE
    )
    
    related_id = uuid4()
    
    # Create transaction with related entity
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="contest_entry",
        amount=Decimal('25.00'),
        currency="USDT",
        related_entity="contest",
        related_id=related_id,
        tx_metadata={"contest_id": str(related_id)}
    )
    
    assert transaction.related_entity == "contest"
    assert transaction.related_id == related_id
    assert transaction.tx_metadata["contest_id"] == str(related_id)
    
    # Retrieve and verify
    retrieved_tx = await get_transaction_by_id(async_session, transaction.id)
    assert retrieved_tx.related_entity == "contest"
    assert retrieved_tx.related_id == related_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_without_user(async_session):
    """Test transaction creation without user (system transaction)."""
    # Create transaction without user_id
    transaction = await create_transaction(
        session=async_session,
        user_id=None,
        tx_type="system_fee",
        amount=Decimal('1.00'),
        currency="USDT",
        tx_metadata={"description": "System maintenance fee"}
    )
    
    assert transaction is not None
    assert transaction.user_id is None
    assert transaction.tx_type == "system_fee"
    assert transaction.amount == Decimal('1.00')
    
    # Query system transactions
    system_transactions = await get_transactions_by_type(
        async_session,
        "system_fee",
        limit=10
    )
    
    assert len(system_transactions) == 1
    assert system_transactions[0].id == transaction.id
    assert system_transactions[0].user_id is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_currency_handling(async_session):
    """Test transaction creation with different currencies."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=44444,
        username="currencyuser",
        status=UserStatus.ACTIVE
    )
    
    # Create transactions with different currencies
    usdt_tx = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT"
    )
    
    btc_tx = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('0.001'),
        currency="BTC"
    )
    
    eth_tx = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('0.1'),
        currency="ETH"
    )
    
    # Verify currencies
    assert usdt_tx.currency == "USDT"
    assert btc_tx.currency == "BTC"
    assert eth_tx.currency == "ETH"
    
    # Query by currency (if implemented)
    user_transactions = await get_transactions_by_user(async_session, user.id)
    currencies = {tx.currency for tx in user_transactions}
    assert currencies == {"USDT", "BTC", "ETH"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_large_amounts(async_session):
    """Test transaction creation with large amounts."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=55555,
        username="largeuser",
        status=UserStatus.ACTIVE
    )
    
    # Create transaction with large amount
    large_amount = Decimal('999999999.99999999')  # 30 digits, 8 decimal places
    
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=large_amount,
        currency="USDT"
    )
    
    assert transaction.amount == large_amount
    
    # Verify precision is maintained
    retrieved_tx = await get_transaction_by_id(async_session, transaction.id)
    assert retrieved_tx.amount == large_amount


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_metadata_complex_types(async_session):
    """Test transaction creation with complex metadata types."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=66666,
        username="complexuser",
        status=UserStatus.ACTIVE
    )
    
    # Create transaction with complex metadata
    complex_metadata = {
        "tx_hash": "0x1234567890abcdef",
        "confirmations": 12,
        "block_number": 12345678,
        "gas_used": 21000,
        "gas_price": "20000000000",
        "from_address": "0xabcdef1234567890",
        "to_address": "0x9876543210fedcba",
        "logs": [
            {"address": "0x123", "topics": ["0x456"], "data": "0x789"},
            {"address": "0xabc", "topics": ["0xdef"], "data": "0x012"}
        ],
        "nested": {
            "level1": {
                "level2": "value",
                "array": [1, 2, 3, "string"]
            }
        }
    }
    
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        tx_metadata=complex_metadata
    )
    
    assert transaction.tx_metadata == complex_metadata
    
    # Verify complex data is preserved
    retrieved_tx = await get_transaction_by_id(async_session, transaction.id)
    assert retrieved_tx.tx_metadata["logs"] == complex_metadata["logs"]
    assert retrieved_tx.tx_metadata["nested"]["level1"]["array"] == [1, 2, 3, "string"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transaction_not_found_handling(async_session):
    """Test handling when transaction doesn't exist."""
    fake_tx_id = uuid4()
    
    # Try to get non-existent transaction
    transaction = await get_transaction_by_id(async_session, fake_tx_id)
    assert transaction is None
    
    # Try to update non-existent transaction
    updated_tx = await update_transaction_metadata(
        async_session,
        fake_tx_id,
        {"test": "data"}
    )
    assert updated_tx is None
