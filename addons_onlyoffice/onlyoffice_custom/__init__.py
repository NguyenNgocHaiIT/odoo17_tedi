# -*- coding: utf-8 -*-

from . import models
from . import controller
from . import wizard

from odoo import api, SUPERUSER_ID

def disable_standard_folder_rule(env):
    rule = env.ref('documents.documents_folder_groups_rule', raise_if_not_found=False)
    rule_document1 = env.ref('documents.documents_document_readonly_rule', raise_if_not_found=False)
    rule_document2 = env.ref('documents.documents_document_write_rule', raise_if_not_found=False)

    rule.write({'active': False})
    rule_document1.write({'active': False})
    rule_document2.write({'active': False})

def restore_standard_folder_rule(env):
    rule = env.ref('documents.documents_folder_groups_rule', raise_if_not_found=False)
    rule_document1 = env.ref('documents.documents_document_readonly_rule', raise_if_not_found=False)
    rule_document2 = env.ref('documents.documents_document_write_rule', raise_if_not_found=False)

    rule.write({'active': True})
    rule_document1.write({'active': True})
    rule_document2.write({'active': True})
