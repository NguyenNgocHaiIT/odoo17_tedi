# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DocumentDirectory(models.Model):
    _name = "document.directory"
    _description = "Document Directory"
    _inherit = ['avatar.mixin', 'mail.thread']
    _order = "name"
    _rec_name = 'complete_name'
    _parent_store = True

    name = fields.Char('Directory Name', required=True, translate=True)
    complete_name = fields.Char('Complete Name', compute='_compute_complete_name', recursive=True, store=True)
    tag_ids = fields.Many2many(
        comodel_name='directory.tag',
        relation='document_directory_tag_rel', column1='directory_id', column2='tag_id',
        string="Tags")
    model_id = fields.Many2one('ir.model', 'Related Model', required=False, index=True)
    model = fields.Char(string='Model Name', related='model_id.model', store=True, readonly=True)
    active = fields.Boolean('Active', default=True)
    visible_directory = fields.Boolean('Visible Directory', default=False)
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
    parent_id = fields.Many2one('document.directory', string='Parent Directory', index=True, check_company=True)
    child_ids = fields.One2many('document.directory', 'parent_id', string='Child Directories')
    attachment_ids = fields.One2many('ir.attachment', 'document_directory_id', string='Attachments', readonly=False)
    total_attachment = fields.Integer(compute='_compute_total_attachment', string='Total Attachment')
    total_sub_directory = fields.Integer(compute='_compute_total_sub_directory', string='Total Sub Directories')
    note = fields.Text('Note')
    color = fields.Integer('Color Index')
    parent_path = fields.Char(index=True, unaccent=False)
    master_document_directory_id = fields.Many2one(
        'document.directory', 'Master Directory', compute='_compute_master_directory_id', store=True)

    user_ids = fields.Many2many('res.users', 'document_directory_users_rel', 'directory_id', 'uid', string="Users")

    _sql_constraints = [
        ('directory_model_uniq', 'unique(model_id)', "Directory for this model already exists!"),
    ]

    @api.depends_context('hierarchical_naming')
    def _compute_display_name(self):
        if self.env.context.get('hierarchical_naming', True):
            return super()._compute_display_name()
        for record in self:
            record.display_name = record.name

    @api.model
    def name_create(self, name):
        record = self.create({'name': name})
        return record.id, record.display_name

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for directory in self:
            if directory.parent_id:
                directory.complete_name = '%s / %s' % (directory.parent_id.complete_name, directory.name)
            else:
                directory.complete_name = directory.name

    @api.depends('parent_path')
    def _compute_master_document_directory_id(self):
        for directory in self:
            directory.master_document_directory_id = int(directory.parent_path.split('/')[0])

    def _compute_total_attachment(self):
        attachments = self.env['ir.attachment']._read_group([('document_directory_id', 'in', self.ids)],
                                                            ['document_directory_id'], ['__count'])
        result = {attachment.id: count for attachment, count in attachments}
        for directory in self:
            directory.total_attachment = result.get(directory.id, 0)

    def _compute_total_sub_directory(self):
        records = self._read_group([('parent_id', 'in', self.ids)],
                                   ['parent_id'], ['__count'])
        result = {record.id: count for record, count in records}
        for directory in self:
            directory.total_sub_directory = result.get(directory.id, 0)

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive document_directories.'))

    @api.model_create_multi
    def create(self, vals_list):
        # TDE note: auto-subscription of manager done by hand, because currently
        # the tracking allows to track+subscribe fields linked to a res.user record
        # An update of the limited behavior should come, but not currently done.
        document_directories = super(DocumentDirectory, self.with_context(mail_create_nosubscribe=True)).create(vals_list)
        return document_directories

    def write(self, vals):
        return super(DocumentDirectory, self).write(vals)

    def get_children_document_directory_ids(self):
        return self.env['document.directory'].search([('id', 'child_of', self.ids)])

    def get_document_directory_hierarchy(self):
        if not self:
            return {}

        hierarchy = {
            'parent': {
                'id': self.parent_id.id,
                'name': self.parent_id.name,
                'attachment': self.parent_id.total_attachment,
            } if self.parent_id else False,
            'self': {
                'id': self.id,
                'name': self.name,
                'attachment': self.total_attachment,
            },
            'children': [
                {
                    'id': child.id,
                    'name': child.name,
                    'attachment': child.total_attachment
                } for child in self.child_ids
            ]
        }

        return hierarchy
