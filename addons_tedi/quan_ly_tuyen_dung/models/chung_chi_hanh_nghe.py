from odoo import api, fields, models, _

class ProfessorLicense(models.Model):
    _name = "professor.license"
    _description = "Chứng chỉ hành nghề"
    _order = "sequence, id"  # giống plan detail: sắp theo sequence trước

    sequence = fields.Integer(string="STT sắp xếp", default=1)
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)

    name = fields.Char(string="Tên chứng chỉ")
    code = fields.Char(string="Mã chứng chỉ")
    license_place = fields.Char(string="Nơi cấp phép")
    start_date = fields.Date(string="Từ ngày")
    end_date = fields.Date(string="Đến ngày")

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "license_attachment_rel",
        "professor_licenseId", "attachment_id",
        string="Tài liệu đính kèm",
    )

    applicant_id = fields.Many2one(
        "hr.applicant", string="Ứng viên",
        ondelete="cascade", index=True, required=True,
    )

    # ====== Core: đánh số theo từng applicant + sequence (không dựa id) ======
    @api.depends(
        "applicant_id",
        "applicant_id.professor_license_ids",
        "applicant_id.professor_license_ids.sequence",
    )
    def _compute_stt(self):
        for applicant in self.mapped("applicant_id"):
            lines = applicant.professor_license_ids.sorted(key=lambda r: (r.sequence or 0))
            for i, line in enumerate(lines, start=1):
                line.stt = i
        for rec in self.filtered(lambda r: not r.applicant_id):
            rec.stt = 0

    # ÉP UI nhảy số ngay khi thêm/sửa inline
    @api.onchange(
        "sequence",
        "applicant_id",
        "applicant_id.professor_license_ids.sequence",
    )
    def _onchange_reindex_stt(self):
        for rec in self:
            if not rec.applicant_id:
                rec.stt = 0
                continue
            lines = rec.applicant_id.professor_license_ids.sorted(key=lambda r: (r.sequence or 0))
            for i, line in enumerate(lines, start=1):
                line.stt = i

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        applicant_id = self.env.context.get("default_applicant_id")
        if applicant_id:
            applicant = self.env["hr.applicant"].browse(applicant_id)
            next_seq = (max(applicant.professor_license_ids.mapped("sequence") or [0]) + 1)
            res["sequence"] = next_seq
            # có thể bỏ dòng dưới nếu không muốn số tạm; compute/onchange sẽ đè lại:
            res["stt"] = next_seq
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # hỗ trợ tạo nhiều dòng, tự set sequence tăng dần theo từng applicant
        for vals in vals_list:
            app_id = vals.get("applicant_id") or self.env.context.get("default_applicant_id")
            if app_id and not vals.get("sequence"):
                applicant = self.env["hr.applicant"].browse(app_id)
                vals["sequence"] = (max(applicant.professor_license_ids.mapped("sequence") or [0]) + 1)
        return super().create(vals_list)


