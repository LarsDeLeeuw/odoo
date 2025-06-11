from odoo.tests.common import TransactionCase, tagged

@tagged('-at_install', 'post_install')
class TestSaleOrderTrackSubtype(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'state': 'draft',
        })

    def test_track_subtype_when_state_changes_to_sale(self):
        self.sale_order.write({'state': 'sale'})
        result = self.sale_order._track_subtype({'state': 'draft'})
        expected = self.env.ref('sale.mt_order_confirmed')
        self.assertEqual(result, expected, "Should return 'order confirmed' subtype")

    def test_track_subtype_when_state_changes_to_sent(self):
        self.sale_order.write({'state': 'sent'})
        result = self.sale_order._track_subtype({'state': 'draft'})
        expected = self.env.ref('sale.mt_order_sent')
        self.assertEqual(result, expected, "Should return 'order sent' subtype")

    def test_track_subtype_default_fallback(self):
        result = self.sale_order._track_subtype({})
        expected = super(type(self.sale_order), self.sale_order)._track_subtype({})
        self.assertEqual(result, expected, "Should fall back to super() for other cases")

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.translate import _

@tagged('post_install', '-at_install', 'mytest')
class TestSaleOrderSuggestedRecipients(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'customer@example.com'
        })
        self.sale_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

    def test_suggested_recipient_includes_customer(self):
        recipients = self.sale_order._message_get_suggested_recipients()
        partner_ids = [r['partner_id'] for r in recipients if r.get('reason') == 'Customer']
        self.assertIn(self.partner.id, partner_ids, "Expected partner not found in suggested recipients")

    def test_no_suggested_recipient_if_no_partner(self):
        self.sale_order.partner_id = False
        recipients = self.sale_order._message_get_suggested_recipients()
        customer_recipients = [r for r in recipients if r.get('reason') == 'Customer']
        self.assertEqual(len(customer_recipients), 0, "No 'Customer' recipients should be suggested when partner is missing")
