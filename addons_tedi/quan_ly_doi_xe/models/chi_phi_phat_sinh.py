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
    # EMAIL TEMPLATES
    # ==========================
    def _get_email_template_submit(self):
        """Template email khi submit"""
        return self.env.ref('hr_expense.email_template_expense_submit', raise_if_not_found=False)

    def _get_email_template_approve(self):
        """Template email khi approve"""
        return self.env.ref('hr_expense.email_template_expense_approve', raise_if_not_found=False)

    def _get_email_template_refuse(self):
        """Template email khi refuse"""
        return self.env.ref('hr_expense.email_template_expense_refuse', raise_if_not_found=False)

    # ==========================
    # ACTIONS
    # ==========================
    def action_submit(self):
        self.ensure_one()
        self.state = 'submitted'

        # Lấy tất cả fleet.fleet_group_manager
        group = self.env.ref('fleet.fleet_group_manager', raise_if_not_found=False)
        if group:
            # Lấy tất cả người dùng trong nhóm
            managers = group.users

            # Gửi email cho từng manager
            for manager in managers:
                if manager.email:
                    try:
                        # Tạo email template động
                        mail_template = self.env['mail.template'].create({
                            'name': f'Expense Submit Notification - {self.name}',
                            'subject': f'Đề xuất chi phí {self.name} đã được gửi duyệt',
                            'body_html': f"""
                            <div>
                                <p>Xin chào {manager.name},</p>
                                <p>Đề xuất chi phí <strong>{self.name}</strong> đã được gửi để duyệt.</p>
                                <p><strong>Thông tin chi tiết:</strong></p>
                                <ul>
                                    <li>Người tạo: {self.employee_id.name if self.employee_id else ''}</li>
                                    <li>Số tiền: {self.total_amount}</li>
                                    <li>Loại chi phí: {self.product_id.name if self.product_id else ''}</li>
                                    <li>Mô tả: {self.name}</li>
                                </ul>
                                <p>Vui lòng kiểm tra và phê duyệt.</p>
                                <p>Trân trọng,</p>
                            </div>
                            """,
                            'email_from': self.env.user.email or self.company_id.email,
                            'email_to': manager.email,
                        })

                        mail_template.send_mail(self.id, force_send=True)

                    except Exception as e:
                        _logger.error(f"Failed to send email to {manager.email}: {str(e)}")

        return True

    def action_approve_expense(self):
        self.ensure_one()
        self.state = 'approved'

        # Gửi email cho người tạo (employee)
        if self.employee_id.user_id and self.employee_id.user_id.email:
            try:
                # Tạo email template động
                mail_template = self.env['mail.template'].create({
                    'name': f'Expense Approved - {self.name}',
                    'subject': f'Đề xuất chi phí {self.name} đã được phê duyệt',
                    'body_html': f"""
                    <div>
                        <p>Xin chào {self.employee_id.name},</p>
                        <p>Đề xuất chi phí <strong>{self.name}</strong> của bạn đã được phê duyệt.</p>
                        <p><strong>Thông tin chi tiết:</strong></p>
                        <ul>
                            <li>Số tiền: {self.total_amount}</li>
                            <li>Loại chi phí: {self.product_id.name if self.product_id else ''}</li>
                            <li>Người duyệt: {self.env.user.name}</li>
                            <li>Ngày duyệt: {fields.Datetime.now()}</li>
                        </ul>
                        <p>Trân trọng,</p>
                    </div>
                    """,
                    'email_from': self.env.user.email or self.company_id.email,
                    'email_to': self.employee_id.user_id.email,
                })

                mail_template.send_mail(self.id, force_send=True)

            except Exception as e:
                _logger.error(f"Failed to send approval email: {str(e)}")

        return True

    def action_refuse_expense(self):
        self.ensure_one()
        self.state = 'refused'

        # Gửi email cho người tạo (employee)
        if self.employee_id.user_id and self.employee_id.user_id.email:
            try:
                # Tạo email template động
                mail_template = self.env['mail.template'].create({
                    'name': f'Expense Refused - {self.name}',
                    'subject': f'Đề xuất chi phí {self.name} đã bị từ chối',
                    'body_html': f"""
                    <div>
                        <p>Xin chào {self.employee_id.name},</p>
                        <p>Đề xuất chi phí <strong>{self.name}</strong> của bạn đã bị từ chối.</p>
                        <p><strong>Thông tin chi tiết:</strong></p>
                        <ul>
                            <li>Số tiền: {self.total_amount}</li>
                            <li>Loại chi phí: {self.product_id.name if self.product_id else ''}</li>
                            <li>Người từ chối: {self.env.user.name}</li>
                            <li>Ngày từ chối: {fields.Datetime.now()}</li>
                        </ul>
                        <p>Vui lòng kiểm tra lại thông tin và gửi lại đề xuất nếu cần.</p>
                        <p>Trân trọng,</p>
                    </div>
                    """,
                    'email_from': self.env.user.email or self.company_id.email,
                    'email_to': self.employee_id.user_id.email,
                })

                mail_template.send_mail(self.id, force_send=True)

            except Exception as e:
                _logger.error(f"Failed to send refusal email: {str(e)}")

        return True

    @api.model
    def create(self, vals):
        if not vals.get('product_id'):
            product = self._get_airline_product()
            vals['product_id'] = product.id

        return super().create(vals)