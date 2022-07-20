import logging
import os.path
import threading
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph

from .ui.cfanmain import Ui_MainWindow
from .ui.cfanabout import Ui_AboutDialog
from .settings import Environment, Config
from .sensormanager import SensorManager
from .log import LogManager
from .fanmanager import FanManager
from .profilemanager import ProfileManager
from .fancurve import FanCurve, FanMode
from .graphs import FanCurveWidget


class MainWindow(QtWidgets.QMainWindow):

    manager: FanManager

    def __init__(self, fan_manager: FanManager, palette: QtGui.QPalette):
        super(MainWindow, self).__init__()

        self._palette = palette
        self._accent_color: QtGui.QColor = palette.highlight().color()
        if Config.theme == 'light':
            self._label_color = palette.dark().color()
            self._line_color = palette.mid().color()
        else:
            self._label_color = palette.light().color()
            self._line_color = palette.midlight().color()

        # load UI and run QT setup
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setFixedSize(self.width(), self.height())
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self._geometry = self.saveGeometry()

        # set the fan manager and callback
        self.manager = fan_manager
        self.manager.set_callback(self.manager_callback)

        # set up signals and main UI components
        self._init_pyqt_signals()
        self._init_graphview()
        self._init_ui()
        self._init_tray_menu()

        # apply settings to UI
        self._init_settings()

        # set up UI once
        self._update_ui()
        # run UI update loop
        self._update_ui_loop()

    def show(self):
        super(MainWindow, self).show()
        self.activateWindow()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if event is False:
            # Exit in the menu was pressed
            if self._update_timer is not None and self._update_timer.is_alive():
                self._update_timer.cancel()
                self._update_timer.join()
            if self.ui.switch_daemon.isChecked():
                Config.auto_start = True
            else:
                Config.auto_start = False
            self._toggle_manager(mode=False)
            Config.save_settings()
            QtCore.QCoreApplication.quit()
            return
        else:
            # 'X' was pressed -> don't close, but hide (minimize to tray instead)
            event.ignore()
            self._geometry = self.saveGeometry()
            self.hide()
            return

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        if self._geometry is not None:
            self.restoreGeometry(self._geometry)
        event.accept()

    def _init_pyqt_signals(self):
        """Assign QT signals to UI elements and actions"""
        self.ui.pushButton_fan1.clicked.connect(lambda: self._fan_config_button('fan1'))
        self.ui.pushButton_fan2.clicked.connect(lambda: self._fan_config_button('fan2'))
        self.ui.pushButton_fan3.clicked.connect(lambda: self._fan_config_button('fan3'))
        self.ui.pushButton_fan4.clicked.connect(lambda: self._fan_config_button('fan4'))
        self.ui.pushButton_fan5.clicked.connect(lambda: self._fan_config_button('fan5'))
        self.ui.pushButton_fan6.clicked.connect(lambda: self._fan_config_button('fan6'))

        self.ui.radioButton_off.clicked.connect(self._change_fan_mode)
        self.ui.radioButton_fixed.clicked.connect(self._change_fan_mode)
        self.ui.spinBox_fixed.valueChanged.connect(self._change_fan_mode)
        self.ui.radioButton_curve.clicked.connect(self._change_fan_mode)
        self.ui.pushButton_apply.clicked.connect(self._apply_fan_mode)

        self.channel_elements = {
            'fan1': [self.ui.icon_fan1, self.ui.pushButton_fan1, self.ui.mode_fan1, self.ui.speed_fan1,
                     self.ui.pwm_fan1, self.ui.temp_fan1],
            'fan2': [self.ui.icon_fan2, self.ui.pushButton_fan2, self.ui.mode_fan2, self.ui.speed_fan2,
                     self.ui.pwm_fan2, self.ui.temp_fan2],
            'fan3': [self.ui.icon_fan3, self.ui.pushButton_fan3, self.ui.mode_fan3, self.ui.speed_fan3,
                     self.ui.pwm_fan3, self.ui.temp_fan3],
            'fan4': [self.ui.icon_fan4, self.ui.pushButton_fan4, self.ui.mode_fan4, self.ui.speed_fan4,
                     self.ui.pwm_fan4, self.ui.temp_fan4],
            'fan5': [self.ui.icon_fan5, self.ui.pushButton_fan5, self.ui.mode_fan5, self.ui.speed_fan5,
                     self.ui.pwm_fan5, self.ui.temp_fan5],
            'fan6': [self.ui.icon_fan6, self.ui.pushButton_fan6, self.ui.mode_fan6, self.ui.speed_fan6,
                     self.ui.pwm_fan6, self.ui.temp_fan6],
        }

        self.ui.pushButton_add_profile.clicked.connect(self._add_profile_dialog)
        self.ui.pushButton_remove_profile.clicked.connect(self._remove_profile)

        self.ui.actionLoad_Profile.triggered.connect(self._load_profile_dialog)
        self.ui.actionSave_Profile.triggered.connect(self._save_profile_dialog)
        self.ui.actionSave_Settings.triggered.connect(Config.save_settings)
        self.ui.actionQuit.triggered.connect(self.closeEvent)

        self.ui.actionLight.triggered.connect(lambda: self._set_theme('light'))
        self.ui.actionDark.triggered.connect(lambda: self._set_theme('dark'))
        self.ui.actionSystem.triggered.connect(lambda: self._set_theme('system'))

        self.ui.actionAbout.triggered.connect(self._show_about_dialog)

    def _show_about_dialog(self):
        dlg = QtWidgets.QDialog(self)
        dlg.ui = Ui_AboutDialog()
        dlg.ui.setupUi(dlg)
        dlg.setWindowTitle(f"About {Environment.APP_FANCY_NAME}  (v{Environment.APP_VERSION})")
        dlg.ui.btnClose.clicked.connect(dlg.close)
        dlg.show()

    def _init_tray_menu(self):
        """Setting up tray menu"""
        tray_icon = QtGui.QIcon(":/icons/fan_grey_32.png")
        self._tray: QtWidgets.QSystemTrayIcon = QtWidgets.QSystemTrayIcon(tray_icon, self)
        self._tray.activated.connect(self.show)

        self._tray_menu = QtWidgets.QMenu(self)
        self._option_show = QtWidgets.QAction("Show")
        self._option_show.triggered.connect(self.show)
        self._option_manager = QtWidgets.QAction("Enable Fan Manager")
        self._option_manager.setCheckable(True)
        self._option_manager.triggered.connect(lambda: self._toggle_manager(self._option_manager.isChecked()))
        self._option_exit = QtWidgets.QAction("Exit")
        self._option_exit.triggered.connect(self.closeEvent)

        self._tray_menu.addAction(self._option_show)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction(self._option_manager)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction(self._option_exit)
        self._tray.setContextMenu(self._tray_menu)
        self._tray.show()

    def _init_ui(self):
        """Initialize UI elements with default values"""
        self._actiongroupTheme = QtWidgets.QActionGroup(self)
        self.ui.actionLight.setActionGroup(self._actiongroupTheme)
        self.ui.actionDark.setActionGroup(self._actiongroupTheme)
        self.ui.actionSystem.setActionGroup(self._actiongroupTheme)

        self._actiongroupLog = QtWidgets.QActionGroup(self)
        self.ui.action_Off.setActionGroup(self._actiongroupLog)
        self.ui.action_Debug.setActionGroup(self._actiongroupLog)
        self.ui.action_Info.setActionGroup(self._actiongroupLog)
        self.ui.action_Warning.setActionGroup(self._actiongroupLog)
        self.ui.action_Error.setActionGroup(self._actiongroupLog)

        self.ui.switch_daemon.set_colors(self._accent_color)

        for i in range(1, 7):
            channel = f"fan{i}"
            icon: QtWidgets.QLabel = self.channel_elements.get(channel)[0]
            button: QtWidgets.QPushButton = self.channel_elements.get(channel)[1]
            mode: QtWidgets.QLabel = self.channel_elements.get(channel)[2]
            speed: QtWidgets.QLabel = self.channel_elements.get(channel)[3]
            fan = self.manager.get_pwm_fan(channel)
            if fan:
                if Config.theme == 'light':
                    icon.setPixmap(QtGui.QPixmap(":/fans/fan_connected_dark.png"))
                else:
                    icon.setPixmap(QtGui.QPixmap(":/fans/fan_connected_grey.png"))
                button.setEnabled(True)
                mode.setText("Off")
                speed.setText("0 rpm")
            else:
                if Config.theme == 'light':
                    icon.setPixmap(QtGui.QPixmap(":/fans/fan_disconnected_light.png"))
                else:
                    icon.setPixmap(QtGui.QPixmap(":/fans/fan_disconnected_grey.png"))
                button.setEnabled(False)
                mode.setText("-")
                speed.setText("")

        self.ui.comboBox_sensors.clear()
        for sensor in SensorManager.system_sensors:
            self.ui.comboBox_sensors.addItem(sensor.get_name())

        self._active_button: Optional[QtWidgets.QPushButton] = None
        self._active_curve: Optional[FanCurve] = None
        self._active_channel: Optional[str] = None

    def _init_graphview(self):
        """Initializes the graph widgets"""
        pyqtgraph.setConfigOptions(antialias=True)

        # del self.ui.graphicsView_fancurve
        self.ui.graphicsView_fancurve = FanCurveWidget(
            self.ui.frame_fancurve,
            labels={'left': ('Fan Speed', '%'), 'bottom': ("Temperature", '°C')},
            showGrid={'x': False, 'y': False, 'alpha': 0.1},
            tickSpacing={'left': (20, 10), 'bottom': (20, 10)},
            limits=(-3, 107)
        )
        self.ui.graphicsView_fancurve.set_graph([[0, 0]], False, accent_color=self._accent_color, label_color=self._label_color, line_color=self._line_color)
        self.ui.graphicsView_fancurve.reset_graph()

        self.ui.pushButton_add.clicked.connect(self.ui.graphicsView_fancurve.add_point)
        self.ui.pushButton_remove.clicked.connect(self.ui.graphicsView_fancurve.remove_point)

        self.ui.pushButton_linear_curve.clicked.connect(self._set_fancurve_preset)
        self._set_curve_icon(self.ui.pushButton_linear_curve, ":/curves/curve_linear.png")
        self.ui.pushButton_exponential_curve.clicked.connect(self._set_fancurve_preset)
        self._set_curve_icon(self.ui.pushButton_exponential_curve, ":/curves/curve_exponential.png")
        self.ui.pushButton_logistic_curve.clicked.connect(self._set_fancurve_preset)
        self._set_curve_icon(self.ui.pushButton_logistic_curve, ":/curves/curve_logistic.png")
        self.ui.pushButton_semi_exp_curve.clicked.connect(self._set_fancurve_preset)
        self._set_curve_icon(self.ui.pushButton_semi_exp_curve, ":/curves/curve_semi_exp.png")
        self.ui.pushButton_semi_logistic_curve.clicked.connect(self._set_fancurve_preset)
        self._set_curve_icon(self.ui.pushButton_semi_logistic_curve, ":/curves/curve_semi_log.png")

    @staticmethod
    def _set_curve_icon(button: QtWidgets.QPushButton, icon_file: str):
        pixmap: QtGui.QPixmap = QtGui.QPixmap(icon_file)
        button_icon: QtGui.QIcon = QtGui.QIcon(pixmap)
        button.setIcon(button_icon)

    def _init_settings(self):
        """Apply settings to UI elements"""
        self.ui.actionLight.setChecked(True)
        if Config.theme == 'dark':
            self.ui.actionDark.setChecked(True)
        elif Config.theme == 'system':
            self.ui.actionSystem.setChecked(True)

        if Config.interval > 0.0:
            self.ui.slider_interval.setValue(int(Config.interval))
            self.ui.slider_interval.setToolTip(f"{int(Config.interval)}s")
        self.ui.slider_interval.valueChanged.connect(self._set_interval)

        log_index = int(Config.log_level / 10)
        self._actiongroupLog.actions()[log_index].setChecked(True)
        self.ui.action_Off.triggered.connect(lambda: self._set_log_level(logging.NOTSET))
        self.ui.action_Debug.triggered.connect(lambda: self._set_log_level(logging.DEBUG))
        self.ui.action_Info.triggered.connect(lambda: self._set_log_level(logging.INFO))
        self.ui.action_Warning.triggered.connect(lambda: self._set_log_level(logging.WARNING))
        self.ui.action_Error.triggered.connect(lambda: self._set_log_level(logging.ERROR))

        self.ui.switch_daemon.setChecked(Config.auto_start)
        self.ui.switch_daemon.toggled.connect(lambda: self._toggle_manager(self.ui.switch_daemon.isChecked()))

        self.ui.comboBox_profiles.currentIndexChanged.connect(lambda: self._apply_profile(self.ui.comboBox_profiles.currentText(), self.ui.switch_daemon.isChecked()))
        self._set_profiles_combobox(ProfileManager.get_profile_from_file_name(Config.profile_file))

    def _toggle_manager(self, mode: bool):
        self.ui.slider_interval.setEnabled(mode)
        self.ui.label_Interval.setEnabled(mode)
        self._option_manager.setChecked(mode)
        self.manager.toggle_manager(mode)

    def manager_callback(self, aborted: bool):
        LogManager.logger.debug("Fan manager thread callback")
        if aborted:
            LogManager.logger.warning("Fan manager was aborted")
            palette = self.ui.slider_interval.palette()
            Config.auto_start = False
            self.ui.switch_daemon.setChecked(False)
            self.ui.slider_interval.setEnabled(False)
            self.ui.label_Interval.setEnabled(False)
            self._option_manager.setChecked(False)
            palette.setColor(palette.Highlight, palette.dark().color())
            self.ui.slider_interval.setPalette(palette)
        else:
            LogManager.logger.info("Fan manager thread ended normally")

    def _fan_config_button(self, channel: str):
        self.ui.spinBox_fixed.blockSignals(True)
        button: QtWidgets.QPushButton = self.sender()
        font = QtGui.QFont()
        if self._active_button is not button:
            self._active_channel = channel
            fan_curve = self.manager.get_channel_fancurve(channel)
            fan_sensor = self.manager.get_channel_sensor(channel)
            self.ui.groupBox_mode.setEnabled(True)
            if fan_curve.get_fan_mode() == FanMode.Off:
                self.ui.radioButton_off.setChecked(True)
                self.ui.spinBox_fixed.setEnabled(False)
                self.ui.comboBox_sensors.setEnabled(False)
                self.ui.comboBox_sensors.setCurrentIndex(0)
                self.ui.pushButton_add.setEnabled(False)
                self.ui.pushButton_remove.setEnabled(False)
                self.ui.pushButton_linear_curve.setEnabled(False)
                self.ui.pushButton_exponential_curve.setEnabled(False)
                self.ui.pushButton_logistic_curve.setEnabled(False)
                self.ui.pushButton_semi_exp_curve.setEnabled(False)
                self.ui.pushButton_semi_logistic_curve.setEnabled(False)
            elif fan_curve.get_fan_mode() == FanMode.Fixed:
                self.ui.radioButton_fixed.setChecked(True)
                self.ui.spinBox_fixed.setEnabled(True)
                self.ui.comboBox_sensors.setEnabled(False)
                self.ui.comboBox_sensors.setCurrentIndex(0)
                self.ui.spinBox_fixed.setValue(fan_curve.get_curve_fixed_speed())
                self.ui.pushButton_add.setEnabled(False)
                self.ui.pushButton_remove.setEnabled(False)
                self.ui.pushButton_linear_curve.setEnabled(False)
                self.ui.pushButton_exponential_curve.setEnabled(False)
                self.ui.pushButton_logistic_curve.setEnabled(False)
                self.ui.pushButton_semi_exp_curve.setEnabled(False)
                self.ui.pushButton_semi_logistic_curve.setEnabled(False)
            else:
                self.ui.radioButton_curve.setChecked(True)
                self.ui.spinBox_fixed.setEnabled(False)
                self.ui.comboBox_sensors.setEnabled(True)
                self.ui.comboBox_sensors.setCurrentIndex(fan_sensor)
                self.ui.pushButton_add.setEnabled(True)
                self.ui.pushButton_remove.setEnabled(True)
                self.ui.pushButton_linear_curve.setEnabled(True)
                self.ui.pushButton_exponential_curve.setEnabled(True)
                self.ui.pushButton_logistic_curve.setEnabled(True)
                self.ui.pushButton_semi_exp_curve.setEnabled(True)
                self.ui.pushButton_semi_logistic_curve.setEnabled(True)
            if self._active_button is not None:
                font.setBold(False)
                font.setWeight(50)
                self._active_button.setFont(font)
                self._set_button_color(self._active_button, self._palette.button().color(), self._palette.buttonText().color())
            font.setBold(True)
            font.setWeight(75)
            button.setFont(font)
            self._set_button_color(button, self._palette.highlight().color(), self._palette.highlightedText().color())
            self._active_button = button
            self._active_curve = fan_curve
            self._show_fan_graph(fan_curve.get_fan_mode() == FanMode.Curve)
        else:
            font = QtGui.QFont()
            font.setBold(False)
            font.setWeight(50)
            button.setFont(font)
            self._set_button_color(button, self._palette.button().color(), self._palette.buttonText().color())
            button.setAutoExclusive(False)
            button.setChecked(False)
            self.ui.slider_interval.setFocus()
            button.setAutoExclusive(True)
            self.ui.radioButton_off.setAutoExclusive(False)
            self.ui.radioButton_fixed.setAutoExclusive(False)
            self.ui.radioButton_curve.setAutoExclusive(False)
            self.ui.radioButton_off.setChecked(False)
            self.ui.radioButton_fixed.setChecked(False)
            self.ui.spinBox_fixed.setValue(0)
            self.ui.radioButton_curve.setChecked(False)
            self.ui.comboBox_sensors.setCurrentIndex(0)
            self.ui.groupBox_mode.setEnabled(False)
            self.ui.radioButton_off.setAutoExclusive(True)
            self.ui.radioButton_fixed.setAutoExclusive(True)
            self.ui.radioButton_curve.setAutoExclusive(True)
            self._active_button = None
            self._active_curve = None
            self._active_channel = None
            self.ui.graphicsView_fancurve.reset_graph()
        self.ui.spinBox_fixed.blockSignals(False)

    @staticmethod
    def _set_button_color(button: QtWidgets.QPushButton, background_color: QtGui.QColor, text_color: QtGui.QColor):
        palette = button.palette()
        palette.setColor(palette.Button, background_color)
        palette.setColor(palette.ButtonText, text_color)
        button.setPalette(palette)

    def _change_fan_mode(self):
        if self._active_channel is not None:
            if self.ui.radioButton_off.isChecked():
                self.ui.spinBox_fixed.setEnabled(False)
                self.ui.comboBox_sensors.setEnabled(False)
                self._active_curve = FanCurve.zero_rpm_curve()
                self.ui.pushButton_add.setEnabled(False)
                self.ui.pushButton_remove.setEnabled(False)
                self.ui.pushButton_linear_curve.setEnabled(False)
                self.ui.pushButton_exponential_curve.setEnabled(False)
                self.ui.pushButton_logistic_curve.setEnabled(False)
                self.ui.pushButton_semi_exp_curve.setEnabled(False)
                self.ui.pushButton_semi_logistic_curve.setEnabled(False)
            elif self.ui.radioButton_fixed.isChecked():
                self.ui.spinBox_fixed.setEnabled(True)
                self.ui.comboBox_sensors.setEnabled(False)
                self._active_curve = FanCurve.fixed_speed_curve(self.ui.spinBox_fixed.value())
                self.ui.pushButton_add.setEnabled(False)
                self.ui.pushButton_remove.setEnabled(False)
                self.ui.pushButton_linear_curve.setEnabled(False)
                self.ui.pushButton_exponential_curve.setEnabled(False)
                self.ui.pushButton_logistic_curve.setEnabled(False)
                self.ui.pushButton_semi_exp_curve.setEnabled(False)
                self.ui.pushButton_semi_logistic_curve.setEnabled(False)
            elif self.ui.radioButton_curve.isChecked():
                self.ui.spinBox_fixed.setEnabled(False)
                self.ui.comboBox_sensors.setEnabled(True)
                self._active_curve = FanCurve.linear_curve()
                self.ui.pushButton_add.setEnabled(True)
                self.ui.pushButton_remove.setEnabled(True)
                self.ui.pushButton_linear_curve.setEnabled(True)
                self.ui.pushButton_exponential_curve.setEnabled(True)
                self.ui.pushButton_logistic_curve.setEnabled(True)
                self.ui.pushButton_semi_exp_curve.setEnabled(True)
                self.ui.pushButton_semi_logistic_curve.setEnabled(True)
            self._show_fan_graph(self.ui.radioButton_curve.isChecked())
        else:
            LogManager.logger.warning("Can't change fan mode - no active channel")

    def _apply_fan_mode(self):
        sensor_id = 0
        if self.ui.radioButton_curve.isChecked():
            sensor_id = self.ui.comboBox_sensors.currentIndex()
            graph_data = self.ui.graphicsView_fancurve.get_graph_data()
            self._active_curve.set_curve_from_graph_points(graph_data)
        self.manager.apply_fan_mode(self._active_channel, sensor_id, self._active_curve, profile=self.ui.comboBox_profiles.currentText())

    def _set_fancurve_preset(self):
        preset_button: QtWidgets.QPushButton = self.sender()
        if preset_button is self.ui.pushButton_linear_curve:
            self._active_curve = FanCurve.linear_curve()
        elif preset_button is self.ui.pushButton_exponential_curve:
            self._active_curve = FanCurve.exponential_curve()
        elif preset_button is self.ui.pushButton_logistic_curve:
            self._active_curve = FanCurve.logistic_curve()
        elif preset_button is self.ui.pushButton_semi_exp_curve:
            self._active_curve = FanCurve.semi_exponential_curve()
        elif preset_button is self.ui.pushButton_semi_logistic_curve:
            self._active_curve = FanCurve.semi_logistic_curve()
        else:
            self._active_curve = FanCurve.fixed_speed_curve(0)
        self._show_fan_graph(self.ui.radioButton_curve.isChecked())

    def _show_fan_graph(self, draw_lines: bool):
        graph_data = self._active_curve.get_graph_points_from_curve()
        self.ui.graphicsView_fancurve.set_graph(graph_data, draw_lines, accent_color=self._accent_color, label_color=self._label_color, line_color=self._line_color)
        if draw_lines:
            valid, _, _, fan_percent, _, fan_temperature = self.manager.get_channel_status(self._active_channel)
            if valid:
                self.ui.graphicsView_fancurve.update_line('currTemp', round(fan_temperature, 1))
                self.ui.graphicsView_fancurve.update_line('currFan', fan_percent)

    def _set_profiles_combobox(self, select_profile: str):
        self.ui.comboBox_profiles.clear()
        self.ui.comboBox_profiles.addItems(ProfileManager.profiles)
        self.ui.comboBox_profiles.model().sort(0)
        if select_profile:
            self.ui.comboBox_profiles.setCurrentText(select_profile)

    def _apply_profile(self, profile_name: str, auto_start: bool):
        if self._active_button is not None:
            self._active_button.click()
        self._toggle_manager(mode=False)
        window_title = Environment.APP_FANCY_NAME
        success, applied_profile = self.manager.set_profile(profile_name)
        if success:
            window_title += " - " + applied_profile
            if auto_start:
                self._toggle_manager(mode=True)
            self.ui.pushButton_remove_profile.setEnabled(True)
        else:
            self.ui.comboBox_profiles.setCurrentIndex(0)
            self.ui.pushButton_remove_profile.setEnabled(False)
        self.setWindowTitle(window_title)

    def _load_profile_dialog(self):
        files = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Profile', Environment.settings_path, "Profile files (*.cfp)")
        if files[0] != '':
            # new_profile = ProfileManager.add_profile(files[0])
            new_profile = self.manager.load_profile(files[0])
            self._set_profiles_combobox(new_profile)

    def _save_profile_dialog(self):
        files = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Profile', Environment.settings_path, "Profile files (*.cfp)")
        if files[0] != '':
            profile_name = os.path.splitext(os.path.basename(files[0]))[0]
            self._save_profile(profile_name)

    def _add_profile_dialog(self):
        profile_name, ok = QtWidgets.QInputDialog.getText(self, Environment.APP_FANCY_NAME, 'Add new profile:')
        if ok:
            self._save_profile(profile_name)

    def _save_profile(self, profile_name):
        success, _ = self.manager.save_profile(profile_name)
        if success:
            self._set_profiles_combobox(profile_name)

    def _remove_profile(self):
        profile = self.ui.comboBox_profiles.currentText()
        file_name = ProfileManager.get_file_name_from_profile(profile)
        if self.ui.comboBox_profiles.currentIndex() > 0 and file_name:
            response = QtWidgets.QMessageBox.question(self, Environment.APP_FANCY_NAME,
                                                      f"Are you sure you want to permanently delete the profile '{file_name}'?",
                                                      QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Yes,
                                                      QtWidgets.QMessageBox.Cancel)
            if response == QtWidgets.QMessageBox.Yes:
                if ProfileManager.remove_profile(profile):
                    self._set_profiles_combobox(profile)

    @staticmethod
    def _set_log_level(log_level: int):
        if 0 <= log_level < 40:
            Config.log_level = log_level
            LogManager.set_log_level(log_level)

    def _set_interval(self):
        new_interval: float = round(float(self.ui.slider_interval.value()), 1)
        if new_interval >= 1.0:
            self.ui.slider_interval.setToolTip(f"{int(new_interval)}s")
            Config.interval = float(new_interval)
            LogManager.logger.debug(f"Setting new update interval {Config.interval}")
            self.manager.update_interval(Config.interval)

    def _set_theme(self, theme: str):
        response = QtWidgets.QMessageBox.information(self, Environment.APP_FANCY_NAME,
                                                  f"The change in color theme will be applied after a restart of the program.",
                                                  QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)
        Config.theme = theme

    def _update_ui_loop(self):
        self._update_timer = threading.Timer(1.9, self._update_ui_loop)
        self._update_timer.daemon = True
        self._update_timer.start()
        if not self.isHidden():
            self._update_ui()

    def _update_ui(self):
        # if not self.isHidden() and self._is_initialized:
        if self.manager:
            LogManager.logger.debug("Updating UI")
            for i in range(1, 7):
                channel = f"fan{i}"
                mode: QtWidgets.QLabel = self.channel_elements.get(channel)[2]
                speed: QtWidgets.QLabel = self.channel_elements.get(channel)[3]
                pwm: QtWidgets.QLabel = self.channel_elements.get(channel)[4]
                temp: QtWidgets.QLabel = self.channel_elements.get(channel)[5]
                valid, fan_mode, fan_pwm, fan_percent, fan_rpm, fan_temperature = self.manager.get_channel_status(channel)
                if valid:
                    if fan_mode == FanMode.Off:
                        mode.setText("Off")
                        speed.setText("")
                        pwm.setText("")
                        temp.setText("")
                    else:
                        if fan_mode == FanMode.Fixed:
                            mode.setText("Fixed")
                            temp.setText("")
                        else:
                            mode.setText("Dynamic")
                            temp.setText(f"{str(round(fan_temperature, 1))} °C")
                            if self._active_channel == channel:
                                self.ui.graphicsView_fancurve.update_line('currTemp', round(fan_temperature, 1))
                                self.ui.graphicsView_fancurve.update_line('currFan', fan_percent)
                        speed.setText(f"{str(fan_rpm)} rpm")
                        pwm.setText(f"{str(fan_percent)} %")
                else:
                    mode.setText("")
                    speed.setText("")
                    pwm.setText("")
                    temp.setText("")
