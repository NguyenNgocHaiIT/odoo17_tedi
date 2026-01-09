# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ReportPreview(models.TransientModel):
    _name = 'report.preview'
    _description = 'Report Preview'

    name = fields.Char(string="Name")
    action_report_id = fields.Many2one(
        comodel_name='ir.actions.report', string='Action Report')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment', string="Attachments")

    def action_save_model(self):
        if self.attachment_ids and self.action_report_id:
            attachment_id = self.attachment_ids[0]
            model_file_id = self.env[attachment_id.res_model].browse(attachment_id.res_id)
            config_id = False
            if self.action_report_id.report_type == 'xlsx-jinja':
                config_id = self.env['xlsx.report.config'].search([
                    ('action_report_id', '=', self.action_report_id.id)], limit=1)
            elif self.action_report_id.report_type == 'docx':
                config_id = self.env['docx.report.config'].search([
                    ('action_report_id', '=', self.action_report_id.id)], limit=1)

            if model_file_id and config_id:
                if config_id.binary_id:
                    if config_id.binary_id.ttype == 'many2many':
                        model_file_id.write({config_id.binary_id.name: [(6, 0, self.attachment_ids.ids)]})
                    elif config_id.binary_id.ttype == 'many2one':
                        model_file_id.write({config_id.binary_id.name: attachment_id.id})
