CREATE TABLE IF NOT EXISTS "transaction" (
    "_id" uuid PRIMARY KEY,
    "amount" numeric(11, 2) NOT NULL,
    "pending" boolean NOT NULL,
    "payee" varchar(255) NOT NULL,
    "date_authorized" date NOT NULL,
    "date" date NOT NULL,
    "spent_from_id" uuid,
    "account_id" uuid NOT NULL,
    "category" varchar(63) [] NOT NULL,
    "location" jsonb NOT NULL,
    "plaid_transaction_id" varchar(127) NOT NULL
);
