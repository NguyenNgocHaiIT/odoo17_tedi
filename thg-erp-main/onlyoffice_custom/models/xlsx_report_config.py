# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class XlsxReportConfig(models.Model):
    _inherit = 'xlsx.report.config'

    field_docx_ids = fields.Many2many(
        'field.documentation',
        string="Fields for docx",
        compute='_compute_field_docx_ids')
    onlyoffice_url = fields.Char('OnlyOffice URL', compute='_compute_onlyoffice_url')
    onlyoffice_iframe = fields.Html(
        string='OnlyOffice Preview',
        compute='_compute_onlyoffice_iframe', sanitize=False, store=False)
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment', string="Attachments")

    @api.onchange('attachment_id')
    def _compute_attachment_binary(self):
        for record in self:
            if record.attachment_id:
                record.report_xlsx_template = record.attachment_id.datas
                record.report_xlsx_template_filename = record.attachment_id.name
            else:
                record.report_xlsx_template = False
                record.report_xlsx_template_filename = False

    @api.depends('onlyoffice_url')
    def _compute_onlyoffice_iframe(self):
        for record in self:
            url = record.onlyoffice_url or ''
            if url and url.strip():
                record.onlyoffice_iframe = f'''
                          <div style="border: 1px solid #ddd; border-radius: 4px; overflow: hidden; height: 1000px;">
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
                          <div style="border: 2px dashed #dee2e6; border-radius: 4px; padding: 40px; text-align: center; background: #f8f9fa; height: 1000px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                              <i class="fa fa-external-link fa-3x text-muted mb-3"></i>
                              <p class="text-muted mb-1">Enter OnlyOffice URL to preview</p>
                              <small class="text-muted">Example: https://doc.onlyoffice.com/editor</small>
                          </div>
                      '''

    @api.depends('model_id')
    def _compute_field_docx_ids(self):
        FieldDoc = self.env['field.documentation']

        for report in self:
            report.field_docx_ids = False

            if not report.model_id or not report.model_id.model:
                continue

            model_name = report.model_id.model

            field_docs_to_link = self.env['field.documentation']
            new_records_vals = []

            ModelFields = self.env['ir.model.fields'].sudo().search([
                ('model_id', '=', report.model_id.id),
            ])

            for field in ModelFields:
                existing_doc = FieldDoc.search([
                    ('field_name', '=', field.name), ('model_name', '=', report.model_id.model)
                ], limit=1)

                if existing_doc:
                    field_docs_to_link += existing_doc
                else:
                    new_records_vals.append({
                        'field_name': field.name,
                        'model_name': report.model_id.model,
                        'field_string': field.field_description,
                        'field_type': field.ttype,
                    })

            if new_records_vals:
                new_docs = FieldDoc.sudo().create(new_records_vals)

                field_docs_to_link += new_docs

            report.field_docx_ids = field_docs_to_link

    @api.depends('attachment_ids')
    def _compute_onlyoffice_url(self):
        for res in self:
            if res.attachment_ids:
                attendance_id = res.attachment_ids[0]
                web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                res.onlyoffice_url = f'{web_base_url}/onlyoffice/editor/{attendance_id.id}'
            else:
                res.onlyoffice_url = False
