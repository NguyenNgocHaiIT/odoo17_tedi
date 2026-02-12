from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrExpense(models.Model):
    _inherit = "hr.expense"

    passenger_count = fields.Integer(
        string="Số người bay",
        default=1
    )

    product_code = fields.Char(
        string="Mã loại chi phí",
        related="product_id.default_code",
        store=False,
        readonly=True
    )

    predict_amount = fields.Monetary(string="Chi phí dự kiến")

    department_id = fields.Many2one('hr.department', string="Đơn vị")

    # ==========================
    # PRODUCT: VÉ MÁY BAY
    # ==========================
    def _get_airline_product(self):
        Product = self.env['product.product']

        product = Product.search(
            [('default_code', '=', 'AIRLINES')],
            limit=1
        )

        if not product:
            product = Product.create({
                'name': 'Vé máy bay',
                'default_code': 'AIRLINES',
            })

        return product

    # ==========================
    # ACTIONS - EMAIL ĐƠN GIẢN
    # ==========================
    def action_submit(self):
        self.ensure_one()
        self.state = 'submitted'

        # Lấy tất cả fleet.fleet_group_manager
        group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
        if group:
            # Lấy tất cả người dùng trong nhóm
            managers = group.users

            # Lấy emails của tất cả managers
            manager_emails = [manager.email for manager in managers if manager.email]

            if manager_emails:
                try:
                    # Tạo email đơn giản
                    mail_values = {
                        'subject': f'Cần duyệt đề xuất chi phí: {self.name}',
                        'email_to': ', '.join(manager_emails),
                        'email_from': self.env.user.email or self.company_id.email or 'noreply@company.com',
                        'body_html': f"""
                        <p>Có đề xuất chi phí cần duyệt:</p>
                        <ul>
                            <li><b>Tên:</b> {self.name}</li>
                            <li><b>Người tạo:</b> {self.employee_id.name if self.employee_id else ''}</li>
                            <li><b>Số tiền:</b> {self.total_amount}</li>
                            <li><b>Loại chi phí:</b> {self.product_id.name if self.product_id else ''}</li>
                        </ul>
                        <p>Vui lòng vào hệ thống để duyệt.</p>
                        """,
                    }

                    # Tạo và gửi email
                    mail = self.env['mail.mail'].create(mail_values)
                    mail.send()

                    _logger.info(f"Email sent to managers for expense {self.name}")

                except Exception as e:
                    _logger.error(f"Failed to send email: {str(e)}")

        return True

    def action_approve_expense(self):
        self.ensure_one()
        self.state = 'approved'

        # Gửi email cho người tạo
        if self.employee_id.user_id and self.employee_id.user_id.email:
            try:
                # Tạo email đơn giản
                mail_values = {
                    'subject': f'Đề xuất chi phí đã được duyệt: {self.name}',
                    'email_to': self.employee_id.user_id.email,
                    'email_from': self.env.user.email or self.company_id.email or 'noreply@company.com',
                    'body_html': f"""
                    <p>Đề xuất chi phí của bạn đã được duyệt:</p>
                    <ul>
                        <li><b>Tên:</b> {self.name}</li>
                        <li><b>Số tiền:</b> {self.total_amount}</li>
                        <li><b>Người duyệt:</b> {self.env.user.name}</li>
                        <li><b>Ngày duyệt:</b> {fields.Datetime.now()}</li>
                    </ul>
                    """,
                }

                # Tạo và gửi email
                mail = self.env['mail.mail'].create(mail_values)
                mail.send()

                _logger.info(f"Approval email sent for expense {self.name}")

            except Exception as e:
                _logger.error(f"Failed to send approval email: {str(e)}")

        return True

    def action_refuse_expense(self):
        self.ensure_one()
        self.state = 'refused'

        # Gửi email cho người tạo
        if self.employee_id.user_id and self.employee_id.user_id.email:
            try:
                # Tạo email đơn giản
                mail_values = {
                    'subject': f'Đề xuất chi phí bị từ chối: {self.name}',
                    'email_to': self.employee_id.user_id.email,
                    'email_from': self.env.user.email or self.company_id.email or 'noreply@company.com',
                    'body_html': f"""
                    <p>Đề xuất chi phí của bạn đã bị từ chối:</p>
                    <ul>
                        <li><b>Tên:</b> {self.name}</li>
                        <li><b>Số tiền:</b> {self.total_amount}</li>
                        <li><b>Người từ chối:</b> {self.env.user.name}</li>
                        <li><b>Ngày từ chối:</b> {fields.Datetime.now()}</li>
                    </ul>
                    <p>Vui lòng kiểm tra lại.</p>
                    """,
                }

                # Tạo và gửi email
                mail = self.env['mail.mail'].create(mail_values)
                mail.send()

                _logger.info(f"Refusal email sent for expense {self.name}")

            except Exception as e:
                _logger.error(f"Failed to send refusal email: {str(e)}")

        return True

    @api.model
    def create(self, vals):
        if not vals.get('product_id'):
            product = self._get_airline_product()
            vals['product_id'] = product.id

        return super().create(vals)