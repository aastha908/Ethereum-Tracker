-- =====================================================
-- TRANSACTIONS
-- =====================================================

CREATE TABLE IF NOT EXISTS transactions (

    tx_hash TEXT PRIMARY KEY,

    from_address TEXT,
    to_address TEXT,

    nonce INTEGER,

    value_wei TEXT,

    gas_limit INTEGER,
    gas_price_wei TEXT,

    input_data TEXT,

    first_seen TIMESTAMP,

    current_status TEXT,

    current_block_number INTEGER,
    current_block_hash TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TRANSACTION EVENTS
-- =====================================================

CREATE TABLE IF NOT EXISTS transaction_events (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tx_hash TEXT NOT NULL,

    event_time TIMESTAMP,

    event_type TEXT,

    details TEXT,

    FOREIGN KEY(tx_hash)
    REFERENCES transactions(tx_hash)
);

-- =====================================================
-- BLOCKS
-- =====================================================

CREATE TABLE IF NOT EXISTS blocks (

    block_hash TEXT PRIMARY KEY,

    block_number INTEGER,

    parent_hash TEXT,

    timestamp INTEGER,

    observed_time TIMESTAMP,

    is_canonical INTEGER DEFAULT 1,

    gas_used INTEGER,
    gas_limit INTEGER,
    base_fee_per_gas TEXT,
    transaction_count INTEGER,
    block_size INTEGER,
    is_empty INTEGER DEFAULT 0
);

-- =====================================================
-- RECEIPTS
-- =====================================================

CREATE TABLE IF NOT EXISTS transaction_receipts (

    tx_hash TEXT PRIMARY KEY,

    block_number INTEGER,

    block_hash TEXT,

    transaction_index INTEGER,

    gas_used INTEGER,

    effective_gas_price TEXT,

    status INTEGER,

    contract_address TEXT,

    FOREIGN KEY(tx_hash)
    REFERENCES transactions(tx_hash)
);

-- =====================================================
-- CONFIRMATIONS
-- =====================================================

CREATE TABLE IF NOT EXISTS transaction_confirmations (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tx_hash TEXT,

    block_number INTEGER,

    confirmation_count INTEGER,

    recorded_at TIMESTAMP,

    FOREIGN KEY(tx_hash)
    REFERENCES transactions(tx_hash)
);

-- =====================================================
-- REPLACEMENTS
-- =====================================================

CREATE TABLE IF NOT EXISTS replacements (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    original_tx TEXT,

    replacement_tx TEXT,

    sender TEXT,

    nonce INTEGER,

    detected_time TIMESTAMP
);

-- =====================================================
-- TRACES
-- =====================================================

CREATE TABLE IF NOT EXISTS traces (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tx_hash TEXT,

    trace_address TEXT,

    call_type TEXT,

    from_address TEXT,

    to_address TEXT,

    value_wei TEXT,

    gas INTEGER,

    trace_index INTEGER,

    FOREIGN KEY(tx_hash)
    REFERENCES transactions(tx_hash)
);

-- =====================================================
-- REORGS
-- =====================================================

CREATE TABLE IF NOT EXISTS reorgs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    detected_time TIMESTAMP,

    block_number INTEGER,

    old_block_hash TEXT,

    new_block_hash TEXT,

    reorg_group_id TEXT,
    depth INTEGER
);

-- =====================================================
-- TRANSACTION STATE HISTORY
-- =====================================================

CREATE TABLE IF NOT EXISTS transaction_state_history (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tx_hash TEXT,

    state TEXT,

    block_number INTEGER,

    block_hash TEXT,

    recorded_at TIMESTAMP,

    FOREIGN KEY(tx_hash)
    REFERENCES transactions(tx_hash)
);


CREATE TABLE IF NOT EXISTS monitored_blocks (

    block_hash TEXT PRIMARY KEY,

    block_number INTEGER NOT NULL,

    parent_hash TEXT NOT NULL,

    observed_at TIMESTAMP,

    is_canonical INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS block_transactions (

    block_hash TEXT,
    tx_hash TEXT,

    PRIMARY KEY (
        block_hash,
        tx_hash
    )
);

-- =====================================================
-- CONSENSUS LAYER
-- =====================================================

CREATE TABLE IF NOT EXISTS consensus_slots (

    slot INTEGER PRIMARY KEY,
    epoch INTEGER,
    proposer_index INTEGER,
    block_root TEXT,
    is_missed INTEGER DEFAULT 0,
    recorded_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS epoch_finality (

    epoch INTEGER PRIMARY KEY,
    justified INTEGER DEFAULT 0,
    finalized INTEGER DEFAULT 0,
    recorded_at TIMESTAMP
);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_events_txhash
ON transaction_events(tx_hash);

CREATE INDEX IF NOT EXISTS idx_events_type
ON transaction_events(event_type);

CREATE INDEX IF NOT EXISTS idx_blocks_number
ON blocks(block_number);

CREATE INDEX IF NOT EXISTS idx_receipts_block
ON transaction_receipts(block_number);

CREATE INDEX IF NOT EXISTS idx_confirmations_txhash
ON transaction_confirmations(tx_hash);

CREATE INDEX IF NOT EXISTS idx_traces_txhash
ON traces(tx_hash);

CREATE INDEX IF NOT EXISTS idx_state_history_txhash
ON transaction_state_history(tx_hash);

CREATE INDEX IF NOT EXISTS idx_replacements_sender_nonce
ON replacements(sender, nonce);

CREATE INDEX IF NOT EXISTS idx_monitored_blocks_number
ON monitored_blocks(block_number);