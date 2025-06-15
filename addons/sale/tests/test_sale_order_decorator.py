from odoo.addons.sale.models.sale_order_decorators.sale_order_logic import SaleOrderLogic

from odoo.addons.sale.models.sale_order_decorators.sale_order_logic_interface import SaleOrderLogicInterface
from odoo.tests.common import TransactionCase, tagged
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.sale.models.sale_order_decorators.sale_order_decorator_interface import SaleOrderDecoratorInterface
from odoo.addons.sale.models.sale_order_decorators import _decorator_map


class DummyTrackingDecorator(SaleOrderDecoratorInterface):
    _instances = []
    _tracking = []

    def __init__(self, orders, logic):
        super().__init__(orders, logic)
        self.id = len(self._instances)
        self._instances.append(self)

    def action_confirm(self):
        self._tracking.append(f"confirm{self.id}")
        return super().action_confirm()

    def _action_cancel(self):
        self._tracking.append(f"cancel{self.id}")
        return super()._action_cancel()

    def _validate_order(self):
        self._tracking.append(f"validate{self.id}")
        super()._validate_order()

    def _recompute_prices(self):
        self._tracking.append(f"recompute{self.id}")
        super()._recompute_prices()


@tagged('-at_install', 'post_install')
class TestSaleOrderDecorator(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _decorator_map["DummyTrackingDecorator"] = DummyTrackingDecorator
        cls.__save_config_param = cls.env['ir.config_parameter'].sudo().get_param('sale.customize', None)


    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        _decorator_map.pop("DummyTrackingDecorator")
        if not cls.__save_config_param is None:
            cls.env['ir.config_parameter'].sudo().set_param('sale.customize', cls.__save_config_param)


    def setUp(self):
        super().setUp()
        # should init to None, set to be sure
        SaleOrder._LogicDecoratorBuilder._logic_chain = None
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
            'type': 'consu'
        })

    def tearDown(self):
        SaleOrder._LogicDecoratorBuilder._logic_chain = None
        DummyTrackingDecorator._instances.clear()

    def _create_sale_order(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0
            })]
        })
        return order

    def test_decorator_chain_created_when_needed(self):
        order = self._create_sale_order()
        self.env['ir.config_parameter'].sudo().set_param('sale.customize', 'DummyTrackingDecorator, sale')

        # At this point _logic_chain should be None
        self.assertIsNone(SaleOrder._LogicDecoratorBuilder._logic_chain)
        # Trigger logic that creates the chain (e.g., order.action_confirm())
        order.action_confirm()

        # Now _logic_chain should be assigned
        chain = SaleOrder._LogicDecoratorBuilder._logic_chain
        self.assertIsNotNone(SaleOrder._LogicDecoratorBuilder._logic_chain)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1], DummyTrackingDecorator)
        self.assertEqual(chain[0], SaleOrderLogic)

    def test_decorator_implicit_sale(self):
        # identical to previous execept implicit config parameter
        order = self._create_sale_order()
        self.env['ir.config_parameter'].sudo().set_param('sale.customize', 'DummyTrackingDecorator')
        self.assertIsNone(SaleOrder._LogicDecoratorBuilder._logic_chain)

        order.action_confirm()

        chain = SaleOrder._LogicDecoratorBuilder._logic_chain
        self.assertIsNotNone(chain)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1], DummyTrackingDecorator)
        self.assertEqual(chain[0], SaleOrderLogic)

    def test_decorator_no_config_default_value(self):
        # identical to previous execept implicit config parameter
        order = self._create_sale_order()
        self.env['ir.config_parameter'].sudo().search([
            ('key', '=', 'sale.customize')
        ]).unlink()
        self.assertIsNone(SaleOrder._LogicDecoratorBuilder._logic_chain)

        order.action_confirm()

        chain = SaleOrder._LogicDecoratorBuilder._logic_chain
        self.assertIsNotNone(chain)
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0], SaleOrderLogic)

    def test_decorator_chain_invalid_module_ignored(self):
        _decorator_map.pop("DummyTrackingDecorator")
        result = None
        try:
            order = self._create_sale_order()
            self.env['ir.config_parameter'].sudo().set_param('sale.customize', 'DummyTrackingDecorator, sale')
            self.assertIsNone(SaleOrder._LogicDecoratorBuilder._logic_chain)

            order.action_confirm()

            chain = SaleOrder._LogicDecoratorBuilder._logic_chain
            self.assertIsNotNone(chain)
            self.assertEqual(len(chain), 1)
            self.assertEqual(chain[0], SaleOrderLogic)
        except Exception as err:
            result = err
        _decorator_map["DummyTrackingDecorator"] = DummyTrackingDecorator
        if not result is None:
            raise result


    def test_decorator_chain_complete_interface_called_correctly(self):
        self.env['ir.config_parameter'].sudo().set_param('sale.customize', 'DummyTrackingDecorator, sale')
        interface = SaleOrder
        i = 0
        for message, func in [
            ("confirm", interface.action_confirm),
            ("validate", interface._validate_order),
            ("cancel", interface._action_cancel),
            ("recompute", interface._recompute_prices)]:
            order = self._create_sale_order()
            func(order)
            self.assertEqual(DummyTrackingDecorator._tracking[0], message + str(i))
            i += len(DummyTrackingDecorator._tracking)
            DummyTrackingDecorator._tracking.clear()
        self.assertEqual(len(SaleOrder._LogicDecoratorBuilder._logic_chain), 2)


    def test_decorator_chain_complete_nested_decorators(self):
        self.env['ir.config_parameter'].sudo().set_param('sale.customize', 'DummyTrackingDecorator, DummyTrackingDecorator, DummyTrackingDecorator, DummyTrackingDecorator, DummyTrackingDecorator, sale')
        order = self._create_sale_order()
        self.assertIsNone(SaleOrder._LogicDecoratorBuilder._logic_chain)

        order.action_confirm()

        chain = SaleOrder._LogicDecoratorBuilder._logic_chain
        self.assertIsNotNone(chain)
        self.assertEqual(len(chain), 6)

        self.assertEqual(chain[5], DummyTrackingDecorator)
        self.assertEqual(chain[4], DummyTrackingDecorator)
        self.assertEqual(chain[3], DummyTrackingDecorator)
        self.assertEqual(chain[2], DummyTrackingDecorator)
        self.assertEqual(chain[1], DummyTrackingDecorator)
        self.assertEqual(chain[0], SaleOrderLogic)
        # creation happens from left to right, execution from right to left
        # assert in form of a stack view

        for i in range(5):
            self.assertEqual(DummyTrackingDecorator._tracking[i], f"confirm{4 - i}")
