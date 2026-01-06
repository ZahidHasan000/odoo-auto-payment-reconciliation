from odoo import models, api
import re
import logging

_logger = logging.getLogger(__name__)

class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    def _extract_so_reference(self, text):
        """Extract SO reference"""
        if not text:
            return None
        
        patterns = [
            r'SO[-/]?\d+[-/]?\d*[-/]?\d*',
            r'S[-/]?\d+[-/]?\d*',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None

    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        """Add SO reference to move line"""
        vals_list = super()._prepare_move_line_default_vals(counterpart_account_id)
        
        for vals, line in zip(vals_list, self):
            if line.payment_ref:
                so_ref = self._extract_so_reference(line.payment_ref)
                if so_ref and vals and len(vals) > 0:
                    vals[0]['name'] = line.payment_ref
        
        return vals_list

    def button_reconcile_bank_statement_line(self):
        """Trigger SO reconciliation"""
        res = super().button_reconcile_bank_statement_line()
        
        for line in self:
            if not line.is_reconciled and line.payment_ref:
                self._auto_reconcile_with_so(line)
        
        return res

    def _auto_reconcile_with_so(self, statement_line):
        """Auto-reconcile bank statement"""
        so_ref = self._extract_so_reference(statement_line.payment_ref)
        if not so_ref:
            return

        so = self.env['sale.order'].search([
            '|', ('name', '=', so_ref), ('name', 'ilike', so_ref)
        ], limit=1)

        if not so:
            return

        invoices = so.invoice_ids.filtered(
            lambda i: i.state == 'posted' 
            and i.move_type in ('out_invoice', 'out_refund')
            and i.payment_state in ('not_paid', 'partial')
        )

        if not invoices or not statement_line.move_id:
            return

        stmt_lines = statement_line.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
        )

        inv_lines = invoices.mapped('line_ids').filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
        )

        if stmt_lines and inv_lines:
            try:
                (stmt_lines | inv_lines).reconcile()
                _logger.info(f"Bank statement reconciled with SO {so.name}")
            except:
                pass
