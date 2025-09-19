# CricAlgo Product Requirements Analysis

## Read Summary (≤ 400 words)

**Product Overview:**
CricAlgo is a Telegram-based cricket prediction platform that enables users to participate in paid contests by predicting match outcomes. The platform operates on a three-bucket wallet system (deposit, winning, bonus balances) and uses USDT (BEP20) as the primary currency.

**Core Flows:**

1. **Registration:** Users register via Telegram using their telegram_id and username. The system automatically creates a wallet with three balance buckets upon registration.

2. **Deposit:** Users submit transaction hashes for USDT deposits on BEP20 chain. Admins manually verify and approve deposits, which are credited to the deposit_balance bucket.

3. **Join Contests:** Users join contests by paying entry fees, which are debited from wallet buckets in priority order (deposit → bonus → winning). Each contest has a unique code, entry fee, and prize structure.

4. **Payouts:** After match completion, winnings are calculated based on the contest's prize structure and credited to users' winning_balance bucket.

5. **Withdraw:** Users request withdrawals to external USDT addresses. Admins process these requests and send USDT to the specified address.

**Wallet Behavior:**
- Three-bucket system: deposit_balance (user funds), winning_balance (contest winnings), bonus_balance (promotional funds)
- Debit priority: deposit → bonus → winning when joining contests
- All balance movements are logged in the transactions table
- Non-negative balance constraints enforced

**Admin Responsibilities:**
- Verify and approve/reject deposit requests
- Process withdrawal requests and send USDT
- Create and manage contests with custom prize structures
- Monitor user accounts and handle disputes
- Generate invitation codes for user acquisition

## Assumptions List (explicit)

- **Deposit Chain:** All deposits use BEP20 (Binance Smart Chain) for USDT. (must confirm)
- **Manual Verification:** All deposits require manual admin verification before crediting. (must confirm)
- **Withdrawal Processing:** Withdrawals are processed manually by admins within 24-48 hours. (must confirm)
- **Contest Entry:** Users can only join contests before the join_cutoff timestamp. (must confirm)
- **Prize Structure:** Prize distribution is calculated based on the JSONB prize_structure field. (must confirm)
- **Commission:** Platform takes a percentage commission from each contest (commission_pct field). (must confirm)
- **Invitation System:** Users need invitation codes to register (enabled by default). (must confirm)
- **TOTP Security:** Admin accounts support TOTP 2FA for enhanced security. (must confirm)
- **Transaction Logging:** All financial movements are logged in the transactions table. (must confirm)
- **Contest Status:** Contests can be scheduled, open, closed, or cancelled. (must confirm)

## Open Questions / Clarifications (prioritized)

1. **Prize Calculation Logic:** How exactly is the prize_structure JSONB field used to calculate winnings? What's the expected format?
2. **Contest Creation Workflow:** What's the process for admins to create contests? How are matches linked to contests?
3. **Deposit Verification Process:** What tools/APIs will admins use to verify BEP20 transactions?
4. **Withdrawal Limits:** Are there minimum/maximum withdrawal limits or daily limits?
5. **Contest Capacity:** How does the max_players field work? What happens when capacity is reached?
6. **User Status Management:** When and why would a user account be frozen or disabled?
7. **Audit Logging:** What specific admin actions need to be logged in the audit_logs table?
8. **Invitation Code Management:** How are invitation codes generated and distributed?
9. **Match Data Source:** How are cricket matches populated in the matches table?
10. **Error Handling:** What happens if a contest is cancelled after users have joined?

## Risks & Legal Note

**Regulatory Risks:**
- **Gambling Regulations:** Cricket prediction contests with monetary prizes may be classified as gambling in many jurisdictions, requiring specific licenses and compliance measures.
- **Cryptocurrency Regulations:** USDT usage may be restricted or require special authorization in certain countries.
- **Financial Services:** Operating a wallet system and processing payments may require money transmitter licenses.

**Recommended Mitigations:**
- **Legal Consultation:** Engage with legal experts familiar with gambling and cryptocurrency regulations in target markets.
- **Geographic Restrictions:** Implement geo-blocking for jurisdictions where the service may be prohibited.
- **Terms of Service:** Create comprehensive terms clearly defining the platform's nature and user responsibilities.
- **Compliance Monitoring:** Implement systems to monitor and report suspicious transactions for AML compliance.
- **Insurance:** Consider obtaining appropriate insurance coverage for financial operations.

## Implementation Checklist (initial)

See `backlog.json` for detailed implementation tasks.

## Acceptance Criteria for Step 2 (repo skeleton)

See `acceptance_step2.md` for specific requirements.
