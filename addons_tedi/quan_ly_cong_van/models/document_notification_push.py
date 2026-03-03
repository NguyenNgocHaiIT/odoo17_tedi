# -*- coding: utf-8 -*-
"""
Tích hợp Web Push Notification vào module Quản lý Công văn.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


# ============================================================
# HELPER FUNCTIONS — không dùng mixin class để tránh lỗi Odoo
# ============================================================

def _push_to_employees(env, employees, title, body):
    """Gửi Web Push cho danh sách hr.employee có fcm_token."""
    try:
        users = env['res.users']
        for emp in employees:
            if emp.user_id and emp.user_id.fcm_token:
                users |= emp.user_id
        if users:
            users.send_push_notification(title, body)
            _logger.info(
                f"[WebPush] '{title}' → {len(users)} người: "
                f"{', '.join(users.mapped('name'))}"
            )
    except Exception as e:
        _logger.error(f"[WebPush] Lỗi gửi push đến employees: {e}")


def _push_to_users(env, users, title, body):
    """Gửi Web Push cho danh sách res.users có fcm_token."""
    try:
        users_with_token = users.filtered(lambda u: u.fcm_token)
        if users_with_token:
            users_with_token.send_push_notification(title, body)
            _logger.info(
                f"[WebPush] '{title}' → {len(users_with_token)} user"
            )
    except Exception as e:
        _logger.error(f"[WebPush] Lỗi gửi push đến users: {e}")


def _push_to_group(env, group_xml_id, title, body):
    """Gửi Web Push cho tất cả thành viên có fcm_token trong một security group."""
    try:
        group = env.ref(group_xml_id, raise_if_not_found=False)
        if not group:
            return
        users = group.users.filtered(lambda u: u.fcm_token)
        if users:
            users.send_push_notification(title, body)
            _logger.info(
                f"[WebPush] '{title}' → nhóm '{group_xml_id}' ({len(users)} người)"
            )
    except Exception as e:
        _logger.error(f"[WebPush] Lỗi gửi push đến nhóm {group_xml_id}: {e}")


# ============================================================
# OVERRIDE: OfficeDocument
# ============================================================

class OfficeDocumentPush(models.Model):
    _inherit = 'office.document'

    # ----------------------------------------------------------
    # 1. TRÌNH TRƯỞNG ĐƠN VỊ
    # ----------------------------------------------------------
    def trinh_truong_don_vi(self):
        result = super().trinh_truong_don_vi()
        if self.truong_don_vi_duyet:
            _push_to_employees(
                self.env,
                self.truong_don_vi_duyet,
                "📋 Văn bản cần duyệt",
                f"Văn bản '{self.trich_yeu[:60]}' cần bạn duyệt."
                if self.trich_yeu else "Có văn bản mới cần bạn duyệt.",
            )
        return result

    # ----------------------------------------------------------
    # 2. TRÌNH LÃNH ĐẠO — công văn đi (chờ duyệt)
    # ----------------------------------------------------------
    def trinh_lanh_dao_cong_van_di(self):
        result = super().trinh_lanh_dao_cong_van_di()
        if self.lanh_dao_theo_doi:
            _push_to_employees(
                self.env,
                self.lanh_dao_theo_doi,
                "📋 Văn bản cần duyệt",
                f"Văn bản '{self.trich_yeu[:60]}' đang chờ bạn duyệt."
                if self.trich_yeu else "Có văn bản đang chờ duyệt.",
            )
        return result

    # ----------------------------------------------------------
    # 3. TRÌNH LÃNH ĐẠO — công văn đi (bút phê)
    # ----------------------------------------------------------
    def trinh_lanh_dao_cong_van_di_but_phe(self):
        result = super().trinh_lanh_dao_cong_van_di_but_phe()
        if self.lanh_dao_theo_doi:
            _push_to_employees(
                self.env,
                self.lanh_dao_theo_doi,
                "✍️ Văn bản cần bút phê",
                f"Văn bản '{self.trich_yeu[:60]}' cần bạn bút phê."
                if self.trich_yeu else "Có văn bản cần bút phê.",
            )
        return result

    # ----------------------------------------------------------
    # 4. TRÌNH LÃNH ĐẠO — công văn đến (bút phê)
    # ----------------------------------------------------------
    def trinh_lanh_dao_cong_van_den(self):
        result = super().trinh_lanh_dao_cong_van_den()
        if self.lanh_dao_xu_ly:
            _push_to_employees(
                self.env,
                self.lanh_dao_xu_ly,
                "✍️ Văn bản cần bút phê",
                f"Văn bản '{self.trich_yeu[:60]}' cần bạn bút phê/xử lý."
                if self.trich_yeu else "Có văn bản cần bút phê.",
            )
        return result

    # ----------------------------------------------------------
    # 5. DUYỆT VĂN BẢN
    # ----------------------------------------------------------
    def approve(self):
        result = super().approve()
        body = (
            f"Văn bản '{self.trich_yeu[:60]}' đã được duyệt."
            if self.trich_yeu else "Văn bản của bạn đã được duyệt."
        )
        # Thông báo người tạo
        _push_to_users(self.env, self.create_uid, "✅ Văn bản đã được duyệt", body)
        # Thông báo văn thư
        _push_to_group(
            self.env,
            'quan_ly_cong_van.group_van_thu',
            "✅ Văn bản đã duyệt — cần xử lý tiếp",
            body,
        )
        return result

    # ----------------------------------------------------------
    # 6. DUYỆT ĐƠN VỊ (Trưởng đơn vị duyệt)
    # ----------------------------------------------------------
    def approve_don_vi(self):
        result = super().approve_don_vi()
        _push_to_users(
            self.env,
            self.create_uid,
            "✅ Trưởng đơn vị đã duyệt",
            f"Văn bản '{self.trich_yeu[:60]}' đã được trưởng đơn vị duyệt."
            if self.trich_yeu else "Văn bản đã được trưởng đơn vị duyệt.",
        )
        return result

    # ----------------------------------------------------------
    # 7. XÁC NHẬN (submit lên văn thư)
    # ----------------------------------------------------------
    def xac_nhan(self):
        result = super().xac_nhan()
        user = self.env.user
        if not user.has_group('quan_ly_cong_van.group_van_thu'):
            _push_to_group(
                self.env,
                'quan_ly_cong_van.group_van_thu',
                "📬 Văn bản mới cần duyệt",
                f"'{self.trich_yeu[:60]}' vừa được xác nhận, chờ duyệt."
                if self.trich_yeu else "Có văn bản mới chờ duyệt.",
            )
        return result

    # ----------------------------------------------------------
    # 8. PHÁT HÀNH
    # ----------------------------------------------------------
    def phat_hanh(self):
        result = super().phat_hanh()
        body = (
            f"Văn bản '{self.trich_yeu[:60]}' đã chính thức phát hành."
            if self.trich_yeu else "Văn bản đã được phát hành."
        )
        _push_to_users(self.env, self.create_uid, "🚀 Văn bản đã phát hành", body)
        if self.nguoi_xu_ly_chinh:
            _push_to_employees(
                self.env, self.nguoi_xu_ly_chinh, "🚀 Văn bản đã phát hành", body
            )
        return result

    # ----------------------------------------------------------
    # 9. HỦY
    # ----------------------------------------------------------
    def huy(self):
        result = super().huy()
        _push_to_users(
            self.env,
            self.create_uid,
            "🚫 Văn bản đã hủy",
            f"Văn bản '{self.trich_yeu[:60]}' đã bị hủy."
            if self.trich_yeu else "Văn bản đã bị hủy.",
        )
        return result


# ============================================================
# OVERRIDE: PhanPhat Wizard
# ============================================================

class PhanPhatPush(models.TransientModel):
    _inherit = 'office.document.phan.phat'

    def phan_phat(self):
        result = super().phan_phat()

        doc_id = self.env.context.get('active_id')
        if not doc_id:
            return result
        doc = self.env['office.document'].browse(doc_id)
        if not doc.exists():
            return result

        # Tổng hợp người nhận
        nguoi_xu_ly_chinh_ids = []
        nguoi_dong_xu_ly_ids = []
        if self.loai_phan_phat in ('don_vi', 'ca_hai'):
            nguoi_xu_ly_chinh_ids += self.nguoi_xu_ly_chinh.ids
            nguoi_dong_xu_ly_ids += self.nguoi_dong_xu_ly.ids
        if self.loai_phan_phat in ('ca_nhan', 'ca_hai'):
            nguoi_xu_ly_chinh_ids += self.ca_nhan_xu_ly_chinh.ids
            nguoi_dong_xu_ly_ids += self.ca_nhan_dong_xu_ly.ids

        all_ids = list(set(nguoi_xu_ly_chinh_ids + nguoi_dong_xu_ly_ids))
        if all_ids:
            employees = self.env['hr.employee'].browse(all_ids)
            _push_to_employees(
                self.env,
                employees,
                "📄 Văn bản mới được phân phát",
                f"Bạn được giao xử lý: {doc.trich_yeu[:80]}"
                if doc.trich_yeu else "Bạn vừa được phân công xử lý văn bản.",
            )
        return result


# ============================================================
# OVERRIDE: ButPhe Wizard
# ============================================================

class ButPhePush(models.TransientModel):
    _inherit = 'office.document.but.phe'

    def but_phe(self):
        # Lấy trich_yeu trước khi gọi super (phòng ngừa context thay đổi)
        doc_id = self.env.context.get('active_id')
        trich_yeu = ''
        if doc_id:
            doc = self.env['office.document'].browse(doc_id)
            if doc.exists():
                trich_yeu = doc.trich_yeu or ''

        result = super().but_phe()

        _push_to_group(
            self.env,
            'quan_ly_cong_van.group_van_thu',
            "✍️ Văn bản đã bút phê",
            f"Văn bản '{trich_yeu[:60]}' đã bút phê, chờ phân phát."
            if trich_yeu else "Có văn bản vừa được bút phê, chờ phân phát.",
        )
        return result


# ============================================================
# OVERRIDE: RejectDocumentWizard (văn thư từ chối)
# ============================================================

class RejectDocumentWizardPush(models.TransientModel):
    _inherit = 'office.document.reject.wizard'

    def action_confirm_reject(self):
        doc = self.office_document_id
        creator = doc.create_uid
        trich_yeu = doc.trich_yeu or ''

        result = super().action_confirm_reject()

        _push_to_users(
            self.env,
            creator,
            "❌ Văn bản bị từ chối",
            f"Văn bản '{trich_yeu[:60]}' đã bị từ chối. Vui lòng chỉnh sửa lại."
            if trich_yeu else "Văn bản của bạn đã bị từ chối.",
        )
        return result


# ============================================================
# OVERRIDE: LanhDaoRejectWizard (lãnh đạo từ chối)
# ============================================================

class LanhDaoRejectWizardPush(models.TransientModel):
    _inherit = 'office.document.lanh.dao.reject.wizard'

    def action_confirm_reject(self):
        doc = self.office_document_id
        creator = doc.create_uid
        truong_don_vi = doc.truong_don_vi_duyet
        trich_yeu = doc.trich_yeu or ''

        result = super().action_confirm_reject()

        # Push cho người tạo
        _push_to_users(
            self.env,
            creator,
            "❌ Văn bản bị lãnh đạo từ chối",
            f"Văn bản '{trich_yeu[:60]}' bị từ chối, chờ trưởng đơn vị duyệt lại."
            if trich_yeu else "Văn bản của bạn bị lãnh đạo từ chối.",
        )

        # Push cho trưởng đơn vị
        if truong_don_vi:
            _push_to_employees(
                self.env,
                truong_don_vi,
                "⚠️ Văn bản cần duyệt lại",
                f"Văn bản '{trich_yeu[:60]}' bị lãnh đạo từ chối, cần bạn xem xét lại."
                if trich_yeu else "Có văn bản bị từ chối, cần bạn duyệt lại.",
            )
        return result


# ============================================================
# OVERRIDE: ChuyenLanhDaoWizard
# ============================================================

class ChuyenLanhDaoWizardPush(models.TransientModel):
    _inherit = 'office.document.chuyen.lanh.dao'

    def action_chuyen(self):
        lanh_dao_moi = self.lanh_dao_moi_id
        trich_yeu = self.office_document_id.trich_yeu or ''

        result = super().action_chuyen()

        if lanh_dao_moi:
            _push_to_employees(
                self.env,
                lanh_dao_moi,
                "🔄 Được chuyển xử lý văn bản",
                f"Bạn vừa được chuyển xử lý: '{trich_yeu[:60]}'."
                if trich_yeu else "Bạn vừa được chuyển xử lý một văn bản.",
            )
        return result