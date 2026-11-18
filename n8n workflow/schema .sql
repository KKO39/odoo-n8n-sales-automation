-- ============================================================================
--  AI ERP Assistant - Shopping Cart  |  COMPLETE SETUP (schema + cleanup)
--
--  One file does everything:
--    1) creates the 4 tables if they do not exist
--    2) upgrades older / partly-different tables (adds missing columns, ids -> BIGINT,
--       removes the old telegram_id design that blocks inserts)
--    3) CLEANS unfinished test carts and duplicate rows
--    4) creates the unique constraints / indexes the workflow needs
--    5) prints a verification table (everything must say OK)
--
--  Safe to run more than once. Runs inside one transaction: if anything fails,
--  nothing is changed.
--
--  WHAT THE CLEANUP (step 3) DELETES
--    - carts that were never submitted  (status: cart / checkout / submitting)
--    - their items, and the pending "awaiting" state of every customer
--    - duplicate rows that would block the unique indexes
--  Submitted / closed orders and the product_cache are NOT touched.
--  Do not want the cleanup?  Delete or comment out the block marked STEP 3.
--
--  Tables
--    pending_orders       one row per order      (status: cart > checkout > submitting > submitted)
--    pending_order_items  products inside an order (linked by order_id)
--    pending_order        one row per customer: what the bot is waiting for
--                         (awaiting) + the quotation waiting for confirmation
--    product_cache        product list cached when the bot lists / searches products
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- STEP 1  Tables
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pending_order (
    telegram_id      BIGINT PRIMARY KEY,
    partner_id       INTEGER,
    delivery_address TEXT,
    status           TEXT NOT NULL DEFAULT 'cart',
    awaiting         TEXT,
    quotation_id     INTEGER,
    quotation_name   TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pending_orders (
    id               SERIAL PRIMARY KEY,
    chat_id          BIGINT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'cart',
    delivery_address TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pending_order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER REFERENCES pending_orders (id) ON DELETE CASCADE,
    product_id   INTEGER NOT NULL,
    product_name TEXT,
    quantity     NUMERIC NOT NULL DEFAULT 1,
    price        NUMERIC NOT NULL DEFAULT 0,
    subtotal     NUMERIC NOT NULL DEFAULT 0,
    currency     TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS product_cache (
    product_id INTEGER PRIMARY KEY,
    name       TEXT,
    code       TEXT,
    price      NUMERIC DEFAULT 0,
    currency   TEXT,
    stock      NUMERIC,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- STEP 2  Upgrade tables that already existed in an older shape
-- ----------------------------------------------------------------------------
-- pending_order
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS partner_id       INTEGER;
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS delivery_address TEXT;
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS status           TEXT NOT NULL DEFAULT 'cart';
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS awaiting         TEXT;
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS quotation_id     INTEGER;
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS quotation_name   TEXT;
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS created_at       TIMESTAMPTZ DEFAULT now();
ALTER TABLE pending_order ADD COLUMN IF NOT EXISTS updated_at       TIMESTAMPTZ DEFAULT now();

-- pending_orders
ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS status           TEXT NOT NULL DEFAULT 'cart';
ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS delivery_address TEXT;
ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS created_at       TIMESTAMPTZ DEFAULT now();
ALTER TABLE pending_orders ADD COLUMN IF NOT EXISTS updated_at       TIMESTAMPTZ DEFAULT now();

-- pending_order_items
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS order_id     INTEGER;
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS product_name TEXT;
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS quantity     NUMERIC NOT NULL DEFAULT 1;
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS price        NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS subtotal     NUMERIC NOT NULL DEFAULT 0;
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS currency     TEXT;
ALTER TABLE pending_order_items ADD COLUMN IF NOT EXISTS created_at   TIMESTAMPTZ DEFAULT now();

-- product_cache
ALTER TABLE product_cache ADD COLUMN IF NOT EXISTS code       TEXT;
ALTER TABLE product_cache ADD COLUMN IF NOT EXISTS price      NUMERIC DEFAULT 0;
ALTER TABLE product_cache ADD COLUMN IF NOT EXISTS currency   TEXT;
ALTER TABLE product_cache ADD COLUMN IF NOT EXISTS stock      NUMERIC;
ALTER TABLE product_cache ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Telegram ids are bigger than 2,147,483,647 for newer accounts: keep them BIGINT.
-- (no change / no rewrite when the column already is BIGINT)
ALTER TABLE pending_orders ALTER COLUMN chat_id     TYPE BIGINT;
ALTER TABLE pending_order  ALTER COLUMN telegram_id TYPE BIGINT;

-- Old design had pending_order_items.telegram_id NOT NULL. The workflow links items
-- by order_id and does not fill telegram_id, so that rule would reject every insert.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = current_schema()
                 AND table_name = 'pending_order_items'
                 AND column_name = 'telegram_id') THEN
        ALTER TABLE pending_order_items ALTER COLUMN telegram_id DROP NOT NULL;
    END IF;
END $$;
DROP INDEX IF EXISTS pending_order_items_cart_product_uidx;   -- old (telegram_id, product_id) rule

-- ----------------------------------------------------------------------------
-- STEP 3  CLEANUP  (delete this block if you want to keep unfinished carts)
-- ----------------------------------------------------------------------------
-- items that belong to no order (old design leftovers)
DELETE FROM pending_order_items WHERE order_id IS NULL;

-- unfinished carts and their items (submitted / closed orders are kept)
DELETE FROM pending_order_items
WHERE order_id IN (SELECT id FROM pending_orders
                   WHERE status IN ('cart', 'checkout', 'submitting'));
DELETE FROM pending_orders WHERE status IN ('cart', 'checkout', 'submitting');

-- bot is not waiting for anything from anybody
UPDATE pending_order SET awaiting = NULL;

-- duplicates that would block the unique indexes below
DELETE FROM pending_order a USING pending_order b
WHERE a.telegram_id = b.telegram_id AND a.ctid < b.ctid;

DELETE FROM pending_order_items a USING pending_order_items b
WHERE a.order_id = b.order_id AND a.product_id = b.product_id AND a.id > b.id;

-- ----------------------------------------------------------------------------
-- STEP 4  Constraints and indexes the workflow relies on
-- ----------------------------------------------------------------------------
-- INSERT ... ON CONFLICT (telegram_id)
CREATE UNIQUE INDEX IF NOT EXISTS pending_order_telegram_uidx
    ON pending_order (telegram_id);

-- INSERT ... ON CONFLICT (order_id, product_id): same product twice = quantity + 1
CREATE UNIQUE INDEX IF NOT EXISTS pending_order_items_order_product_uidx
    ON pending_order_items (order_id, product_id);

-- a customer can have only ONE open cart
CREATE UNIQUE INDEX IF NOT EXISTS pending_orders_one_cart_per_chat
    ON pending_orders (chat_id) WHERE status = 'cart';

-- speed
CREATE INDEX IF NOT EXISTS pending_orders_chat_status_idx
    ON pending_orders (chat_id, status);
CREATE INDEX IF NOT EXISTS pending_order_items_order_idx
    ON pending_order_items (order_id);

-- items must belong to a real order (added only if no such link exists yet)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
        WHERE c.contype = 'f'
          AND c.conrelid  = 'pending_order_items'::regclass
          AND c.confrelid = 'pending_orders'::regclass
          AND a.attname   = 'order_id') THEN
        ALTER TABLE pending_order_items
            ADD CONSTRAINT pending_order_items_order_fk
            FOREIGN KEY (order_id) REFERENCES pending_orders (id) ON DELETE CASCADE;
    END IF;
END $$;

COMMIT;

-- ----------------------------------------------------------------------------
-- STEP 5  Verification  (every row must say OK)
-- ----------------------------------------------------------------------------
SELECT t.object,
       CASE WHEN to_regclass(t.object) IS NOT NULL THEN 'OK' ELSE 'MISSING' END AS status
FROM (VALUES
        ('pending_order'),
        ('pending_orders'),
        ('pending_order_items'),
        ('product_cache'),
        ('pending_order_telegram_uidx'),
        ('pending_order_items_order_product_uidx'),
        ('pending_orders_one_cart_per_chat')
     ) AS t (object);
