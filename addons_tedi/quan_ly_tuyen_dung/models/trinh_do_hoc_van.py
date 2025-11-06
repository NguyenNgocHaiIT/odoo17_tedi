from odoo import api, fields, models, _

class EducationLevel(models.Model):
    _name = "education.level"
    _description = "Education Level"
    _order = "sequence, id"

    sequence = fields.Integer(string="STT sắp xếp", default=1)
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)

    training_major = fields.Char(string="Chuyên ngành đào tạo")
    school = fields.Char(string="Trường đào tạo")
    year_graduation = fields.Char(string="Năm tốt nghiệp")
    professional_qualification = fields.Selection([
        ("bachelor", "Cử nhân"),
        ("engineer", "Kỹ sư"),
        ("master", "Thạc sĩ"),
        ("PhD", "Tiến sĩ"),
    ])
    graduation_type = fields.Selection([
        ("Ordinary", "Trung bình"),
        ("Average_Good", "Trung bình khá"),
        ("Good", "Khá"),
        ("Very_Good", "Giỏi"),
        ("Excellent", "Xuất sắc"),
    ])
    applicant_id = fields.Many2one(
        "hr.applicant", string="Ứng viên",
        ondelete="cascade", index=True, required=True,
    )

    # TÍNH THEO TỪNG ỨNG VIÊN + SEQUENCE (KHÔNG DỰA ID)
    @api.depends(
        "applicant_id",
        "applicant_id.education_level_ids",
        "applicant_id.education_level_ids.sequence",
    )
    def _compute_stt(self):
        for applicant in self.mapped("applicant_id"):
            lines = applicant.education_level_ids.sorted(key=lambda r: (r.sequence or 0))
            for i, line in enumerate(lines, start=1):
                line.stt = i
        for rec in self.filtered(lambda r: not r.applicant_id):
            rec.stt = 0

    # ÉP UI NHẢY SỐ NGAY TRONG INLINE: khi sequence hoặc sibling thay đổi
    @api.onchange(
        "sequence",
        "applicant_id",
        "applicant_id.education_level_ids.sequence",
    )
    def _onchange_reindex_stt(self):
        for rec in self:
            if not rec.applicant_id:
                rec.stt = 0
                continue
            lines = rec.applicant_id.education_level_ids.sorted(key=lambda r: (r.sequence or 0))
            for i, line in enumerate(lines, start=1):
                line.stt = i

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        app_id = self.env.context.get("default_applicant_id")
        if app_id:
            applicant = self.env["hr.applicant"].browse(app_id)
            next_seq = (max(applicant.education_level_ids.mapped("sequence") or [0]) + 1)
            res["sequence"] = next_seq
            # Không bắt buộc set stt ở đây, nhưng set để user thấy số tạm thời:
            res["stt"] = next_seq
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            app_id = vals.get("applicant_id") or self.env.context.get("default_applicant_id")
            if app_id and not vals.get("sequence"):
                applicant = self.env["hr.applicant"].browse(app_id)
                vals["sequence"] = (max(applicant.education_level_ids.mapped("sequence") or [0]) + 1)
        return super().create(vals_list)

