/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchPanel } from "@web/search/search_panel/search_panel";

// Global variable để lưu strict mode state
let strictDirectoryState = {
    enabled: false,
    currentDirectory: null
};

patch(SearchPanel.prototype, {
    /**
     * Override setup để kiểm tra context
     */
    setup() {
        super.setup();

        console.log("SearchPanel initialized");

        // Kiểm tra context khi component mount
        this._checkStrictModeContext();
    },

    /**
     * Kiểm tra strict mode từ context
     */
    _checkStrictModeContext() {
        try {
            // Lấy context từ nhiều nguồn
            const sources = [
                () => this.env.services.action?.currentController?.context,
                () => this.env.services.action?.currentAction?.context,
                () => {
                    const urlParams = new URLSearchParams(window.location.hash.split('?')[1] || '');
                    const contextStr = urlParams.get('context');
                    return contextStr ? JSON.parse(contextStr) : {};
                }
            ];

            for (const getContext of sources) {
                try {
                    const context = getContext();
                    if (context && context.strict_directory_filter !== undefined) {
                        strictDirectoryState.enabled = context.strict_directory_filter;
                        console.log("Strict mode from context:", strictDirectoryState.enabled);
                        break;
                    }
                } catch (e) {
                    // Continue to next source
                }
            }
        } catch (error) {
            console.warn("Error checking strict mode context:", error);
        }
    },

    /**
     * Xử lý khi click category
     */
    async _onCategoryValueClick(category, valueId) {
        // Lưu ID directory hiện tại
        if (category.fieldName === "document_directory_id") {
            strictDirectoryState.currentDirectory = valueId;
        }

        // Gọi phương thức gốc
        await super._onCategoryValueClick(category, valueId);

        // Áp dụng strict filter nếu cần
        this._maybeApplyStrictFilter(category, valueId);
    },

    /**
     * Áp dụng strict filter nếu đang ở strict mode
     */
    _maybeApplyStrictFilter(category, valueId) {
        if (category.fieldName !== "document_directory_id" ||
            !strictDirectoryState.enabled ||
            !valueId) {
            return;
        }

        console.log(`Strict mode enabled for directory ${valueId}`);

        // Tìm và cập nhật search domain
        // Sử dụng setTimeout để đảm bảo search đã được thực hiện
        setTimeout(() => {
            this._updateSearchDomain(valueId);
        }, 100);
    },

    /**
     * Cập nhật search domain
     */
    _updateSearchDomain(directoryId) {
        // Tìm tất cả các component có thể có searchModel
        const components = document.querySelectorAll('[data-search-model]');

        if (components.length > 0) {
            // Thử từ component đầu tiên
            const component = components[0];
            const searchModel = component.__owl__?.searchModel;

            if (searchModel) {
                console.log("Found searchModel in DOM component");
                this._applyDomainToSearchModel(searchModel, directoryId);
                return;
            }
        }

        // Thử từ window (nếu searchModel được lưu global)
        if (window.__searchModel__) {
            console.log("Found searchModel in window");
            this._applyDomainToSearchModel(window.__searchModel__, directoryId);
            return;
        }

        console.warn("Could not find searchModel to apply strict filter");
    },

    /**
     * Áp dụng domain cho searchModel
     */
    _applyDomainToSearchModel(searchModel, directoryId) {
        const strictDomain = [["document_directory_id", "=", directoryId]];

        // Kiểm tra domain hiện tại
        const currentDomain = searchModel.domain || [];
        const alreadyStrict = currentDomain.some(d =>
            Array.isArray(d) &&
            d[0] === "document_directory_id" &&
            d[1] === "=" &&
            d[2] === directoryId
        );

        if (!alreadyStrict) {
            console.log("Applying strict domain:", strictDomain);

            if (searchModel.updateDomain) {
                searchModel.updateDomain(strictDomain, { noSearch: false });
            } else if (searchModel.domain) {
                searchModel.domain = strictDomain;
                if (searchModel.search) {
                    searchModel.search();
                } else if (searchModel.trigger) {
                    searchModel.trigger("search");
                }
            }
        }
    },

    /**
     * Hiển thị indicator
     */
    _getCategoryValueDescription(category, valueId) {
        const description = super._getCategoryValueDescription(category, valueId);

        if (category.fieldName === "document_directory_id" &&
            strictDirectoryState.enabled &&
            valueId === strictDirectoryState.currentDirectory) {
            return {
                ...description,
                display_name: `${description.display_name} (Strict)`
            };
        }

        return description;
    }
});