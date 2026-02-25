# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import xlsxwriter
import io
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


class ThanhToanXeController(http.Controller):

    @http.route('/web/binary/download_thanh_toan_report', type='http', auth="user")
    def download_thanh_toan_report(self, vehicle_id, report_type, month=None, year=None, start_date=None, end_date=None,
                                   **kwargs):
        """Xuất file Excel báo cáo thanh toán"""

        # Lấy dữ liệu
        vehicle = request.env['fleet.vehicle'].browse(int(vehicle_id))
        report_type = report_type

        # Xử lý khoảng thời gian
        if report_type == 'monthly':
            month = int(month)
            year = int(year)
            start_date = datetime(year, month, 1)
            end_date = datetime(year, month, 1) + relativedelta(months=1)
            period_title = f"THÁNG {month} NĂM {year}"
        else:  # period
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d') + relativedelta(days=1)  # Thêm 1 ngày
            period_title = f"TỪ {start_date.strftime('%d/%m/%Y')} ĐẾN {end_date.strftime('%d/%m/%Y')}"

        # Tạo hoặc lấy báo cáo
        if report_type == 'monthly':
            report_domain = [
                ('vehicle_id', '=', vehicle.id),
                ('month', '=', month),
                ('year', '=', year),
                ('report_type', '=', 'monthly')
            ]
        else:
            report_domain = [
                ('vehicle_id', '=', vehicle.id),
                ('start_date_period', '=', start_date.date()),
                ('end_date_period', '=', end_date.date() - relativedelta(days=1)),  # Trừ lại 1 ngày
                ('report_type', '=', 'period')
            ]

        report = request.env['fleet.vehicle.odometer'].search(report_domain, limit=1)

        if not report:
            # Tạo báo cáo mới nếu chưa có
            report_vals = {
                'vehicle_id': vehicle.id,
                'report_type': report_type,
            }

            if report_type == 'monthly':
                report_vals.update({
                    'month': month,
                    'year': year,
                })
            else:
                report_vals.update({
                    'start_date_period': start_date.date(),
                    'end_date_period': end_date.date() - relativedelta(days=1),
                })

            report = request.env['fleet.vehicle.odometer'].create(report_vals)
            report.action_calculate_data()

        # Lấy danh sách chuyến đi trong khoảng thời gian
        trips = request.env['hr_tedi.vehicle.registration'].search([
            ('assigned_vehicle_id', '=', vehicle.id),
            ('state', '=', 'done'),
            ('end_date', '>=', start_date),
            ('end_date', '<', end_date)
        ], order='start_date asc')

        # Tạo file Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Báo cáo')

        # Định dạng
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        cell_format = workbook.add_format({
            'border': 1,
            'valign': 'vcenter'
        })

        center_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        no_border_cell_format = workbook.add_format({
            'valign': 'vcenter'
        })

        no_border_center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter'
        })

        no_border_number_format = workbook.add_format({
            'num_format': '#,##0.00',
            'valign': 'vcenter'
        })

        # Thiết lập độ rộng cột
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:C', 25)
        worksheet.set_column('D:D', 25)
        worksheet.set_column('E:E', 35)
        worksheet.set_column('F:F', 25)
        worksheet.set_column('G:G', 40)
        worksheet.set_column('H:H', 15)

        # Tiêu đề chính
        worksheet.merge_range('A1:H1', 'THANH TOÁN CHỐT CÂY SỐ XE', title_format)
        title = f"{vehicle.model_id.brand_id.name or ''} {vehicle.model_id.name or ''} ({vehicle.license_plate or ''} - {vehicle.tedi_driver_employee_id.name or vehicle.driver_id.name or 'Chưa có tài xế'}) {period_title}"
        worksheet.merge_range('A2:H2', title, title_format)

        # Thông tin số km
        row = 4
        worksheet.write(row, 1, f"Số km đầu: {report.odometer_start:,.0f}", no_border_cell_format)
        worksheet.write(row, 6, f"Số km cuối: {report.value:,.0f}", no_border_cell_format)

        row += 1
        worksheet.write(row, 1, f"Số km theo đồng hồ: {report.speedometer_total:,.0f}", no_border_cell_format)
        worksheet.write(row, 6, f"Số km theo thực tế: {report.odometer_total:,.0f}", no_border_cell_format)

        row += 2
        if report_type == 'monthly':
            title_table = f"Quá trình đăng ký xe tháng {month} năm {year}"
        else:
            start_display = start_date.strftime('%d/%m/%Y')
            end_display = (end_date - relativedelta(days=1)).strftime('%d/%m/%Y')
            title_table = f"Quá trình đăng ký xe từ {start_display} đến {end_display}"

        worksheet.write(row, 0, title_table, no_border_cell_format)

        # Tiêu đề bảng chi tiết
        row += 2
        headers = ['STT', 'Ngày đăng ký', 'Giờ đăng ký', 'Ngày về', 'Người đăng ký', 'Nơi đến', 'Nội dung công việc',
                   'Số km đi']

        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)

        # Dữ liệu chi tiết chuyến đi
        row += 1
        stt = 1
        for trip in trips:
            worksheet.write(row, 0, stt, center_format)
            worksheet.write(row, 1, trip.start_date.strftime('%d/%m/%Y') if trip.start_date else '', center_format)
            worksheet.write(row, 2, trip.start_date.strftime('%H:%M') if trip.start_date else '', center_format)
            worksheet.write(row, 3, trip.end_date.strftime('%d/%m/%Y') if trip.end_date else '', center_format)
            worksheet.write(row, 4, trip.requester_id.name or '', cell_format)
            worksheet.write(row, 5, trip.destination or '', cell_format)
            worksheet.write(row, 6, trip.work_content or '', cell_format)
            worksheet.write(row, 7, trip.distance_km, cell_format)

            row += 1
            stt += 1

        # Tổng kết
        row += 2
        worksheet.write(row, 0, f"1. Tổng số km thực tế đã đi: {report.odometer_total:,.0f} km", no_border_cell_format)

        row += 1
        worksheet.write(row, 0, f"- Số km đi nội tỉnh: {report.km_noi_tinh:,.0f} km", no_border_cell_format)

        row += 1
        worksheet.write(row, 0, f"- Số km đi ngoại tỉnh: {report.km_ngoai_tinh:,.0f} km", no_border_cell_format)

        row += 1
        worksheet.write(row, 0, f"2. Định mức xăng theo quy định: {vehicle.fuel_rate or 0} lít / 100 km",
                        no_border_cell_format)

        row += 1
        worksheet.write(row, 0, f"- Số xăng được thanh toán: {report.xang_duoc_thanh_toan:,.2f} lít",
                        no_border_cell_format)

        row += 1
        worksheet.write(row, 0, f"3. Định mức dầu theo quy định: {vehicle.oil_change_rate or 0} lít / 3,000 km",
                        no_border_cell_format)

        row += 1
        worksheet.write(row, 0, f"- Số dầu được thanh toán: {report.dau_duoc_thanh_toan:,.2f} lít",
                        no_border_cell_format)

        # Chữ ký
        current_date = datetime.now()
        day = current_date.day
        month_str = current_date.month
        year_str = current_date.year
        date_text = f'Hà Nội, ngày {day:02d} tháng {month_str:02d} năm {year_str}'

        row += 3
        worksheet.write(row, 6, date_text, no_border_center_format)

        row += 1
        worksheet.write(row, 2, 'Chánh văn phòng', no_border_center_format)
        worksheet.write(row, 6, 'Người lập biểu', no_border_center_format)

        workbook.close()
        output.seek(0)

        # Trả về file
        if report_type == 'monthly':
            filename = f'Thanh_toan_xe_{vehicle.license_plate}_{month}_{year}.xlsx'
        else:
            start_str = start_date.strftime('%Y%m%d')
            end_str = (end_date - relativedelta(days=1)).strftime('%Y%m%d')
            filename = f'Thanh_toan_xe_{vehicle.license_plate}_{start_str}_{end_str}.xlsx'

        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"')
            ]
        )