from odoo import models
import re
import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _extract_so_reference(self, text):
        """Extract Sales Order reference from text"""
        if not text:
            return None
        
        # Universal patterns for SO detection
        patterns = [
            r'SO[-/]?\d+[-/]?\d*[-/]?\d*',  # SO-202511-6722, SO/2024/001
            r'S[-/]?\d+[-/]?\d*',            # S001
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None

    def action_post(self):
        """Override post to trigger reconciliation"""
        res = super(AccountPayment, self).action_post()
        
        for payment in self:
            if payment.partner_type == 'customer' and payment.state == 'posted':
                _logger.info("="*70)
                _logger.info(f"🔄 AUTO-RECONCILIATION: Processing payment {payment.name}")
                _logger.info("="*70)
                try:
                    self._auto_reconcile_with_sales_order(payment)
                except Exception as e:
                    _logger.error(f"Auto-reconciliation error: {str(e)}", exc_info=True)
        
        return res

    def _auto_reconcile_with_sales_order(self, payment):
        """Main reconciliation logic"""
        if not payment.move_id:
            _logger.info("No journal entry found")
            return

        so_reference = None
        
        # STEP 1: Check payment fields for SO reference
        _logger.info("STEP 1: Checking payment fields")
        _logger.info(f"  payment.ref: '{payment.ref}'")
        
        if payment.ref:
            so_reference = self._extract_so_reference(payment.ref)
            if so_reference:
                _logger.info(f"Found SO in payment.ref: {so_reference}")

        # STEP 2: If no SO, find it from invoice
        if not so_reference:
            _logger.info("STEP 2: No SO in payment, searching invoice")
            
            invoice = None
            
            # Method 1: Get invoice from payment reference (INV/2026/00004)
            if payment.ref and payment.ref.startswith('INV'):
                invoice = self.env['account.move'].search([
                    ('name', '=', payment.ref),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                ], limit=1)
                if invoice:
                    _logger.info(f"Found invoice by ref: {invoice.name}")
            
            # Method 2: Match by partner and amount
            if not invoice:
                _logger.info(f"Searching by partner={payment.partner_id.name}, amount={payment.amount}")
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', payment.partner_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                ], order='date desc', limit=5)
                
                _logger.info(f"Found {len(invoices)} candidate invoices")
                for inv in invoices:
                    _logger.info(f"    - {inv.name}: amount_total={inv.amount_total}, residual={inv.amount_residual}")
                    if abs(inv.amount_residual - payment.amount) < 0.01:
                        invoice = inv
                        _logger.info(f"Matched by amount: {invoice.name}")
                        break
            
            # Extract SO from invoice
            if invoice:
                _logger.info(f"Extracting SO from invoice {invoice.name}")
                
                # Method A: Check invoice_origin
                if invoice.invoice_origin:
                    _logger.info(f"    invoice_origin: '{invoice.invoice_origin}'")
                    so_reference = self._extract_so_reference(invoice.invoice_origin)
                    if so_reference:
                        _logger.info(f"Found SO in invoice_origin: {so_reference}")
                
                # Method B: Check sale_reference_id (your custom field)
                if not so_reference and hasattr(invoice, 'sale_reference_id') and invoice.sale_reference_id:
                    sale_ref_name = invoice.sale_reference_id.name if hasattr(invoice.sale_reference_id, 'name') else str(invoice.sale_reference_id)
                    _logger.info(f"    sale_reference_id: '{sale_ref_name}'")
                    so_reference = self._extract_so_reference(sale_ref_name)
                    if so_reference:
                        _logger.info(f"Found SO in sale_reference_id: {so_reference}")
                
                # Method C: Get from invoice lines
                if not so_reference:
                    sale_orders = invoice.invoice_line_ids.mapped('sale_line_ids.order_id')
                    if sale_orders:
                        so_reference = sale_orders[0].name
                        _logger.info(f"Found SO from invoice lines: {so_reference}")
            else:
                _logger.info("No matching invoice found")

        # STEP 3: If still no SO, exit
        if not so_reference:
            _logger.info("="*70)
            _logger.info(f"No SO reference found for payment {payment.name}")
            _logger.info("  To enable auto-reconciliation:")
            _logger.info("  1. Include SO number in payment memo, OR")
            _logger.info("  2. Ensure payment amount matches an unpaid invoice")
            _logger.info("="*70)
            return

        # STEP 4: Find Sales Order
        _logger.info("STEP 3: Finding Sales Order")
        _logger.info(f"  Searching for: {so_reference}")
        
        sale_order = self.env['sale.order'].search([
            '|',
            ('name', '=', so_reference),
            ('name', 'ilike', so_reference)
        ], limit=1)

        if not sale_order:
            # Try without dashes/slashes
            numbers_only = re.sub(r'[^\d]', '', so_reference)
            if numbers_only:
                sale_order = self.env['sale.order'].search([
                    ('name', 'ilike', numbers_only)
                ], limit=1)

        if not sale_order:
            _logger.warning(f"Sales Order '{so_reference}' not found in system")
            return

        _logger.info(f"Found SO: {sale_order.name} (ID: {sale_order.id})")

        # STEP 5: Get unpaid invoices
        _logger.info("STEP 4: Finding unpaid invoices")
        
        invoices = sale_order.invoice_ids.filtered(
            lambda inv: inv.state == 'posted' 
            and inv.move_type in ('out_invoice', 'out_refund')
            and inv.payment_state in ('not_paid', 'partial')
        )

        if not invoices:
            _logger.info(f"No unpaid invoices for SO {sale_order.name}")
            _logger.info(f"All invoices: {sale_order.invoice_ids.mapped('name')}")
            _logger.info(f"States: {sale_order.invoice_ids.mapped('payment_state')}")
            return

        _logger.info(f"Found {len(invoices)} unpaid invoice(s):")
        for inv in invoices:
            _logger.info(f"   - {inv.name}: residual=${inv.amount_residual}")

        # STEP 6: Prepare reconciliation
        _logger.info("STEP 5: Preparing reconciliation")
        
        payment_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
            and not l.reconciled
            and l.credit > 0
        )

        if not payment_lines:
            _logger.warning("No unreconciled payment lines found")
            _logger.info(f"Payment lines: {payment.move_id.line_ids.mapped('name')}")
            return

        invoice_lines = invoices.mapped('line_ids').filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
            and not l.reconciled
            and l.debit > 0
        )

        if not invoice_lines:
            _logger.info("All invoice lines already reconciled")
            return

        payment_amount = sum(payment_lines.mapped('credit'))
        invoice_amount = sum(invoice_lines.mapped('debit'))
        
        _logger.info(f"Payment: {len(payment_lines)} line(s), total=${payment_amount}")
        _logger.info(f"Invoice: {len(invoice_lines)} line(s), total=${invoice_amount}")

        # STEP 7: Reconcile
        _logger.info("STEP 6: Performing reconciliation")
        
        lines_to_reconcile = payment_lines | invoice_lines

        try:
            lines_to_reconcile.reconcile()
            _logger.info("="*70)
            _logger.info(f"SUCCESS!")
            _logger.info(f"Payment: {payment.name}")
            _logger.info(f"SO: {sale_order.name}")
            _logger.info(f"Invoices: {invoices.mapped('name')}")
            _logger.info("="*70)
        except Exception as e:
            _logger.error(f"Reconciliation failed: {str(e)}")
            # Try partial
            try:
                amount = min(payment_amount, invoice_amount)
                if amount > 0:
                    self.env['account.partial.reconcile'].create({
                        'debit_move_id': invoice_lines[0].id,
                        'credit_move_id': payment_lines[0].id,
                        'amount': amount,
                    })
                    _logger.info(f"Partial reconciliation: ${amount}")
            except Exception as pe:
                _logger.error(f"Partial reconciliation failed: {str(pe)}")


