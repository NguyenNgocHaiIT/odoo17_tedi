from odoo import fields
from odoo.fields import Binary as OriginalBinary
import logging
import magic
import base64

_logger = logging.getLogger(__name__)

class PatchedBinary(OriginalBinary):

    def create(self, record_values):
        super().create(record_values)
        if not record_values:
            return
        env = record_values[0][0].env
        for record, value in record_values:
            if not value:
                break
            file_bytes = base64.b64decode(value)
            mime = magic.from_buffer(file_bytes, mime=True)
            env['ir.attachment'].sudo().search([
                ('res_model', '=', self.model_name),
                ('res_field', '=', self.name),
                ('res_id', '=', record.id),
            ]).write({'mimetype': mime})

    def write(self, records, value):
        super().write(records, value)
        if not value or not records:
            return
        if self.store and any(records._ids):
            file_bytes = base64.b64decode(value)
            mime = magic.from_buffer(file_bytes, mime=True)
            real_records = records.filtered('id')
            atts = records.env['ir.attachment'].sudo().search([
                ('res_model', '=', self.model_name),
                ('res_field', '=', self.name),
                ('res_id', 'in', real_records.ids),
            ])
            if atts:
                atts.write({'mimetype': mime})

# Override fields.Binary
fields.Binary = PatchedBinary
