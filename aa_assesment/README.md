Automatic Payment Reconciliation Using Sales Order Reference
Overview

This module extends Odoo Accounting to automatically reconcile customer payments and bank statement lines with invoices generated from Sales Orders (SO) when a Sales Order reference is detected.

The solution works seamlessly with Odoo’s native reconciliation engine and supports real-world accounting scenarios such as partial payments, multiple invoices per SO, refunds, and bank statement reconciliation.

Business Requirement

In an Odoo accounting environment, payments can be created through:

Journal Entries (Customer Payments)

Bank Statement Lines

If a Sales Order (SO) reference exists in the journal item label / payment reference, the system should:

Automatically identify the related Sales Order

Find the correct customer invoice(s)

Reconcile the payment without manual intervention

Key Features

✔ Automatic SO detection from multiple sources
✔ Supports partial payments
✔ Supports multiple invoices per Sales Order
✔ Supports refunds / credit notes
✔ Works for payments and bank statements
✔ Uses Odoo’s native reconciliation logic
✔ No onchange-based reconciliation
✔ No hardcoded SO formats
✔ No brute-force ORM loops


How It Works
1. Sales Order Reference Detection

The system attempts to extract the SO reference from the following sources (in order):

Payment Flow

payment.ref

Invoice referenced by payment.ref

invoice.invoice_origin

Custom sale_reference_id (if present)

Sales Order linked via invoice lines

Bank Statement Flow

statement_line.payment_ref

Flexible regex patterns are used to support formats like:

(a)SO-202511-6722

(b)SO/2024/001

(c)SO202511

(d)S001

Technical Design
Extended Models
1. account.payment

Hooks into action_post

Triggers auto-reconciliation after payment posting

Never interferes with draft/onchange behavior

2. account.bank.statement.line

Hooks into button_reconcile_bank_statement_line

Adds SO reference to journal item labels

Performs reconciliation after standard bank reconciliation