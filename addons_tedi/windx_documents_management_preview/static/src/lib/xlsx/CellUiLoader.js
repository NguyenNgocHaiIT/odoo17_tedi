/******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};

/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {

/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId])
/******/ 			return installedModules[moduleId].exports;

/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			exports: {},
/******/ 			id: moduleId,
/******/ 			loaded: false
/******/ 		};

/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);

/******/ 		// Flag the module as loaded
/******/ 		module.loaded = true;

/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}


/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;

/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;

/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "";

/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(0);
/******/ })
/************************************************************************/
/******/ ({

/***/ 0:
/***/ (function(module, exports, __webpack_require__) {

	module.exports = __webpack_require__(144);


/***/ }),

/***/ 144:
/***/ (function(module, exports, __webpack_require__) {

	var CellUI = __webpack_require__(145);

	window.createCellJS = function(){
	    var cellJS = new CellJS();
	    cellJS.setUI(new CellUI());

	    return cellJS;
	};

	window.cellParser = function(file, successFn, errorFn){
	    window.cellJS.parse(file, successFn, errorFn);
	};

	window.cellAfterRender = function(element, callBackFn, sheetId) {
	    window.cellJS.render(element, callBackFn, sheetId);
	};

/***/ }),

/***/ 145:
/***/ (function(module, exports, __webpack_require__) {

	// var MobileUI = require('./MobileUI');
	// var DesktopUI = require('./DesktopUI');

	var MobileUI = __webpack_require__(146);
	var DesktopUI = MobileUI;

	function UI() {
	    this.mobileUI = null;
	    this.desktopUI = null;
	}

	UI.prototype.initialize = function(loaderInstance) {
	    this.loaderInstance = loaderInstance;

	    if ($.browser.mobile) {
	        this.mobileUI = new MobileUI(this.loaderInstance);
	    } else {
	        this.desktopUI = new DesktopUI(this.loaderInstance);
	    }
	};

	UI.prototype.getMobileUIInstance = function() {
	    return this.mobileUI;
	};

	UI.prototype.getDesktopUIInstance = function() {
	    return this.desktopUI;
	};

	UI.prototype.destroy = function(callback) {
	    if (this.mobileUI) {
	        if (this.mobileUI.destroy) {
	            this.mobileUI.destroy(callback);
	        }
	    }

	    if (this.desktopUI) {
	        if (this.desktopUI.destroy) {
	            this.desktopUI.destroy(callback);
	        }
	    }

	    this.mobileUI = null;
	    this.desktopUI = null;
	};


	module.exports = UI;

/***/ }),

/***/ 146:
/***/ (function(module, exports) {

	var themeColor = '#323639';

	function DesktopUI(instance) {
	    this.jsViewer = instance;
	    this.jsElement = this.jsViewer.getElement();
	    this.fileInfo = this.jsViewer.getFileInfo();

	    this.$jsElement = $(this.jsElement);
	    this.isDesktop = this.jsElement.getBoundingClientRect().width >= 760;

        // remove header, footer
        $('#' + this.Config.id.root + ' .' + this.Config.class.header).remove();
        $('#' + this.Config.id.root + ' .' + this.Config.class.footer).remove();

	    this.createTemplate();
	    this.setEvent();
        this.mainButtonTouch();
	}

	DesktopUI.prototype = {
	    Config: {
	        logoTitle: "WinDX",
	        logoSubTitle: "Js Document Viewer",
	        id: {
                root: "ms-office-root",
	        },
	        class: {
                header: "windx-ms-office-preview-header",
                footer: "windx-ms-office-preview-footer",
	        },

	        styles: {
	            header: {
	                wrapper: "z-index: 1000; display: block; width: 100%; height: 30px; position: relative; margin: 0; padding: 0; background: " + themeColor + "; font-family: Arial; transform: translate3d(0px, 0px, 0px); -webkit-transform: translate3d(0px, 0px, 0px); -ms-transform: translate3d(0px, 0px, 0px);",
	                logo: "float: left; height: 30px; padding: 5px 10px 5px 10px; background-color: " + themeColor + "; text-align: left;",
	                logoText: "font-weight: 600; font-size: 16px; color: #fff; margin: 0; padding: 0;",
	                logoSubText: "font-size: 16px; font-weight: normal; font-style: italic; color: #fff; margin: 0; padding: 0;",

	                rightMenu: "float: right padding: 5px 10px 5px 18px;!important; position: absolute; top: 0; right: 0; font-size: 10px; padding: 0 5px; color: #ffffff;",

	                buttonGroup: "float: left; margin: 0; padding-left: 0; list-style: none; border: none !important;",
	                buttonGroupItem: "float: left; display: block; position: relative; cursor: pointer;",
	                btnA: "cursor: pointer; display: block; float: left; width: 30px; height: 30px; text-align: center; margin-left: 0px; overflow: hidden; white-space: nowrap; margin-right: 10px;",
	                icon: "width:20px; height:20px; margin: 5px;"
	            },

	            footer: {
	                wrapper: "z-index: 1000; display: block; position: absolute; width: 100%; height: 25px; background: " + themeColor + "; bottom: 0; margin: 0; padding: 0; font-family: Arial; ",
	                floatButton: "position: absolute; cursor: pointer; width: 40px; height: 40px; background-color: " + themeColor + "; font-size: 35px; color: #FFFFFF; text-align: center; border-radius: 50%; -webkit-user-select: none; -moz-user-select: none; -ms-user-select: none; user-select: none; z-index: 1001; right: 20px; bottom: 50px;",
                    btnA: "cursor: pointer; display: block; float: left; width: 40px; height: 40px; text-align: center; margin-left: 0px; overflow: hidden; white-space: nowrap; margin-right: 10px;",
	                icon: "width:20px; height:20px; margin: 10px;"
	            },

	            sheetInfo: {
	                wrapper: "position:relative; display:inline-block; width: 70%; height: 100%; font-size: 10px;  color: #ffffff; overflow: hidden;",
	                select: "position:relative; display:inline-block; width: 70%; height: 100%; font-size: 10px;  color: #ffffff; overflow: hidden;",
	                fileName: "display:inline-block; position:absolute; width: 30%; font-size: 10px; color: #ffffff; text-align: right; overflow: hidden;",

	                sheetName: {
	                    wrapper: "position:absolute; top: 0; left:-100000px; margin:0; padding:0; list-style: none; left:65px;",
	                    item: "float: left; display: block; position: relative; cursor: pointer;",
	                    itemA: "cursor: pointer;display: block;float: left;min-width: 60px;height: 13px;text-align: center;margin-left: 0;overflow: hidden;white-space: nowrap;border: 1px solid #969696;background: #ffffff;color: #000000;font-size: 10px;padding: 3px;border-radius: 0 0 3px 3px; border-bottom: 3px solid #00B48C;box-sizing: content-box;",
	                    activeA: "border-bottom: 3px solid #00B48C;"
	                },

	                sheetMoveNode: {
	                    wrapper : "width:60px;",
	                    ul: "padding:0;list-style: none; margin:0;",
	                    li: "float: left; display: block; position: relative; cursor: pointer; margin: 0px;",
	                    btn: "cursor: pointer;display: block;float: left; width: 25px;height: 15px;text-align: center; overflow: hidden;white-space: nowrap; color: #ffffff;font-size: 12px; margin-left:3px; padding-top: 5px;"
	                }
	            },
	        }
	    },
	    createTemplate: function () {
	        this.$header = $('<div class="' + this.Config.class.header + '" style="' + this.Config.styles.header.wrapper + '"></div>');
	        this.$logo = $('' +
	            '<div style="' + this.Config.styles.header.logo + '">' +
	            // '<p style="' + this.Config.styles.header.logoText + '">' + this.Config.logoTitle + '</p>' +
	            // '<p style="' + this.Config.styles.header.logoSubText + '">' + this.Config.logoSubTitle + '</p>' +
	            '<p style="' + this.Config.styles.header.logoSubText + '">' + this.fileInfo.fileName + '</p>' +
	            '</div>');

	        this.$menuBtns = {
	            header: {
	                fullscreen: $('' +
	                    '<li style="' + this.Config.styles.header.buttonGroupItem + '">' +
	                        '<a style="' + this.Config.styles.header.btnA + '">' +
	                            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 63 63" xml:space="preserve"  preserveAspectRatio="xMinYMin meet" style="' + this.Config.styles.header.icon + '">' +
	                                '<g fill="#ffffff">' +
	                                    '<path d="M18.796842008225546,12.51633946062611 l2.8179575342658323,-2.6678772754275046 c1.8829356299311009,-1.8525303911064799 1.3959653249159782,-3.9422216450450005 -1.0851021631730577,-4.522840085639954 H8.594546552057071 C6.615773609350767,5.397378463184758 5.291564648060893,5.995267079432097 5.356996722011477,8.611090585991851 L5.339483304448495,20.559376476425335 c0.5022945453827311,2.4635540705260555 2.2222580952138657,2.944200085865656 3.8269249794220395,1.0697779228054491 l3.167982643614863,-2.9940646775380335 l10.013053249724036,10.00867489533329 c0.8698330722947447,0.8676438950993718 2.2808793956677347,0.8698330722947447 3.1485232907671064,0.004378354390745358 l3.1463341135717338,-3.1463341135717338 c0.8676438950993718,-0.8654547179039992 0.8654547179039992,-2.278690218472362 -0.002189177195372681,-3.1463341135717338 C28.6401124043529,22.35547474427332 18.796842008225546,12.51633946062611 18.796842008225546,12.51633946062611 zM25.4351569903273,36.43018141714546 c-0.8632655407086263,-0.8654547179039992 -2.2721226868862443,-0.8654547179039992 -3.137577404790243,0.004378354390745358 l-9.982648010899416,9.973891302117925 l-3.1594691767439698,-2.9896863231472883 c-1.5980993526220568,-1.8700438086694622 -3.3136845480624446,-1.3893977933298605 -3.815979093445177,1.0653995684147037 L5.358942657296253,56.40423414772579 c-0.0629996548446138,2.6004992661921453 1.2524525976637693,3.2049554140256022 3.229036363174701,3.272333423260961 h11.906934765632002 c2.4701216021121724,-0.5849967949856996 2.957091907127295,-2.665688098232132 1.0807238087823123,-4.507515845272345 l-2.8092008254843406,-2.659363808556611 l9.806540867627213,-9.81091922201796 c0.8654547179039992,-0.8654547179039992 0.8676438950993718,-2.2743118640816165 0.002189177195372681,-3.13538822759487 C28.574923572312915,39.56338046754496 25.4351569903273,36.43018141714546 25.4351569903273,36.43018141714546 zM39.56216067397779,28.645953794221413 c0.8632655407086263,0.8654547179039992 2.2743118640816165,0.8632655407086263 3.139766581985615,-0.004378354390745358 l9.984837188094787,-10.00867489533329 l3.1594691767439698,2.9940646775380335 c1.59372099823131,1.8744221630602074 3.3093061936717003,1.3937761477206059 3.8116007390544313,-1.0697779228054491 l-0.017513417562981446,-11.948285890433484 C59.703563839048826,5.993077902236724 58.3834899902391,5.395189285989386 56.411771062940105,5.323432922363281 h-11.915691474413492 c-2.4723107793075454,0.5828076177903275 -2.9463892630610284,2.6722556298182503 -1.0697779228054491,4.522840085639954 l2.813579179875086,2.670066452622878 L36.42677244638293,22.351096389882574 c-0.8654547179039992,0.8676438950993718 -0.8654547179039992,2.2808793956677347 0,3.1463341135717338 C36.42677244638293,25.497430503454307 39.56216067397779,28.645953794221413 39.56216067397779,28.645953794221413 zM55.85499032958366,43.416575573311476 l-3.150712467962479,2.9896863231472883 l-9.950053594879423,-9.973891302117925 c-0.8654547179039992,-0.8698330722947447 -2.2721226868862443,-0.8698330722947447 -3.1310098732041247,-0.004378354390745358 l-3.1288206960087517,3.1331990503994978 c-0.8610763635132533,0.8610763635132533 -0.8588871863178806,2.270176751601468 0.004378354390745358,3.13538822759487 l9.778081564087367,9.806540867627213 l-2.807011648288968,2.663742162947357 c-1.8678546314740898,1.845962859520362 -1.3893977933298605,3.929086581872763 1.0741562771961946,4.507515845272345 h11.878718704002752 c1.9678270567294416,-0.06737800923535912 3.2898468408239423,-0.6718341570688162 3.220279654393211,-3.272333423260961 l0.017513417562981446,-11.920069828804237 C59.15772899166924,42.02912371526639 57.44652215061959,41.54872094183738 55.85499032958366,43.416575573311476 z"></path>' +
	                                '</g>' +
	                            '</svg>' +
	                        '</a>' +
	                    '</li>')
	            },

	            footer: {
	                main: $('' +
	                    '<div style="' + this.Config.styles.footer.floatButton + '">' +
	                        '<a style="' + this.Config.styles.footer.btnA + '">' +
	                            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 63 63" xml:space="preserve" transform="translate(0 -9)" style="' + this.Config.styles.footer.icon + '">' +
	                                '<g fill="#ffffff">' +
	                                    '<path d="M56.588499999999996,25 H40 H25 H8.4115 C4.336,25 1,28.423000000000002 1,32.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,40 64,36.577 64,32.5 S60.664,25 56.588499999999996,25 z" stroke-dasharray="none" stroke="null"></path>' +
	                                    '<path d="M56.588499999999996,3 H40 H25 H8.4115 C4.336,3 1,6.423000000000002 1,10.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,18 64,14.576999999999998 64,10.5 S60.664,3 56.588499999999996,3 z" stroke-dasharray="none" stroke="null"></path>' +
	                                    '<path d="M56.588499999999996,47 H40 H25 H8.4115 C4.336,47 1,50.423 1,54.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,62 64,58.577 64,54.5 S60.664,47 56.588499999999996,47 z" stroke-dasharray="none" stroke="null"></path>' +
	                                '</g>' +
	                            '</svg>' +
	                        '</a>' +
	                    '</div>'),

	                zoomOut: $('' +
	                    '<div style="' + this.Config.styles.footer.floatButton + '">' +
	                        '<a style="' + this.Config.styles.footer.btnA + '">' +
	                            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 65 65" xml:space="preserve" transform="translate(0 -9)" style="' + this.Config.styles.footer.icon + '">' +
	                                '<g fill="#ffffff">' +
	                                    '<path d="M56.97085819470882,24.880952835083008 H40.11904835700989 V8.02914299738407 C40.11904835700989,3.8889524440765384 36.64171495890617,0.5 32.50000059604645,0.5 s-7.61904776096344,3.3889524440765384 -7.61904776096344,7.529142997384071 V24.880952835083008 H8.02914299738407 C3.8889524440765384,24.880952835083008 0.5,28.35828623318672 0.5,32.50000059604645 s3.3889524440765384,7.61904776096344 7.529142997384071,7.61904776096344 H24.880952835083008 v16.851809837698934 C24.880952835083008,61.111048748016366 28.35828623318672,64.5000011920929 32.50000059604645,64.5000011920929 s7.61904776096344,-3.3889524440765384 7.61904776096344,-7.529142997384071 V40.11904835700989 h16.851809837698934 C61.111048748016366,40.11904835700989 64.5000011920929,36.64171495890617 64.5000011920929,32.50000059604645 S61.111048748016366,24.880952835083008 56.97085819470882,24.880952835083008 z"></path>' +
	                                '</g>' +
	                            '</svg>' +
	                        '</a>' +
	                    '</div>'),

	                resetZoom: $('' +
	                    '<div style="' + this.Config.styles.footer.floatButton + '">' +
	                        '<a style="' + this.Config.styles.footer.btnA + '">' +
	                            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" xml:space="preserve" transform="translate(0 -9)" style="' + this.Config.styles.footer.icon + '">' +
	                                '<g fill="#ffffff">' +
	                                    '<path d="m61.15,53.93l-11.68,-11.68c-0.53,-0.53 -1.24,-0.82 -1.99,-0.82l-1.91,0c3.23,-4.13 5.15,-9.33 5.15,-14.99c0,-13.46 -10.9,-24.36 -24.36,-24.36s-24.36,10.9 -24.36,24.36s10.9,24.36 24.36,24.36c5.66,0 10.86,-1.92 14.99,-5.15l0,1.91c0,0.75 0.29,1.46 0.82,1.99l11.68,11.68c1.1,1.1 2.88,1.1 3.97,0l3.31,-3.31c1.1,-1.1 1.1,-2.88 0.01,-3.98zm-34.79,-12.5c-8.28,0 -14.99,-6.7 -14.99,-14.99c0,-8.28 6.7,-14.99 14.99,-14.99c8.28,0 14.99,6.7 14.99,14.99c0,8.28 -6.7,14.99 -14.99,14.99z"/>' +
	                                '</g>' +
	                            '</svg>' +
	                        '</a>' +
	                    '</div>'),

	                zoomIn: $('' +
	                    '<div style="' + this.Config.styles.footer.floatButton + '">' +
	                        '<a style="' + this.Config.styles.footer.btnA + '">' +
	                            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 63 63" xml:space="preserve" transform="translate(0 -9)" style="' + this.Config.styles.footer.icon + '">' +
	                                '<g fill="#ffffff">' +
	                                    '<path d="M56.588499999999996,25 H40 H25 H8.4115 C4.336,25 1,28.423000000000002 1,32.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,40 64,36.577 64,32.5 S60.664,25 56.588499999999996,25 z"></path>' +
	                                '</g>' +
	                            '</svg>' +
	                        '</a>' +
	                    '</div>')
	            }
	        };

	        /** Header Menu Setting **/
	        var _this = this;
	        if (this.$logo) {
	            this.$header.append(this.$logo);
	        }

	        var $menuWrapper = $('<div></div>');
	        var $menu = $('<div style="' + this.Config.styles.header.rightMenu + '"></div>');
	        var $menuGroup = $('<ul style="' + this.Config.styles.header.buttonGroup + '"></ul>');
	        $.each(this.$menuBtns.header, function () {
	            $menuGroup.append(this);
	        });
	        $menu.append($menuGroup);
	        $menuWrapper.append($menu);

	        this.$header.append($menu);

	        /** Footer Menu Setting **/
	        this.$footer = $('<div class="' + this.Config.class.footer + '" style="' + this.Config.styles.footer.wrapper + '"></div>');
	        this.$pageInfo = $('<div style="' + this.Config.styles.header.rightMenu + '"></div>');

	        /** Sheet Select Menu Setting **/
	        if (this.isDesktop) {
	            var sheetNameStr = '';
	            var isFirst = true;
	            if (this.fileInfo.sheetNames) {
	                $.each(this.fileInfo.sheetNames, function () {
	                    if (this.name && this.state !== 'hidden') {
	                        sheetNameStr += '' +
	                            '<li style="'+_this.Config.styles.sheetInfo.sheetName.item +'">' +
	                            '<a style="'+_this.Config.styles.sheetInfo.sheetName.itemA + ( (isFirst) ? _this.Config.styles.sheetInfo.sheetName.activeA : "") + '" data-sheet-id="' + this.sheetId + '">' +
	                            '<span>' + this.name + '</span>' +
	                            '</a>' +
	                            '</li>';
	                        isFirst = false;
	                    }
	                });
	            }

	            this.$sheetMoveNode = $('' +
	                '<div style="'+this.Config.styles.sheetInfo.sheetMoveNode.wrapper+'">' +
	                    '<ul style="'+this.Config.styles.sheetInfo.sheetMoveNode.ul+'">' +
	                        '<li style="'+this.Config.styles.sheetInfo.sheetMoveNode.li+'"><a style="'+this.Config.styles.sheetInfo.sheetMoveNode.btn+'" data-action="prev"><span>◀</span></a></li>' +
	                        '<li style="'+this.Config.styles.sheetInfo.sheetMoveNode.li+'"><a style="'+this.Config.styles.sheetInfo.sheetMoveNode.btn+'" data-action="next"><span>▶</span></a></li>' +
	                    '</ul>' +
	                '</div>' +
	                '');


	            this.$sheetNameNode = $('<ul style="'+this.Config.styles.sheetInfo.sheetName.wrapper+'">' + sheetNameStr + '</ul>');
	            this.$sheetInfo = $('<div style="' + this.Config.styles.sheetInfo.wrapper + '"></div>');

	            this.$sheetInfo.append(this.$sheetNameNode);
	            this.$footer.append(this.$sheetInfo);
	        } else {
	            var selectHTML = '<optgroup>';
	            if (this.fileInfo.sheetNames) {
	                $.each(this.fileInfo.sheetNames, function () {
	                    if (this.name && this.state !== 'hidden') {
	                        selectHTML += '<option value="' + this.sheetId + '">' + this.name + '</option>'
	                    }
	                });
	            }
	            selectHTML += '</optgroup>';
	            this.$sheetNameSelect = $('<select style="' + _this.Config.styles.sheetInfo.select + '">' + selectHTML + '</select>');
	            this.$footer.append(this.$sheetNameSelect);
	        }

	        this.$footer.append(this.$pageInfo);
	        $.each(this.$menuBtns.footer, function (key, value) {
	            if (value) {
	                if (key !== 'main') {
	                    value.hide();
	                }
	                _this.$footer.append(value);
	            }
	        });

	        this.$jsElement.parent().before(this.$header);
	        this.$jsElement.parent().after(this.$footer);
	    },

	    setEvent: function () {
	        var _this = this;
	        $.each(this.$menuBtns.header, function (key) {
	            $(this).children('a').on('touchstart mousedown', (function (_key) {
	                return function (e) {
	                    e.stopPropagation();
	                    e.preventDefault();

	                    _this._clickButton(this, _key);
	                }
	            })(key));
	        });
	        $.each(this.$menuBtns.footer, function (key) {
	            $(this).children('a').on('touchstart mousedown', (function (_key) {
	                return function (e) {
	                    e.stopPropagation();
	                    e.preventDefault();

	                    _this._clickButton(this, _key);
	                }
	            })(key));
	        });

	        if (this.$sheetNameSelect) {
	            this.$sheetNameSelect.on('change', function () {
	                var val = _this.$sheetNameSelect.val();
	                _this.jsViewer.gotoPage(val);
	            });
	        }

	        if (this.$sheetInfo) {
	            var sheetInfoWidth = this.$sheetInfo.width() - 65;
	            var sheetNameNodeWidth = this.$sheetNameNode.width() + 1;
	            var $sheets = $(this.$sheetNameNode).find('li');
	            var $sheetButtons = $sheets.find('a');
	            $sheetButtons.on('touchstart mousedown', function () {
	                var $this = $(this);
	                if ($this.hasClass('active')) {
	                    return;
	                }

	                $sheetButtons.removeClass('active');
	                $sheetButtons.css({
	                    'height': '15px',
	                    'border-bottom': '1px solid #969696'
	                });

	                var val = this.getAttribute('data-sheet-id');
	                $this.css({
	                    'height': '13px',
	                    'border-bottom': '3px solid #00B48C'
	                });
	                $this.addClass('active');
	                _this.jsViewer.gotoPage(val);
	            });

	            if (sheetInfoWidth < sheetNameNodeWidth) {
	                var sheetNameWidthInfo = [];
	                $sheets.each(function (i) {
	                    sheetNameWidthInfo[i] = $(this).width();
	                });

	                var _width = 0, lastIndex = 0;
	                for (var length = sheetNameWidthInfo.length, i = length - 1; i >= 0; i--) {
	                    _width += sheetNameWidthInfo[i];
	                    if (sheetInfoWidth < _width) {
	                        lastIndex = i + 1;
	                        break;
	                    }
	                }

	                this.currentIndex = 0;
	                this.$sheetMoveNode.find('a').on('touchstart mousedown', function () {
	                    var action = this.getAttribute('data-action');
	                    if (action === 'prev') {
	                        _this.currentIndex--;
	                    } else {
	                        _this.currentIndex++;
	                    }

	                    if (_this.currentIndex < 0) {
	                        _this.currentIndex = 0;
	                    } else if (_this.currentIndex > lastIndex) {
	                        _this.currentIndex = lastIndex
	                    }

	                    $sheets.each(function (i) {
	                        if (i < _this.currentIndex) {
	                            this.style.display = 'none';
	                        } else {
	                            this.style.display = 'block';
	                        }
	                    });
	                });
	            }

                // Active sheet 0
                $($sheetButtons[0]).mousedown();
	        }

	    },

	    _clickButton: function (element, type) {
	        switch (type) {
	            case 'fullscreen' :
	                this.fullscreen();
	                break;
	            case 'main' :
	                this.mainButtonTouch();
	                break;
	            case 'resetZoom' :
	                this.resetZoom();
	                break;
	            case 'zoomOut' :
	                this.zoomOut();
	                break;
	            case 'zoomIn' :
	                this.zoomIn();
	                break;
	        }
	    },

	    setPageInfo: function (index) {
	        this.$pageInfo.html('<span>' + (index + 1) + '/' + this.totalPage + '</span>');
	    },

	    fullscreen: function (e) {
	        var elem = this.jsElement;

	        if (this.isFullScreen()) {
	            if (document.exitFullscreen) {
	                document.exitFullscreen();
	            } else if (document.webkitExitFullscreen) {
	                document.webkitExitFullscreen();
	            } else if (document.webkitCancelFullScreen) {
	                document.webkitCancelFullScreen();
	            } else if (document.mozCancelFullScreen) {
	                document.mozCancelFullScreen();
	            } else if (document.msExitFullscreen) {
	                document.msExitFullscreen();
	            }
	        } else {
	            if (elem.requestFullscreen) {
	                elem.requestFullscreen();
	            } else if (elem.mozRequestFullScreen) {
	                elem.mozRequestFullScreen();
	            } else if (elem.webkitRequestFullscreen) {
	                elem.webkitRequestFullscreen();
	            } else if (elem.msRequestFullscreen) {
	                elem.msRequestFullscreen();
	            } else {
	                // console.log("Not Support FullScreen");
	            }
	        }
	    },

	    isFullScreen: function () {
	        return !!(document.fullscreenElement || document.webkitFullscreenElement || document.webkitCurrentFullScreenElement || document.mozFullScreenElement || document.msFullscreenElement);
	    },

	    resetZoom: function () {
	        this.jsViewer.setZoom(1);
	    },

	    zoomOut: function () {
	        var currentZoom = this.jsViewer.getZoom();
	        this.jsViewer.setZoom(currentZoom + 0.5);
	    },

	    zoomIn: function () {
	        var currentZoom = this.jsViewer.getZoom();
	        this.jsViewer.setZoom(currentZoom - 0.5);
	    },

	    mainButtonTouch: function () {
	        var action = 'change';
	        if (this.$menuBtns.footer.main.hasClass('open')) {
	            action = '';
	            this.moveButtons(this.$menuBtns.footer.next, 20, action);
	            this.moveButtons(this.$menuBtns.footer.prev, 20, action);
	            this.moveButtons(this.$menuBtns.footer.zoomOut, 20, action);
	            this.moveButtons(this.$menuBtns.footer.resetZoom, 20, action);
	            this.moveButtons(this.$menuBtns.footer.zoomIn, 20, action);

	            this.$menuBtns.footer.main.find('g').html(
	                '<path d="M56.588499999999996,25 H40 H25 H8.4115 C4.336,25 1,28.423000000000002 1,32.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,40 64,36.577 64,32.5 S60.664,25 56.588499999999996,25 z" stroke-dasharray="none" stroke="null"></path>' +
	                '<path d="M56.588499999999996,3 H40 H25 H8.4115 C4.336,3 1,6.423000000000002 1,10.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,18 64,14.576999999999998 64,10.5 S60.664,3 56.588499999999996,3 z" stroke-dasharray="none" stroke="null"></path>' +
	                '<path d="M56.588499999999996,47 H40 H25 H8.4115 C4.336,47 1,50.423 1,54.5 s3.3360000000000003,7.5 7.4115,7.5 H25 h15 h16.5885 C60.664,62 64,58.577 64,54.5 S60.664,47 56.588499999999996,47 z" stroke-dasharray="none" stroke="null"></path>'
	            );

	            this.$menuBtns.footer.main.removeClass('open');
	        } else {
	            $.each(this.$menuBtns.footer, function (key, value) {
	                if (value && key !== 'main') {
	                    value.show();
	                }
	            });

                this.viewButton(action);

	            this.$menuBtns.footer.main.find('g').html(
	                '<path d="M45.361877472758295,32.50024811834097 l13.902431874096393,-13.902431874096393 c0.8831252442598347,-0.8822971073091034 1.3240253568291664,-1.9540719489455225 1.3240253568291664,-3.2154901522994046 c0,-1.2610869485735894 -0.442059504300356,-2.3326961628198624 -1.3240253568291664,-3.2154901522994046 L52.83349466964603,5.73535875287652 C51.95086630755663,4.852896018177271 50.87925709331035,4.4114990234375 49.618501399517065,4.4114990234375 c-1.2615838307440281,0 -2.3328617902100093,0.4413969947397711 -3.215987034469843,1.3238597294390204 L32.50024811834097,19.637790626972915 L18.59765061685443,5.73535875287652 C17.715519136935473,4.852896018177271 16.64374429529905,4.4114990234375 15.382160464555025,4.4114990234375 c-1.2605900664031504,0 -2.3325305354297163,0.4413969947397711 -3.2154901522994046,1.3238597294390204 L5.735524380266666,12.166835939645768 C4.8532272729575645,13.048967419564724 4.4114990234375,14.121239143371582 4.4114990234375,15.38232609194517 c0,1.261418203353882 0.44123136734962487,2.3326961628198624 1.3240253568291664,3.2154901522994046 l13.902266246706247,13.902431874096393 L5.735524380266666,46.402679992437356 C4.8532272729575645,47.28563960930705 4.4114990234375,48.35691756877303 4.4114990234375,49.618667026907204 c0,1.2604244390130044 0.44123136734962487,2.3323649080395703 1.3240253568291664,3.214827642738819 l6.4313115593791,6.430980304598809 c0.882793989479542,0.8831252442598347 1.9549000858962535,1.3240253568291664 3.2154901522994046,1.3240253568291664 c1.261418203353882,0 2.3326961628198624,-0.442059504300356 3.2154901522994046,-1.3240253568291664 l13.90259750148654,-13.902431874096393 l13.903425638437271,13.902431874096393 c0.8824627346992493,0.8831252442598347 1.953243811994791,1.3240253568291664 3.215987034469843,1.3240253568291664 c1.2605900664031504,0 2.3323649080395703,-0.442059504300356 3.2149932701289656,-1.3240253568291664 l6.429655285477638,-6.430980304598809 c0.8831252442598347,-0.8818002251386644 1.3240253568291664,-1.954403203725815 1.3240253568291664,-3.214827642738819 c0,-1.2617494581341744 -0.4409001125693322,-2.333027417600155 -1.3240253568291664,-3.215987034469843 L45.361877472758295,32.50024811834097 z"></path>'
	            );

	            this.$menuBtns.footer.main.addClass('open');
	        }
	    },

	    viewButton: function (action) {
            this.moveButtons(this.$menuBtns.footer.next, 270, action);
            this.moveButtons(this.$menuBtns.footer.prev, 220, action);
            this.moveButtons(this.$menuBtns.footer.zoomOut, 170, action);
            this.moveButtons(this.$menuBtns.footer.resetZoom, 120, action);
            this.moveButtons(this.$menuBtns.footer.zoomIn, 70, action);
	    },

	    moveButtons: function ($button, position, action) {
	        if (!$button) {
	            return;
	        }
	        if (action === 'change') {
	            $button.animate({
	                right: position,
	                opacity: 1
	            }, "fast");
	        } else {
	            $button.animate({
	                right: position,
	                opacity: 0
	            }, "fast");

	            $button.fadeOut('fast');
	        }
	    },

	    destroy : function(callback){
	        this.$logo.remove();
	        this.$header.remove();
	        this.$footer.remove();

	        this.$logo = null;
	        this.$header = null;
	        this.$footer = null;
	        this.fileInfo = null;
	        this.totalPage = null;
	        this.$jsElement = null;

	        this.jsViewer = null;

	        delete this.$menuBtns;

	        if (callback) {
	            callback();
	        }
	    }

	};

	module.exports = DesktopUI;

/***/ })

/******/ });