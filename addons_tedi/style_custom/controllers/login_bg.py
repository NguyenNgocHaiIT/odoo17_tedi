from odoo import http
from odoo.http import request
import base64
from odoo.modules.module import get_module_resource

class StyleCustomController(http.Controller):

    @http.route('/style_custom/login_bg', type='http', auth='public', cache=3600)
    def login_bg_image(self):
        # 1. Lấy ảnh từ DB
        image = request.env['style.custom.image'].sudo().search([], limit=1)
        if image and image.image:
            return request.make_response(
                base64.b64decode(image.image),
                [('Content-Type', 'image/png')]
            )

        # 2. Lấy ảnh mặc định từ module
        default_path = file_path('style_custom/static/src/img/background_login.jpg')

        if default_path:
            try:
                with open(default_path, 'rb') as f:
                    return request.make_response(
                        f.read(),
                        [('Content-Type', 'image/png')]
                    )
            except FileNotFoundError:
                pass

        # 3. Fallback ảnh rỗng (transparent PNG 1x1 px)
        transparent_png = base64.b64decode(
            b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
        )
        return request.make_response(
            transparent_png,
            [('Content-Type', 'image/png')]
        )
