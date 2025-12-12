# -*- coding: utf-8 -*-

from logging import getLogger
from odoo import _, api, fields, models

_logger = getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    field_docx_ids = fields.Many2many(
        'field.documentation',
        string="Fields for docx",
        compute='_compute_field_docx_ids')
    onlyoffice_iframe_html = fields.Char(
        string="OnlyOffice Editor",
        compute='_compute_onlyoffice_iframe_html',
        store=False)

    # @api.depends('attachment_id')  # Thay thế bằng các trường tạo nên URL động
    def _compute_onlyoffice_iframe_html(self):
        # Giả định: Lấy ID đính kèm (attachment_id) hoặc ID bản ghi hiện tại
        # Đây là nơi bạn xây dựng URL động

        # Ví dụ URL TĨNH của bạn:
        BASE_URL = "http://localhost/9.1.0-7ae99ff4e34db49ea0727c342474c9ea/web-apps/apps/documenteditor/main/index.html"

        # Ví dụ: Giả sử bạn muốn truyền ID của bản ghi hiện tại (self.id)
        # THAY THẾ logic này bằng logic OnlyOffice thực tế của bạn

        for rec in self:
            # Xây dựng các tham số động
            dynamic_params = {
                '_dc': '9.1.0-168',
                'lang': 'en_US',
                'customer': 'ONLYOFFICE',
                'type': 'desktop',
                'frameEditorId': 'doceditor',
                'isForm': 'false',
                'record_id': rec.id or 0,
                'parentOrigin': 'http://localhost:8069',
                'uitheme': 'default-light',
                'fileType': 'docx'
            }

            # Chuyển dictionary tham số thành chuỗi truy vấn (query string)
            query_string = "&".join(f"{k}={v}" for k, v in dynamic_params.items())
            full_src = f"{BASE_URL}?{query_string}"

            # Tạo mã Iframe hoàn chỉnh với src động
            # Cần đảm bảo width và height phù hợp với bố cục 2/3
            iframe_html = f"""
                    <iframe
                        id="onlyoffice_iframe"
                        class="onlyoffice-frame"
                        src="{full_src}" 
                        title="OnlyOffice Editor"
                        style="width: 100%; height: 2000px;"
                        sandbox="allow-same-origin allow-scripts allow-forms allow-modals"
                    ></iframe>
                """
            rec.onlyoffice_iframe_html = iframe_html

    @api.onchange('model_id')
    def _onchange_display_name(self):
        for record in self:
            record.model = record.model_id.model

    @api.depends('model_id')
    def _compute_field_docx_ids(self):
        """
        Tính toán danh sách field.documentation. Kiểm tra từng field:
        Nếu đã tồn tại -> Liên kết.
        Nếu chưa tồn tại -> Tạo mới.
        """
        FieldDoc = self.env['field.documentation']

        for report in self:
            report.field_docx_ids = False

            if not report.model_id or not report.model_id.model:
                continue

            model_name = report.model_id.model

            # Khởi tạo danh sách các bản ghi FieldDoc cần liên kết
            field_docs_to_link = self.env['field.documentation']
            new_records_vals = []

            # 1. Lấy tất cả các field gốc (ir.model.fields) của model được chọn
            ModelFields = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', report.model_id.id),
            ])

            # 2. Lặp qua từng field và kiểm tra/tạo
            for field in ModelFields:
                # Tìm kiếm bản ghi FieldDocumentation cho field cụ thể này
                existing_doc = FieldDoc.search([
                    ('field_name', '=', field.name), ('model_name', '=', report.model)
                    # SỬ DỤNG field_id để kiểm tra chính xác nhất
                ], limit=1)

                if existing_doc:
                    # Nếu đã tồn tại -> Thêm vào danh sách liên kết
                    field_docs_to_link += existing_doc
                else:
                    # Nếu chưa tồn tại -> Thêm vào danh sách tạo mới
                    new_records_vals.append({
                        'field_name': field.name,
                        'model_name': report.model,
                        'field_string': field.field_description,
                        'field_type': field.ttype,
                    })

            # 3. Tạo hàng loạt các bản ghi FieldDocumentation mới
            if new_records_vals:
                # Gán quyền quản trị để tạo bản ghi
                new_docs = FieldDoc.sudo().create(new_records_vals)

                # Thêm các bản ghi mới tạo vào danh sách liên kết
                field_docs_to_link += new_docs

            # 4. Gán kết quả vào trường Many2many
            report.field_docx_ids = field_docs_to_link

    def action_render_field_code(self):
        """
        Render mã code của các field đã tính toán (ví dụ: {{ o.name }})
        và trả về action client để kích hoạt chức năng copy ở frontend (JS).
        """
        self.ensure_one()

        codes = []
        # Lặp qua các field đã được tính toán
        for field_doc in self.field_docx_ids:
            # Tạo mã code theo cú pháp Docx/Jinja.
            code = f"{{{{ o.{field_doc.field_name} }}}}"
            codes.append(code)

        # Nối tất cả các mã code thành một chuỗi duy nhất, cách nhau bằng dòng mới
        rendered_code = "\n".join(codes)

        # Trả về action client. 'tag' là tên mà JavaScript sẽ lắng nghe và xử lý.
        return {
            'type': 'ir.actions.client',
            'tag': 'field_doc_copy_to_clipboard',  # Tên tag JS tùy chỉnh
            'name': 'Copy Field Codes',
            'params': {
                'text_to_copy': rendered_code,  # Dữ liệu cần copy
                'message': f"Đã sao chép {len(codes)} mã field vào bộ nhớ tạm!",
            }
        }
