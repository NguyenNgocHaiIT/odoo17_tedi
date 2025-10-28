from odoo import api, fields, models

class WebsitePost(models.Model):
    _name = 'website.post'

    name = fields.Char(string='Tiêu đề')
    post_type = fields.Many2one('post.type', string='Loại tin tức')
    create_user = fields.Many2one('res.users', string='Người tạo',  default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Ngày tạo')
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('chua_duyet', 'chưa duyệt'),
        ('da_duyet', 'đã duyệt')
    ], string='Trạng thái', default='draft')
    confirm_user = fields.Many2one('res.users', string='Người duyệt')
    have_post = fields.Boolean(string='Đã đăng lên web')
    image = fields.Image(string='Hình ảnh đính kèm')
    content = fields.Text(string='Nội dung')

    def action_submit_leader(self):
        # logic trình lãnh đạo (ví dụ: chuyển trạng thái)
        self.write({'state': 'chua_duyet'})
        return True

    def action_save_draft(self):
        # logic lưu nháp
        self.write({'state': 'draft'})
        return True

    def approve(self):
        self.write({'state': 'da_duyet'})
        return True

class PostType(models.Model):
    _name = 'post.type'

    name = fields.Char('Tên loại tin tức')