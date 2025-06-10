class StyleManager:
    @staticmethod
    def get_theme_default_colors(is_dark):
        if is_dark:
            return {
                'bg': "qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba(120,255,240,90), stop:0.12 rgba(80,220,200,140), stop:0.25 rgba(60,160,150,180), stop:0.40 rgba(40,110,120,200), stop:0.60 rgba(25,60,80,220), stop:0.80 rgba(15,30,40,240), stop:1 rgba(10,15,25,255))",                
                'fg': '#EAECEE',
                '_btn_bg': '#5DADE2',
                '_btn_hover': '#3498DB',
                '_btn_fg': '#FFFFFF',
                '_lbl_fg': '#FFFFFF',
                '_inp_bg': '#2C3E50',
                '_inp_fg': '#EAECEE',
                '_inp_border': '#3C526E',
                '_textedit_bg': '#20252A',
                '_textedit_fg': '#D0D3D4',
                '_textedit_border': '#2980B9',
                '_table_bg': '#23272e',
                '_table_header_bg': '#2c313a',
                '_table_header_fg': '#e0e0e0',
                '_table_row_alt': '#262b33',
                '_table_grid': '#393e46',
                '_table_text': '#e0e0e0',
                '_table_select_bg': '#3a7afe',
                '_table_select_fg': '#ffffff',
                '_progress_bg': '#23272e',
                '_progress_fg': '#EAECEE',
                '_progress_chunk': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6a82fb, stop:1 #fc5c7d)',
            }
        else:
            bg = "qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba(180,130,80,255), stop:0.5 rgba(120,70,40,255), stop:1 rgba(80,40,20,255))"
            text_color = "#333333"
            hover_color = "rgba(255,255,255,30)"
            status_color = "#FFFFFF"
            return {
                'bg': "qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba(255,255,255,255), stop:0.12 rgba(255,255,252,252), stop:0.25 rgba(255,254,245,250), stop:0.40 rgba(255,253,240,245), stop:0.60 rgba(255,252,235,240), stop:0.80 rgba(255,250,230,230), stop:1 rgba(254,248,220,210))",
                'fg': '#2E3B4E',
                '_btn_bg': bg,
                '_btn_hover': hover_color,
                '_btn_fg': '#FFFFFF',
                '_lbl_fg': text_color,
                '_inp_bg': '#FFF8E1',
                '_inp_fg': '#2E3B4E',
                '_inp_border': '#D2B48C',
                '_textedit_bg': '#FAFAFA',
                '_textedit_fg': '#2C3E50',
                '_textedit_border': '#B0B0B0',
                '_table_bg': 'rgba(255,255,255,0.95)',
                '_table_header_bg': '#f5f5f5',
                '_table_header_fg': '#222',
                '_table_row_alt': '#f7f9fa',
                '_table_grid': '#e0e0e0',
                '_table_text': '#222',
                '_table_select_bg': '#e3f0ff',
                '_table_select_fg': '#222',
                '_progress_bg': '#f5f5f5',
                '_progress_fg': '#2E3B4E',
                '_progress_chunk': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f7971e, stop:1 #ffd200)',
            }
    @staticmethod
    def build_stylesheet(colors):
        return f"""
        QWidget#main_window {{ background-color: {colors['bg']}; color: {colors['fg']}; font-family: 'Segoe UI', sans-serif; }}
        QPushButton {{ background: {colors['_btn_bg']}; color: {colors['_btn_fg']}; border-radius: 5px; padding: 10px; font-size: 16px; }}
        QPushButton:hover {{ background-color: {colors['_btn_hover']}; color: #00FFFF; }}
        QLabel {{ color: {colors['_lbl_fg']}; background: transparent; }}
        QLineEdit {{ background-color: {colors['_inp_bg']}; color: {colors['_inp_fg']}; border: 1px solid {colors['_inp_border']}; border-radius: 4px; padding: 4px; font-size: 16px; }}
        QTextEdit {{ background-color: {colors.get('_textedit_bg', '#FAFAFA')}; color: {colors.get('_textedit_fg', '#2C3E50')}; border: 1px solid {colors.get('_textedit_border', '#B0B0B0')}; border-radius: 4px; padding: 4px; font-size: 16px; opacity: 0.9; }}
        QScrollArea {{ background-color: {colors['bg']}; }}
        QFormLayout {{ margin:5px; spacing:10px; }}
        QTabWidget::pane {{ border: 1px solid {colors['_inp_border']}; background: transparent; }}
        QTabWidget::tab-bar {{ left: 5px; }}
        QTabBar::tab {{ background: {colors['_btn_bg']}; color: {colors['_btn_fg']}; padding: 8px; border: 1px solid {colors['_inp_border']}; border-bottom: 1px solid {colors['_inp_border']}; }}
        QTabBar::tab:selected {{ background: {colors['bg']}; border-color: {colors['_inp_border']}; border-bottom: 2px solid {colors['_btn_hover']}; }}
        QTabBar::tab:hover {{ background: {colors['_btn_hover']}; }}
        QTableWidget {{ background: {colors['_table_bg']}; alternate-background-color: {colors['_table_row_alt']}; gridline-color: {colors['_table_grid']}; color: {colors['_table_text']}; font-size: 14px; selection-background-color: {colors['_table_select_bg']}; selection-color: {colors['_table_select_fg']}; border-left: 1px solid {colors['_inp_border']}; border-right: 1px solid {colors['_inp_border']}; }}
        QHeaderView::section {{ background: {colors['_table_header_bg']}; color: {colors['_table_header_fg']}; border: none; border-bottom: 2px solid {colors['_table_grid']}; font-weight: 600; font-size: 14px; padding: 6px 0px; border-radius: 0; }}
        QTableWidget::item:selected {{ background: {colors['_table_select_bg']}; color: {colors['_table_select_fg']}; }}
        QTableWidget::item {{ border: none; padding: 4px 8px; }}
        QGroupBox {{ border: 1px solid {colors.get('_inp_border', '#CCCCCC')}; border-radius: 6px; margin-top: 20px; padding: 10px; background-color: transparent; }}
        QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px 0 5px; left: 10px; color: {colors.get('_lbl_fg', '#333333')}; font-weight: bold; }}
        QProgressBar {{ border: none; border-radius: 8px; background: {colors['_progress_bg']}; height: 18px; text-align: center; color: {colors['_progress_fg']}; font-size: 14px; font-weight: 500; }}
        QProgressBar::chunk {{ background: {colors['_progress_chunk']}; border-radius: 8px; }}         
"""
    @staticmethod
    def get_sidebar_style(styles):
        bg = styles.get('bg')
        text_color = styles.get('text_color')
        hover_color = styles.get('hover_color', "rgba(255,255,255,30)")
        status_color = styles.get('status_color')
        return f"""
            QFrame#sidebar {{ background: {bg}; color: {text_color}; border: 1px solid #aaa; border-top-right-radius: 20px; border-bottom-right-radius: 20px; width: 190px; }}
            QLabel#dispatcher_icon {{ background: qradialgradient(cx:0.5, cy:0.5, radius:0.9, fx:0.5, fy:0.5, stop:0 #23272b, stop:1 #111); border-radius: 18px 0 0 18px; padding: 10px; margin-left: -8px; margin-top: 4px; margin-bottom: 4px; }}
            QLabel#main_label {{ padding: 4px 8px; font-size: 17px; font-weight: bold; color: #FFFFFF; background: transparent; }}
            QPushButton {{ text-align:left; padding-left:24px; font-size:17px; background: transparent; border: none; }}
            QPushButton[flat="false"] {{ font-size:15px; }}
            QPushButton:hover {{ background: {hover_color}; color: #00FFFF; font-weight: bold; }}
            QPushButton::icon {{ width: 16px; height: 16px; }}
            QFrame {{ background: transparent; }}
            QHBoxLayout {{ spacing: 0; }}
            QVBoxLayout {{ spacing: 0; }}
            QFrame#sidebar QLabel {{ background: transparent; }}
            QFrame#sidebar QFrame {{ background: transparent; }}
            QFrame#sidebar QWidget {{ background: transparent; }}
            QFrame#sidebar QLayout {{ spacing: 0; }}
            QFrame#sidebar QLayout::item {{ margin: 0; }}
            QWidget#bot_stats_container, QWidget#session_stats_container {{ background: transparent; border: none; margin: 2px 0; padding: 5px 0; }}
            QWidget#bot_stats_container:hover, QWidget#session_stats_container:hover {{ background: {hover_color}; border-radius: 4px; }}
            QLabel#bot_stats_title, QLabel#session_stats_title {{ color: #AAAAAA; font-size: 12px; font-weight: bold; background: transparent; min-width: 100px; padding: 0 5px; qproperty-alignment: AlignCenter; }}
            QWidget#bot_stats_container:hover QLabel#bot_stats_title, QWidget#session_stats_container:hover QLabel#session_stats_title {{ color: #00FFFF; }}
        """
    @staticmethod
    def get_sidebar_statblock_styles(is_dark):
        if is_dark:
            number_text_color = '#FFFFFF'
            title_text_color = '#AAAAAA'
        else:
            number_text_color = '#FFFFFF'
            title_text_color = '#FFFFFF'

        return {
            'widget': "background: transparent; border: none; padding: 0 2px;",
            'number_label': f"color: {number_text_color}; background-color: transparent; border: none; font-size: 11px; font-weight: 600; qproperty-alignment: AlignCenter; padding: 0 1px;",
            'title_label': f"color: {title_text_color}; background-color: transparent; border: none; font-size: 9px; font-weight: 400; qproperty-alignment: AlignCenter; padding: 0 1px; min-width: 50px;",
        }
    @staticmethod
    def get_default_sidebar_styles(is_dark):
        if is_dark:
            bg = "qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba(30,80,90,80), stop:0.3 rgba(20,40,60,180), stop:0.6 rgba(15,25,35,230), stop:1 rgba(5,10,20,255))"
            text_color = "#EAECEE"
            hover_color = "rgba(255,255,255,30)"
            status_color = "#EAECEE"
        else:
            bg = "qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba(180,130,80,255), stop:0.2 rgba(160,110,65,255), stop:0.45 rgba(140,90,50,255), stop:0.6 rgba(120,70,40,255), stop:0.8 rgba(100,55,30,255), stop:1 rgba(80,40,20,255))"
            text_color = "#333333"
            hover_color = "rgba(255,255,255,30)"
            status_color = "#FFFFFF"
        return {
            'bg': bg,
            'text_color': text_color,
            'hover_color': hover_color,
            'status_color': status_color,
            'statblock': StyleManager.get_sidebar_statblock_styles(is_dark)
        }
