from odoo import http
from odoo.http import request


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def is_dark_color(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    # Độ sáng theo công thức: (0.299*R + 0.587*G + 0.114*B)
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    return brightness < 128  # Nếu độ sáng thấp => là màu tối


def adjust_brightness(hex_color, factor=1.2):
    """Làm sáng hoặc tối màu theo hệ số factor (>1 là sáng, <1 là tối)"""
    r, g, b = hex_to_rgb(hex_color)
    r = min(int(r * factor), 255)
    g = min(int(g * factor), 255)
    b = min(int(b * factor), 255)
    return f'#{r:02x}{g:02x}{b:02x}'


class StyleCustomController(http.Controller):

    @http.route('/style_custom/custom_dynamic_styles.css', type='http', auth="public", website=True)
    def custom_styles(self):
        navbar_color = request.env['ir.config_parameter'].sudo().get_param(
            'style_custom.navbar_color', '#2e86de'
        )

        text_color = '#ffffff' if is_dark_color(navbar_color) else '#000000'
        hover_color = adjust_brightness(navbar_color, 1.15 if is_dark_color(navbar_color) else 0.85)

        css = f"""
        .o_main_navbar, 
        .o_main_navbar .o_menu_sections .o_nav_entry,
        .o_main_navbar .o_menu_sections .dropdown-toggle,
        .o_main_navbar .o_menu_sections {{
            background-color: {navbar_color} !important;
            color: {text_color} !important;
        }}
        
        .o_main_navbar .o_menu_brand,
        .o_main_navbar .o_nav_entry,
        .o_main_navbar .dropdown-toggle {{
            color: {text_color} !important;
        }}
        
        .o_main_navbar .o_menu_sections .o_nav_entry:hover,
        .o_main_navbar .o_menu_sections .dropdown-toggle:hover {{
            background-color: {hover_color} !important;
        }}
        
        .btn-primary,
        .btn .btn-primary,
        .btn .btn-primary .btn-sm {{
            background-color: {navbar_color} ;
            color: {text_color} ;
            border-color: {navbar_color} ;
        }}
        
        .btn-primary:hover,
        .btn .btn-primary:hover,
        .btn .btn-primary .btn-sm:hover {{
            background-color: {hover_color} ;
            border-color: {hover_color} ;
        }}
        
        .oe_login_form .btn.btn-primary {{
            background-color: {navbar_color} !important;
            color: {text_color} !important;
            border-color: {navbar_color} !important;
        }}
        
        .oe_login_form .btn.btn-primary:hover {{
            background-color: {hover_color} !important;
            border-color: {hover_color} !important;
        }}
        
        """

        return request.make_response(css, [('Content-Type', 'text/css')])
