from odoo import api, fields, models, _

class TrainingProcess(models.Model):
    _name = "training.process"
    _description = "Quá trình đào tạo"
    _order = "sequence, id"  # sắp theo sequence trước, giống plan detail

    sequence = fields.Integer(string="STT sắp xếp", default=1)
    stt = fields.Integer(string="STT", compute="_compute_stt", store=False, readonly=True)

    training_name = fields.Char(string="Tên khoá đào tạo")
    training_location = fields.Char(string="Cơ sở đào tạo")
    start_date = fields.Date(string="Từ ngày")
    end_date = fields.Date(string="Đến ngày")
    result_state = fields.Selection([
        ("pending", "Chưa đánh giá"),
        ("passed", "Đạt"),
        ("failed", "Không đạt"),
        ("cert_issued", "Đã cấp chứng chỉ"),
    ], default="pending", string="Kết quả")

    applicant_id = fields.Many2one(
        "hr.applicant", string="Ứng viên",
        ondelete="cascade", index=True, required=True,
    )

    # ====== Core: đánh số theo từng applicant + sequence (không dựa id) ======
    @api.depends(
        "applicant_id",
        "applicant_id.training_process_ids",
        "applicant_id.training_process_ids.sequence",
    )
    def _compute_stt(self):
        for applicant in self.mapped("applicant_id"):
            lines = applicant.training_process_ids.sorted(key=lambda r: (r.sequence or 0))
            for i, line in enumerate(lines, start=1):
                line.stt = i
        for rec in self.filtered(lambda r: not r.applicant_id):
            rec.stt = 0

    # Ép UI nhảy số ngay trong inline khi đổi sequence/thêm dòng mới
    @api.onchange(
        "sequence",
        "applicant_id",
        "applicant_id.training_process_ids.sequence",
    )
    def _onchange_reindex_stt(self):
        for rec in self:
            if not rec.applicant_id:
                rec.stt = 0
                continue
            lines = rec.applicant_id.training_process_ids.sorted(key=lambda r: (r.sequence or 0))
            for i, line in enumerate(lines, start=1):
                line.stt = i

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        applicant_id = self.env.context.get("default_applicant_id")
        if applicant_id:
            applicant = self.env["hr.applicant"].browse(applicant_id)
            next_seq = (max(applicant.training_process_ids.mapped("sequence") or [0]) + 1)
            res["sequence"] = next_seq
            # có thể bỏ nếu không muốn số tạm; compute/onchange sẽ đè lại:
            res["stt"] = next_seq
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # hỗ trợ tạo nhiều dòng; tự set sequence tăng dần theo từng applicant
        for vals in vals_list:
            app_id = vals.get("applicant_id") or self.env.context.get("default_applicant_id")
            if app_id and not vals.get("sequence"):
                applicant = self.env["hr.applicant"].browse(app_id)
                vals["sequence"] = (max(applicant.training_process_ids.mapped("sequence") or [0]) + 1)
        return super().create(vals_list)


