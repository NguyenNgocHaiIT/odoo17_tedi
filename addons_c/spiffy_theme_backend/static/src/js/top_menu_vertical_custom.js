/** @odoo-module **/

(function() {
    'use strict';
    
    console.log('=== COMPANY NAME FINAL ===');
    
    // 1. HÀM CHÍNH - CẬP NHẬT TÊN CÔNG TY
    function updateCompanyName() {
        console.log('[1] Tìm dropdown công ty...');
        
        // TÌM CHÍNH XÁC DROPDOWN CÔNG TY
        const dropdown = document.querySelector('.company_selections .dropdown-toggle');
        if (!dropdown) {
            console.log('[ERROR] Không tìm thấy .company_selections .dropdown-toggle');
            return false;
        }
        
        console.log('[2] Đã tìm thấy dropdown!');
        
        // TÌM CÔNG TY ĐANG ĐƯỢC CHỌN (aria-checked="true")
        console.log('[3] Tìm công ty đang active...');
        const activeToggle = document.querySelector('.toggle_company[aria-checked="true"]');
        let companyName = 'Công ty';
        
        if (activeToggle) {
            console.log('[4] Tìm thấy toggle active:', activeToggle);
            
            // TÌM TÊN CÔNG TY TRONG .company_label
            const companyLabel = activeToggle.closest('.dropdown-item').querySelector('.company_label');
            if (companyLabel) {
                companyName = companyLabel.textContent.trim();
                console.log('[5] Tên công ty:', companyName);
            }
        } else {
            console.log('[WARNING] Không tìm thấy công ty nào đang active');
        }
        
        // XÓA TÊN CŨ NẾU CÓ
        console.log('[6] Xóa tên cũ...');
        const oldNames = dropdown.querySelectorAll('.display-company-name');
        oldNames.forEach(el => el.remove());
        
        // TẠO PHẦN TỬ HIỂN THỊ TÊN MỚI
        console.log('[7] Tạo phần tử tên mới...');
        const nameSpan = document.createElement('span');
        nameSpan.className = 'display-company-name';
        nameSpan.textContent = companyName;
        
        // THÊM STYLE
        Object.assign(nameSpan.style, {
            marginLeft: '8px',
            fontSize: '14px',
            fontWeight: '500',
            whiteSpace: 'nowrap',
            color: '#333',
            display: 'inline-block',
            verticalAlign: 'middle'
        });
        
        // CHÈN VÀO SAU ICON BUILDING
        console.log('[8] Chèn vào DOM...');
        const icon = dropdown.querySelector('i.ri-building-2-line');
        if (icon) {
            // Chèn vào sau icon (trong cùng .oe_topbar_name)
            icon.parentNode.insertBefore(nameSpan, icon.nextSibling);
            console.log('[9] Đã chèn sau icon');
        } else {
            console.log('[ERROR] Không tìm thấy icon');
            return false;
        }
        
        console.log('[SUCCESS] Đã cập nhật tên công ty:', companyName);
        return true;
    }
    
    // 2. HÀM THÊM CSS
    function addCompanyStyles() {
        if (document.querySelector('#company-name-css')) return;
        
        const style = document.createElement('style');
        style.id = 'company-name-css';
        style.textContent = `
            /* Hiển thị tên công ty */
            .display-company-name {
                margin-left: 8px !important;
                font-size: 14px !important;
                font-weight: 500 !important;
                white-space: nowrap !important;
                color: #333 !important;
                display: inline-block !important;
                vertical-align: middle !important;
                max-width: 150px !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            
            /* Đảm bảo dropdown đủ rộng */
            .company_selections .dropdown-toggle {
                min-width: 140px !important;
                display: inline-flex !important;
                align-items: center !important;
                padding-right: 12px !important;
            }
            
            /* Dark mode */
            body.dark_mode .display-company-name {
                color: #fff !important;
            }
            
            /* Hover effect */
            .company_selections .dropdown-toggle:hover .display-company-name {
                color: var(--biz-theme-primary-color) !important;
            }
        `;
        
        document.head.appendChild(style);
        console.log('Đã thêm CSS');
    }
    
    // 3. HÀM KHỞI TẠO
    function initialize() {
        console.log('=== KHỞI TẠO ===');
        
        // Thêm CSS
        addCompanyStyles();
        
        // Thử cập nhật tên công ty (thử nhiều lần)
        let attempts = 0;
        const maxAttempts = 15;
        
        function tryUpdate() {
            attempts++;
            console.log(`Thử lần ${attempts}/${maxAttempts}`);
            
            if (updateCompanyName()) {
                console.log('=== THÀNH CÔNG ===');
                setupEventListeners();
            } else if (attempts < maxAttempts) {
                console.log('Sẽ thử lại sau 500ms...');
                setTimeout(tryUpdate, 500);
            } else {
                console.log('=== THẤT BẠI ===');
            }
        }
        
        // Bắt đầu sau 300ms
        setTimeout(tryUpdate, 300);
    }
    
    // 4. THIẾT LẬP EVENT LISTENERS
    function setupEventListeners() {
        console.log('Thiết lập event listeners...');
        
        // LẮNG NGHE CLICK VÀO CÔNG TY
        document.addEventListener('click', function(event) {
            const target = event.target;
            
            // Nếu click vào toggle_company hoặc log_into
            if (target.closest('.toggle_company') || target.closest('.log_into')) {
                console.log('Đã click chọn công ty, cập nhật tên...');
                setTimeout(updateCompanyName, 100);
            }
        });
        
        // THEO DÕI THAY ĐỔI aria-checked
        const observer = new MutationObserver(function(mutations) {
            for (const mutation of mutations) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'aria-checked') {
                    console.log('aria-checked thay đổi, cập nhật tên...');
                    setTimeout(updateCompanyName, 50);
                    break;
                }
            }
        });
        
        // QUAN SÁT TẤT CẢ TOGGLE COMPANY
        const toggles = document.querySelectorAll('.toggle_company');
        console.log(`Quan sát ${toggles.length} toggle company`);
        
        toggles.forEach(toggle => {
            observer.observe(toggle, {
                attributes: true,
                attributeFilter: ['aria-checked']
            });
        });
        
        console.log('Event listeners đã sẵn sàng');
    }
    
    // 5. KHỞI ĐỘNG
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
    
    // 6. XUẤT HÀM ĐỂ DEBUG
    window.debugUpdateCompany = updateCompanyName;
    
    console.log('=== MODULE ĐÃ SẴN SÀNG ===');
    console.log('Dùng debugUpdateCompany() để test thủ công');
    
})();