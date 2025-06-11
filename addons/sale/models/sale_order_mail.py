from odoo import _
from odoo.http import request
from odoo.tools import format_amount


class SaleOrderMail:
    def __init__(self, order):
        self.order = order  # this is a single sale.order record

    def _discard_tracking(self):
        return (
            self.order.state == 'draft'
            and request and request.env.context.get('catalog_skip_tracking')
        )

    def track_finalize(self):
        order = self.order
        # The method _track_finalize is sometimes called too early or too late and it
        # might cause a desynchronization with the cache, thus this condition is needed.
        if order.env.cache.contains(order, order._fields['state']) and self._discard_tracking():
            order.env.cr.precommit.data.pop(f'mail.tracking.{order._name}', {})
            order.env.flush_all()
            return True
        return False

    def message_post(self, **kwargs):
        order = self.order
        if order.env.context.get('mark_so_as_sent'):
            order.filtered(lambda o: o.state == 'draft').with_context(tracking_disable=True).write({'state': 'sent'})
        so_ctx = {'mail_post_autofollow': order.env.context.get('mail_post_autofollow', True)}
        if order.env.context.get('mark_so_as_sent') and 'mail_notify_author' not in kwargs:
            kwargs['notify_author'] = order.env.user.partner_id.id in (kwargs.get('partner_ids') or [])
        return so_ctx, kwargs

    def notify_get_recipients_groups(self, groups, message, model_description, msg_vals=None):
        order = self.order
        """ Give access button to users and portal customer as portal is integrated
        in sale. Customer and portal group have probably no right to see
        the document so they don't have the access button. """
        if not order:
            return groups

        if order._context.get('proforma'):
            for group in [g for g in groups if g[0] in ('portal_customer', 'portal', 'follower', 'customer')]:
                group[2]['has_button_access'] = False
            return groups
        local_msg_vals = dict(msg_vals or {})

        # portal customers have full access (existence not granted, depending on partner_id)
        try:
            customer_portal_group = next(group for group in groups if group[0] == 'portal_customer')
        except StopIteration:
            pass
        else:
            access_opt = customer_portal_group[2].setdefault('button_access', {})
            is_tx_pending = order.get_portal_last_transaction().state == 'pending'
            if order._has_to_be_signed():
                if order._has_to_be_paid():
                    access_opt['title'] = _("View Quotation") if is_tx_pending else _("Sign & Pay Quotation")
                else:
                    access_opt['title'] = _("Accept & Sign Quotation")
            elif order._has_to_be_paid() and not is_tx_pending:
                access_opt['title'] = _("Accept & Pay Quotation")
            elif order.state in ('draft', 'sent'):
                access_opt['title'] = _("View Quotation")

        # enable followers that have access through portal
        follower_group = next(group for group in groups if group[0] == 'follower')
        follower_group[2]['active'] = True
        follower_group[2]['has_button_access'] = True
        access_opt = follower_group[2].setdefault('button_access', {})
        if order.state in ('draft', 'sent'):
            access_opt['title'] = _("View Quotation")
        else:
            access_opt['title'] = _("View Order")
        access_opt['url'] = order._notify_get_action_link('view', **local_msg_vals)

        return groups

    def notify_by_email_prepare_rendering_context(self, render_context):
        order = self.order
        lang_code = render_context.get('lang')
        record = render_context['record']
        subtitles = [f"{record.name} - {record.partner_id.name}" if record.partner_id else record.name]
        if order.amount_total:
            # Do not show the price in subtitles if zero (e.g. e-commerce orders are created empty)
            subtitles.append(
                format_amount(order.env, order.amount_total, order.currency_id, lang_code=lang_code),
            )
        render_context['subtitles'] = subtitles
        return render_context

    def track_subtype(self, init_values):
        order = self.order
        if 'state' in init_values and order.state == 'sale':
            return order.env.ref('sale.mt_order_confirmed')
        elif 'state' in init_values and order.state == 'sent':
            return order.env.ref('sale.mt_order_sent')
        return False

    def message_get_suggested_recipients(self, recipients):
        order = self.order
        if order.partner_id:
            order._message_add_suggested_recipient(
                recipients, partner=order.partner_id, reason=_("Customer")
            )
        return recipients