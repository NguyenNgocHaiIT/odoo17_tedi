# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FieldDocumentation(models.Model):
    _name = 'field.documentation'
    _description = 'Field Documentation Storage'
    _order = 'field_name'

    model_name = fields.Char(
        string='Model Name', required=True, index=True)
    field_name = fields.Char(
        string='Field Name', required=True)
    field_string = fields.Char(
        string='Field Display Name', required=True)
    field_type = fields.Char(string='Field Type')
    field_help = fields.Text(string='Field Note')
    rendered_jinja_code = fields.Char(
        string='Code Template Render',
        compute='_compute_rendered_jinja_code',
        store=True,
        help="Recommended Jinja/Docx syntax is based on data type.")

    _sql_constraints = [
        ('field_unique', 'unique(model_name, field_name)', 'This field is already stored for this Model!')
    ]

    @api.model
    def populate_field_documentation(self):
        EXCLUDED_MODELS = ('ir.ui.view', 'ir.model.data', 'ir.attachment', 'res.company')
        all_models = self.env['ir.model'].search([])
        self.search([]).unlink()
        for model_record in all_models:
            model_name = model_record.model

            if model_name in EXCLUDED_MODELS or not hasattr(self.env[model_name], '_fields'):
                continue
            try:
                modelobj = self.env[model_name]
                fields_data = modelobj.fields_get([])
                for field_name, field_info in fields_data.items():
                    self.create({
                        'model_name': model_name,
                        'field_name': field_name,
                        'field_string': field_info.get('string', 'Tên không xác định'),
                        'field_type': field_info.get('type', ''),
                        'field_help': field_info.get('help', ''),
                    })
            except Exception as e:
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Field document collection and storage complete!',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.depends('field_name', 'field_type')
    def _compute_rendered_jinja_code(self):
        for doc in self:
            field_name = doc.field_name
            field_type = doc.field_type

            base_syntax = f"{{{{ docs.{field_name} }}}}"
            syntax = base_syntax

            if field_type in ('datetime', 'date'):
                syntax = f"{{{{ formatdate(docs.{field_name}) }}}}"

            elif field_type == 'float' or field_type == 'integer':
                syntax = f"{{{{ spelled_out(docs.{field_name}) }}}}"

            elif field_type == 'monetary':
                syntax = f"{{{{ convert_currency(docs.{field_name}, docs.currency_id) }}}}"

            elif field_type == 'html':
                syntax = f"{{{{p html2docx(docs.{field_name}) }}}}"

            elif field_type == 'binary':
                if 'image' in field_name or 'photo' in field_name:
                    syntax = f"{{{{render_image(docs.{field_name}, width=15, height=15) }}}}"
                else:
                    syntax = f"{{{{p add_subdoc(docs.{field_name}) }}}}"

            elif field_type == 'text':
                syntax = f"{{{{r rich_text(docs{field_name}) }}}}"

            doc.rendered_jinja_code = syntax
