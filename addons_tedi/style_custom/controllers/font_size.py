from odoo import http
from odoo.http import request

class CustomFontSizeController(http.Controller):

    @http.route('/style_custom/custom_font_size.css', type='http', auth='user')
    def custom_font_size(self):
        font_size = request.env['ir.config_parameter'].sudo().get_param('style_custom.font_size', '14px')
        css = f"""
        html, body, .o_web_client, .o_main_content, .o_form_view, .o_list_view, .o_kanban_view, * {{
            font-size: {font_size} !important;
        }}
        """
        return request.make_response(css, headers=[('Content-Type', 'text/css')])
