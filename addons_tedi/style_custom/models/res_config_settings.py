from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    navbar_color = fields.Char(
        string="Màu thanh menu",
        config_parameter='style_custom.navbar_color'
    )

    header_color = fields.Char(string="Header Color")

    font_size = fields.Char(
        string="Cỡ chữ (px)",
        config_parameter='style_custom.font_size',
        default="14px")

    # --- Logo trang đăng nhập ---
    login_logo = fields.Binary(
        string="Logo công ty",
        attachment=True,
        help="Logo sẽ hiển thị trên trang đăng nhập."
    )
    login_logo_filename = fields.Char(string="Filename")

    # --- Ảnh nền trang đăng nhập ---
    login_bg_image_config = fields.Binary(
        string="Ảnh nền đăng nhập",
        readonly=False,
        attachment=True,
    )
    login_bg_image_filename = fields.Char(string="Filename")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        icp = self.env['ir.config_parameter'].sudo()
        # — Load logo
        logo = icp.get_param('web.login_logo', default=False)
        if logo:
            res['login_logo'] = logo
        # — Load ảnh nền (mới nhất)
        bg = self.env['style.custom.image'].sudo().search(
            [], limit=1, order='create_date desc'
        )
        if bg:
            res['login_bg_image_config'] = bg.image
            res['login_bg_image_filename'] = bg.name
        return res

    def set_values(self):
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        # — Lưu logo vào ir.config_parameter
        if self.login_logo:
            icp.set_param('web.login_logo', self.login_logo)
        else:
            icp.set_param('web.login_logo', False)

        # — Lưu ảnh nền vào model style.custom.image
        old = self.env['style.custom.image'].sudo().search([])
        if old:
            old.unlink()
        if self.login_bg_image_config:
            self.env['style.custom.image'].sudo().create({
                'image': self.login_bg_image_config,
                'name': self.login_bg_image_filename or 'Login Background',
            })



