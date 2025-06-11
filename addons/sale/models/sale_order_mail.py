from odoo.http import request

class SaleOrderMail:
    def __init__(self, order):
        self.order = order  # this is a single sale.order record

    def message_post(self, **kwargs):
        if self.order.env.context.get('mark_so_as_sent'):
            self.order.filtered(lambda o: o.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
        so_ctx = {'mail_post_autofollow': self.order.env.context.get('mail_post_autofollow', True)}
        if self.order.env.context.get('mark_so_as_sent') and 'mail_notify_author' not in kwargs:
            kwargs['notify_author'] = self.order.env.user.partner_id.id in (kwargs.get('partner_ids') or [])
        return so_ctx, kwargs
