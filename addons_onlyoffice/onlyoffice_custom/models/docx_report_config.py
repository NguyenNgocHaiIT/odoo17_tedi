# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class DocxReportConfig(models.Model):
    _inherit = "docx.report.config"

    report_docx_template = fields.Binary(
        string="Report DOCX Template",
        related='attachment_id.datas',
        required=True,
        readonly=True,
        help="DOCX template to be used for the report",
    )
    report_docx_template_filename = fields.Char(
        string="Report DOCX Template Name",
        related='attachment_id.name',
        required=True,
        readonly=True,
    )

    field_docx_ids = fields.Many2many(
        'field.documentation',
        string="Fields for docx",
        compute='_compute_field_docx_ids')
    attachment_id = fields.Many2one(
        'ir.attachment', string="Attachment")
    onlyoffice_url = fields.Char('OnlyOffice URL', compute='_compute_onlyoffice_url')
    onlyoffice_iframe = fields.Html(
        string='OnlyOffice Preview',
        compute='_compute_onlyoffice_iframe', sanitize=False, store=False)
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment', string="Attachments")
    field_filter = fields.Char(
        string='Filter Field Name',
        help='Enter field name to filter (wildcard * allowed)',
        store=False
    )
    binary_id = fields.Many2one(
        'ir.model.fields',
        string='Field Name',
        required=False,
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('relation', '=', 'ir.attachment'), '|',('ttype', '=', 'many2many'), ('ttype', '=', 'many2one')]",
        readonly=False,
        help="Field file report"
    )

    @api.depends('attachment_ids')
    def compute_attachment_binary(self):
        for record in self:
            if record.attachment_ids:
                record.report_docx_template = record.attachment_ids[0].datas
                record.report_docx_template_filename = record.attachment_ids[0].name
            else:
                record.report_docx_template = False
                record.report_docx_template_filename = False

    @api.depends('onlyoffice_url')
    def _compute_onlyoffice_iframe(self):
        for record in self:
            url = record.onlyoffice_url or ''
            if url and url.strip():
                record.onlyoffice_iframe = f'''
                       <div style="border: 1px solid #ddd; border-radius: 4px; overflow: hidden; height: 100%;">
                           <iframe 
                               src="{url}" 
                               width="100%" 
                               height="100%" 
                               frameborder="0"
                               style="border: none;"
                           ></iframe>
                       </div>
                   '''
            else:
                record.onlyoffice_iframe = '''
                       <div style="border: 2px dashed #dee2e6; border-radius: 4px; padding: 40px; text-align: center; background: #f8f9fa; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                           <i class="fa fa-external-link fa-3x text-muted mb-3"></i>
                           <p class="text-muted mb-1">Enter OnlyOffice URL to preview</p>
                           <small class="text-muted">Example: https://doc.onlyoffice.com/editor</small>
                       </div>
                   '''

    @api.depends('model_id', 'field_filter')
    def _compute_field_docx_ids(self):
        FieldDoc = self.env['field.documentation']

        for report in self:
            report.field_docx_ids = False

            if not report.model_id or not report.model_id.model:
                continue

            model_name = report.model_id.model
            filter_pattern = report.field_filter.strip() if report.field_filter else ''
            use_fnmatch = '*' in filter_pattern

            ModelFields = self.env['ir.model.fields'].sudo().search_read(
                [('model_id', '=', report.model_id.id)],
                ['name', 'field_description', 'ttype']
            )

            docs_to_link = self.env['field.documentation']
            new_records_vals = []

            import fnmatch

            for field in ModelFields:
                fname = field['name']

                # filter pattern
                if filter_pattern:
                    if use_fnmatch:
                        if not fnmatch.fnmatch(fname, filter_pattern):
                            continue
                    else:
                        if filter_pattern.lower() not in fname.lower():
                            continue

                # tìm tương đối LIKE
                existing_doc = FieldDoc.search([
                    ('model_name', '=', model_name),
                    ('field_name', 'like', f"%{fname}%")
                ], limit=1)

                if existing_doc:
                    docs_to_link |= existing_doc
                else:
                    new_records_vals.append({
                        'field_name': fname,
                        'model_name': model_name,
                        'field_string': field['field_description'],
                        'field_type': field['ttype'],
                    })

            if new_records_vals:
                new_docs = FieldDoc.sudo().create(new_records_vals)
                docs_to_link |= new_docs

            report.field_docx_ids = docs_to_link

    def action_filter_fields(self):
        self._compute_field_docx_ids()
        return True

    def action_clear_filter(self):
        self.field_filter = False
        self._compute_field_docx_ids()
        return True

    @api.depends('attachment_ids', 'state')
    def _compute_onlyoffice_url(self):
        for res in self:
            if res.attachment_ids:
                attendance_id = res.attachment_ids[0]
                res.attachment_id = attendance_id
                web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                if res.state == 'published':
                    res.onlyoffice_url = f'{web_base_url}/onlyoffice/editor/{attendance_id._origin.id}/1'
                else:
                    res.onlyoffice_url = f'{web_base_url}/onlyoffice/editor/{attendance_id._origin.id}'
            else:
                res.onlyoffice_url = False
                res.attachment_id = False

    def _prepare_action_val(self):
        return {
            "name": self.name,
            "model": self.model_id.model,
            "report_type": "docx",
            "report_docx_template": self.attachment_ids[0].datas,
            "report_docx_template_name": self.report_docx_template_filename,
            "report_name": self._prepare_template_name(),
            "docx_merge_mode": self.docx_merge_mode,
            'docx_autoescape': self.autoescape,
            "print_report_name": self.print_report_name,
        }
