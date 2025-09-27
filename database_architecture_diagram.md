# CricAlgo Database Architecture

## Visual Database Schema

```mermaid
erDiagram
    USERS {
        uuid id PK
        bigint telegram_id UK
        varchar username UK
        enum status
        timestamp created_at
    }
    
    WALLETS {
        uuid id PK
        uuid user_id FK
        numeric deposit_balance
        numeric winning_balance
        numeric bonus_balance
        numeric held_balance
        timestamp updated_at
    }
    
    ADMINS {
        uuid id PK
        varchar username UK
        text password_hash
        varchar email
        text totp_secret
        timestamp created_at
        timestamp last_login
    }
    
    MATCHES {
        uuid id PK
        varchar external_id
        varchar title
        timestamp start_time
        enum status
        timestamp created_at
    }
    
    CONTESTS {
        uuid id PK
        uuid match_id FK
        varchar code UK
        varchar title
        numeric entry_fee
        varchar currency
        int max_players
        jsonb prize_structure
        numeric commission_pct
        timestamp join_cutoff
        enum status
        timestamp created_at
    }
    
    ENTRIES {
        uuid id PK
        uuid contest_id FK
        uuid user_id FK
        varchar entry_code UK
        numeric amount_debited
        int winner_rank
        timestamp created_at
    }
    
    DEPOSIT_REQUESTS {
        uuid id PK
        uuid user_id FK
        varchar tx_hash UK
        numeric amount
        varchar chain
        enum status
        uuid admin_id FK
        text admin_note
        timestamp created_at
        timestamp processed_at
    }
    
    WITHDRAW_REQUESTS {
        uuid id PK
        uuid user_id FK
        text to_address
        numeric amount
        enum status
        uuid admin_id FK
        varchar admin_tx_hash
        text admin_note
        timestamp created_at
        timestamp processed_at
    }
    
    TRANSACTIONS {
        uuid id PK
        uuid user_id FK
        varchar tx_type
        numeric amount
        varchar currency
        varchar related_entity
        uuid related_id
        jsonb metadata
        timestamp created_at
    }
    
    INVITATION_CODES {
        varchar code PK
        uuid created_by FK
        int max_uses
        int uses
        timestamp expires_at
        boolean enabled
        timestamp created_at
    }
    
    AUDIT_LOGS {
        uuid id PK
        uuid admin_id FK
        varchar action
        jsonb details
        timestamp created_at
    }
    
    CHAT_MAP {
        uuid id PK
        bigint telegram_id
        varchar chat_type
        varchar chat_title
        timestamp created_at
    }

    %% Relationships
    USERS ||--|| WALLETS : "has one"
    USERS ||--o{ ENTRIES : "participates in"
    USERS ||--o{ DEPOSIT_REQUESTS : "requests deposits"
    USERS ||--o{ WITHDRAW_REQUESTS : "requests withdrawals"
    USERS ||--o{ TRANSACTIONS : "has transactions"
    
    ADMINS ||--o{ INVITATION_CODES : "creates"
    ADMINS ||--o{ DEPOSIT_REQUESTS : "processes"
    ADMINS ||--o{ WITHDRAW_REQUESTS : "processes"
    ADMINS ||--o{ AUDIT_LOGS : "performs actions"
    
    MATCHES ||--o{ CONTESTS : "has contests"
    CONTESTS ||--o{ ENTRIES : "has entries"
    
    ENTRIES }o--|| CONTESTS : "belongs to"
    ENTRIES }o--|| USERS : "belongs to"
```

## Key Features

### Core Entities
- **Users**: Telegram-based user accounts with unique telegram_id
- **Wallets**: Three-bucket system (deposit, winning, bonus) + held balance
- **Matches**: Cricket matches with external integration support
- **Contests**: Betting contests linked to matches with flexible prize structures

### Financial System
- **Multi-bucket wallet system** for different balance types
- **Transaction ledger** for complete audit trail
- **Deposit/Withdrawal requests** with admin approval workflow
- **Commission tracking** for platform revenue

### Admin Management
- **Admin accounts** with TOTP support
- **Invitation codes** for user registration control
- **Audit logging** for all admin actions
- **Request processing** for deposits/withdrawals

### Data Integrity
- **Unique constraints** on critical fields
- **Check constraints** for non-negative balances
- **Foreign key relationships** with proper cascading
- **Indexes** on frequently queried fields

## Database Design Principles

1. **UUID Primary Keys**: All entities use UUID for security and scalability
2. **Audit Trail**: Complete transaction history with metadata
3. **Flexible Prize Structure**: JSON-based prize distribution
4. **Multi-currency Support**: USDT as primary with extensibility
5. **Admin Controls**: Comprehensive admin management and audit
6. **Performance**: Strategic indexing for common queries
