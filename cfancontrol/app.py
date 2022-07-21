import os.path
import sys
from typing import List

from PyQt5 import QtGui, QtWidgets, QtCore

from .gui import MainWindow
from .fanmanager import FanManager
from .settings import Environment


def main(manager: FanManager, show_app=True, theme='system'):
    # Initialize application
    app = QtWidgets.QApplication(sys.argv)
    if theme != 'system':
        app.setStyle('Fusion')
        app.setPalette(load_color_scheme(theme))
    app_icon = QtGui.QIcon()
    app_icon.addPixmap(QtGui.QPixmap(":/icons/commander_icon.png"))
    app.setWindowIcon(app_icon)

    # Create main window
    mainwin = MainWindow(manager, app.palette())

    # Show GUI elements and start application
    if show_app:
        mainwin.show()
    app.exec()


def warning_already_running():
    app = QtWidgets.QApplication(sys.argv)
    response = QtWidgets.QMessageBox.warning(None, Environment.APP_FANCY_NAME,
                                             f"Cannot start {Environment.APP_NAME} as an instance is already running.\n\n"
                                             f"Check '{Environment.pid_path}/{Environment.APP_NAME}.pid' and remove it if necessary.",
                                             QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)


def load_color_scheme(scheme: str) -> QtGui.QPalette:
    palette = QtGui.QPalette()
    path = os.path.dirname(__file__)
    if scheme == 'dark':
        file_name = "ui/themes/dark.conf"
    elif scheme == 'light':
        file_name = "ui/themes/light.conf"
    else:
        return palette
    file_name = os.path.join(path, file_name)
    color_settings: QtCore.QSettings = QtCore.QSettings(file_name, QtCore.QSettings.IniFormat)
    color_settings.beginGroup("ColorScheme")
    active_colors: List = color_settings.value("active_colors")
    inactive_colors: List = color_settings.value("inactive_colors")
    disabled_colors: List = color_settings.value("disabled_colors")
    color_settings.endGroup()
    ncolor_roles = QtGui.QPalette.NColorRoles - 1
    if len(active_colors) == ncolor_roles and len(inactive_colors) == ncolor_roles and len(disabled_colors) == ncolor_roles:
        for i in range(ncolor_roles):
            role: QtGui.QPalette.ColorRole = QtGui.QPalette.ColorRole(i)
            palette.setColor(QtGui.QPalette.Active, role, QtGui.QColor(active_colors[i]))
            palette.setColor(QtGui.QPalette.Inactive, role, QtGui.QColor(inactive_colors[i]))
            palette.setColor(QtGui.QPalette.Disabled, role, QtGui.QColor(disabled_colors[i]))
    return palette


if __name__ == "__main__":
    # the_settings = Settings()
    the_manager = FanManager()
    main(the_manager, show_app=True, theme='light')
