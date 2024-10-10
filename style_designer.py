#!/usr/bin/env python3
# Copyright (c) 2023 Jim Sloot (persei802@gmail.com)
# Inspired by QDarkStyleSheet project by Colin Duquesnoy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import os
import sys
import json

try:
    import qtsass
except ImportError as e:
    print(e)
    print("qtsass is required to compile stylesheets")
    print("sudo apt install python3-qtsass")

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QFile, Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel, QLineEdit, QColorDialog, QFileDialog, QMessageBox
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor

HERE = os.path.dirname(os.path.abspath(__file__))

HEADER_SCSS = '''
//
//    WARNING! File created programmatically.
//    All changes made in this file will be lost!
//
'''

HEADER_QSS = '''
/* 
    WARNING! File created programmatically by qtsass.
    All changes made in this file will be lost!
*/
'''


# TabWidget pages
EXTRAS = 0
WIDGET = 1
VARIABLES = 2
STYLESHEET = 3
UNRESOLVED = 4

class Preview_Widget(QtWidgets.QMainWindow):
    def __init__(self, uifile):
        super(Preview_Widget, self).__init__()
        try:
            self.instance = uic.loadUi(uifile, self)
        except AttributeError as e:
            print("Error: ", e)
        

class CustomLineEdit(QLineEdit):
    line_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == 1:
            self.line_clicked.emit()


class Create_StyleSheet(QtWidgets.QMainWindow):
    def __init__(self, style=None):
        super(Create_StyleSheet, self).__init__()
        self.style = style
        self.preview = None
        self.current_label = None
        self.current_line = None
        self.qtsass_installed = True
        self.rows = 32
        self.palette_dict = {}
        self.extras_dict = {}
        self.data_dict = {}
        self.unresolved = []
        # file paths
        self.palette_file = None
        self.var_file = None
        self.scss_file = None
        self.qss_file = None
        self.widget_path = None
        self.widget_file = ''

        # Load the UI file:
        ui_file = os.path.join(HERE, 'style_designer.ui')
        try:
            self.instance = uic.loadUi(ui_file, self)
            self.instance.setWindowTitle("Style Designer for Qt Widgets")
        except AttributeError as e:
            print("Error: ", e)

        if not 'qtsass' in sys.modules:
            self.qtsass_installed = False

        # connect the lineEdit signals
        for i in range(1, self.rows+1):
            self[f"code_A{i}"].line_clicked.connect(self.color_clicked)
            self[f"code_A{i}"].returnPressed.connect(self.color_return)

        self.TextEdit_Extras.textChanged.connect(lambda: self.led_palette.setState(True))
        self.TextEdit_Widget.textChanged.connect(lambda: self.led_widget.setState(True))
        self.lineEdit_search.textChanged.connect(self.search_text)
        self.statusBar.addPermanentWidget(self.widget_edit_leds)
        
        # connect the widget signals
        self.action_openPalette.triggered.connect(lambda: self.load_palette())
        self.action_openWidget.triggered.connect(self.load_widget)
        self.action_openUI.triggered.connect(self.load_uifile)
        self.action_CloseUI.triggered.connect(self.close_uifile)
        self.action_SaveAs.triggered.connect(self.save_as)
        self.action_SavePalette.triggered.connect(self.save_palette)
        self.action_SaveWidget.triggered.connect(self.save_widget)
        self.action_CreateVariables.triggered.connect(self.create_variables)
        self.action_CompileStylesheet.triggered.connect(self.compile_stylesheet)
        self.action_PreviewStylesheet.triggered.connect(self.preview_stylesheet)
        self.action_Exit.triggered.connect(self.close_program)
        self.action_help.triggered.connect(self.view_help)

        if self.style is not None:
            self.palette_file = os.path.join(self.style, f"{self.style}.json")
            self.set_paths()
            self.load_palette(self.style)

    # this prevents menubar hovering from clearing the statusBar
    def event(self, event):
        if event.type() == QtCore.QEvent.StatusTip:
            return True
        return super().event(event)

    def preview_stylesheet(self):
        if self.action_PreviewStylesheet.isChecked():
            file = QFile(self.qss_file)
            if not file.open(QFile.ReadOnly):
                self.statusBar.showMessage(f"Could not open {self.qss_file}")
                return
            data = file.readAll()
            text = str(data.data(), encoding='utf-8')
            if self.preview is None:
                self.setStyleSheet(text)
            else:
                self.preview.setStyleSheet(text)
                self.preview.show()
        else:
            if self.preview is None:
                self.setStyleSheet('')
            else:
                self.preview.setStyleSheet('')
                self.preview.hide()
            
    def load_palette(self, style=None):
        if style is None:
            dialog = QFileDialog(self)
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            caption = 'Open stylesheet palette file'
            _filter = 'Stylesheet palette (*.json)'
            _dir = os.path.join(HERE, self.style) if not self.style is None else HERE
            fileName, _ =  dialog.getOpenFileName(None, caption, _dir, _filter, options=options)
            if not fileName: return
            if fileName.endswith('.json'):
                dirname = os.path.dirname(fileName)
                self.style = os.path.basename(dirname)
                self.palette_file = fileName
                self.set_paths()
            else:
                self.statusBar.showMessage("Palette file must end with .json")
                return
        # open palette file and fill in color table
        if os.path.exists(self.palette_file):
            with open(self.palette_file, 'r') as json_file:
                data = json.load(json_file)
            self.palette_dict = data.get('palette')
            self.extras_dict = data.get('extras')
            self.parse_palette()
            self.parse_extras()
        else:
            self.statusBar.showMessage(f"{self.palette_file} not found")
            return
        # check for variables file
        if self.var_file is not None:
            if os.path.exists(self.var_file):
                with open(self.var_file, 'r') as var_file:
                    data = var_file.read()
                self.TextView_Variables.setPlainText(data)
                self.tabWidget.setCurrentIndex(EXTRAS)
        # check for qss file
        if self.qss_file is not None:
            if os.path.exists(self.qss_file):
                with open(self.qss_file, 'r') as qss_file:
                    data = qss_file.read()
                self.TextView_Stylesheet.setPlainText(data)
        self.led_palette.setState(False)

    def load_widget(self):
        dialog = QFileDialog(self)
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        caption = 'Open widget file'
        _filter = "Widget definitions (*.scss)"
        _dir = self.widget_path
        fileName, _ =  dialog.getOpenFileName(None, caption, _dir, _filter, options=options)
        self.widget_file = fileName
        if fileName is None: return
        if not os.path.exists(fileName):
            self.statusBar.showMessage(f"File {fileName} not found")
            return
        with open(self.widget_file, 'r') as widget_file:
            data = widget_file.read()
        self.TextEdit_Widget.setPlainText(data)
        self.lbl_widget_path.setText(self.widget_file)
        self.tabWidget.setCurrentIndex(WIDGET)
        self.led_widget.setState(False)

    def load_uifile(self):
        if not self.preview is None:
            self.statusBar.showMessage("Can only open 1 UI File at a time")
            return
        dialog = QFileDialog(self)
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        caption = 'Open UI file'
        _filter = "Qt Designer Files (*.ui)"
        _dir = 'self.style'
        fileName, _ =  dialog.getOpenFileName(None, caption, _dir, _filter, options=options)
        if not fileName: return
        try:
            self.preview = Preview_Widget(fileName)
            self.preview.show()
        except Exception as error:
            print(error)
            self.statusBar.showMessage(f"Could not open {fileName}")

    def close_uifile(self):
        if self.preview is None: return
        self.preview.close()
        self.preview = None

    def save_palette(self):
        if self.style is None: return
        if not os.path.exists(self.style):
            os.makedirs(self.style)
            with open(self.palette_file, "w") as fn:
                pass
            self.set_paths()
            self.statusBar.showMessage(f"Created new style folder {self.style}")
        self.update_palette_dict()
        self.update_extras_dict()
        self.data_dict = {'palette': self.palette_dict,
                          'extras': self.extras_dict}
        with open(self.palette_file, 'w') as json_file:
            json.dump(self.data_dict, json_file, indent=4)
        self.statusBar.showMessage(f"Saved {self.palette_file}")
        self.led_palette.setState(False)

    def choose_color(self):
        color = QColorDialog.getColor()
        color_name = color.name()
        if isinstance(self.current_label, QLabel) \
            and isinstance(self.current_line, QLineEdit) \
            and color.isValid():
            self.current_line.clear()
            self.current_line.setText(color_name)
            self.set_color_box(self.current_label, color_name)

    def save_as(self):
        dialog = QFileDialog(self)
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        caption = 'SaveAs'
        _filter = "Style Designer Files (*.json)"
        _dir = HERE
        fileName, _ =  dialog.getSaveFileName(self, caption, _dir, _filter, options=options)
        if not fileName: return
        root, ext = os.path.splitext(fileName)
        if ext == '.json':
            pass
        elif ext == '':
            fileName = fileName + '.json'
        else:
            self.statusBar.showMessage("Palette file must end with .json")
            return
        dirname = os.path.dirname(fileName)
        self.style = os.path.basename(dirname)
        self.palette_file = fileName
        self.set_paths()
        self.save_palette()

    def save_widget(self):
        if self.widget_file == '':
            self.statusBar.showMessage("No widget file is open")
            return
        text = self.TextEdit_Widget.toPlainText()
        with open(self.widget_file, 'w') as widget_file:
            widget_file.write(text)
        self.statusBar.showMessage(f"Saved {self.widget_file}")
        self.led_widget.setState(False)

    def create_variables(self):
        if self.var_file is None: return
        if not os.path.exists(self.var_file):
            with open(self.var_file, "w") as fn:
                pass
        # check if palette needs to be saved
        if self.led_palette.getState():
            self.save_palette()
        self.unresolved = []
        scss = self.palette_to_scss()
        data = '\n'.join(str(item) for item in self.unresolved)
        self.TextView_Unresolved.setPlainText(data)
        if scss is None: return

        data = '\n'.join([str(item) for item in scss])
        text = HEADER_SCSS + data
        # save created variables to file
        with open(self.var_file, 'w') as var_file:
            var_file.write(text)

        self.TextView_Variables.setPlainText(text)
        self.lbl_var_path.setText(self.var_file)
        self.tabWidget.setCurrentIndex(VARIABLES)
        self.statusBar.showMessage(f"Created {self.var_file}")

    def compile_stylesheet(self):
        if not self.qtsass_installed:
            self.statusBar.showMessage("Cannot compile - qtsass is not installed")
            return
        if self.var_file is None: return
        if not os.path.exists(self.var_file):
            self.statusBar.showMessage(f"Could not find {self.var_file}")
            return
        if self.scss_file is None: return
        if not os.path.exists(self.scss_file):
            self.statusBar.showMessage(f"Could not find {self.scss_file} - creating a new one")
            if not os.path.exists(self.widget_path):
                self.statusBar.showMessage("No widgets directory found")
                return
            widget_files = os.listdir(self.widget_path)
            widgets = [f for f in widget_files if os.path.isfile(os.path.join(self.widget_path, f))]
            with open(self.scss_file, 'w') as sass_file:
                sass_file.write("@import 'variables';\n")
                for widget in widgets:
                    wname = os.path.basename(widget)
                    wname = wname.strip('_')
                    sass_file.write(f"@import 'widgets/{wname}';\n")
        # check if palette needs to be saved
        if self.led_widget.getState():
            self.save_widget()
        if self.led_palette.getState():
            self.save_palette()
            self.create_variables()
        try:
            qtsass.compile_filename(self.scss_file, self.qss_file, output_style='expanded')
            with open(self.qss_file, 'r') as file:
                data = file.read()
            data = HEADER_QSS + data
            with open(self.qss_file, 'w') as file:
                file.write(data)
            self.TextView_Stylesheet.setPlainText(data)
            self.tabWidget.setCurrentIndex(STYLESHEET)
            self.statusBar.showMessage(f"Stylesheet written to {self.qss_file}")
        except Exception as error:
            print(error)
            self.statusBar.showMessage(f"There was an error when compiling {self.qss_file}")

    def view_help(self):
        help_file = os.path.join(HERE, 'help.txt')
        if not os.path.exists(help_file):
            self.statusBar.showMessage(f"{help_file} not found")
            return
        self.statusBar.showMessage("Help not yet implemented")

    def close_program(self):
        if not self.preview is None:
            self.preview.close()
        icon = QMessageBox.Question
        title = "Close Style_Designer"
        info = "Do you want to save unsaved files?"
        buttons = QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        rtn = self.message_box(icon, title, info, buttons)
        if rtn == QMessageBox.Save:
            if self.led_palette.getState():
                print("Saving palette")
                self.save_palette()
            if self.led_widget.getState():
                print("Saving widget")
                self.save_widget()
            self.close()
        elif rtn == QMessageBox.Discard:
            self.close()

    def parse_palette(self):
        for index, (var, code) in enumerate(self.palette_dict.items()):
            idx = index + 1
            if var.startswith('A'):
                var = ''
            self[f'var_A{idx}'].setText(var)
            self[f'code_A{idx}'].setText(code)
            if not code == '':
                lbl = self[f'color_A{idx}']
                self.set_color_box(lbl, code)

    def parse_extras(self):
        lines = []
        for index, (key, val) in enumerate(self.extras_dict.items()):
            line = f'{key}={val}'
            lines.append(line)
        text = "\n".join(lines)
        self.TextEdit_Extras.setPlainText(text)

    def resolve(self, part):
        sub = part.split()
        for i in range(len(sub)):
            if sub[i].startswith('$'):
                sub[i] = sub[i].strip('$')
                x = sub[i].strip(')')
                x = x.strip(',')
                if x in self.palette_dict.keys():
                    code = self.palette_dict[x]
                    if code.startswith('#'):
                        sub[i] = sub[i].replace(x, code)
                    else:
                        self.unresolved.append(sub[i])
                else:
                    self.unresolved.append(sub[i])
        line = ' '.join(sub)
        return line

    def color_return(self):
        line = self.sender()
        label = self['color' + line.objectName().strip('code')]
        color = line.text()
        if color == "" or len(color) != 7 or not color.startswith('#'):
            self.statusBar.showMessage("Invalid color specification")
        else:
            self.set_color_box(label, color)
        self.led_palette.setState(True)

    def color_clicked(self):
        line = self.sender()
        self.current_label = self['color' + line.objectName().strip('code')]
        self.current_line = line
        self.choose_color()
        self.led_palette.setState(True)

    def set_color_box(self, box, color):
        self.statusBar.showMessage(f"Set {box.objectName()} to {color}")
        box.setStyleSheet(f"background: {color};")
        self.led_palette.setState(True)
        
    def set_paths(self):
        self.var_file = os.path.join(self.style, "_variables.scss")
        self.scss_file = os.path.join(self.style, f"{self.style}.scss")
        self.qss_file = os.path.join(self.style, f"{self.style}.qss")
        self.widget_path = os.path.join(self.style, 'widgets')
        self.lbl_palette_path.setText(self.palette_file)
        self.lbl_var_path.setText(self.var_file)
        self.lbl_style_path.setText(self.qss_file)
        
    def update_palette_dict(self):
        self.palette_dict.clear()
        for i in range(1, self.rows+1):
            index = f'A{i}'
            code = self[f"code_A{i}"].text()
            var = self[f"var_A{i}"].text()
            if not code.startswith('#'):
                code = ''
            if var == '':
                var = index
            self.palette_dict[var] = code
        
    def update_extras_dict(self):
        self.extras_dict.clear()
        text = self.TextEdit_Extras.toPlainText()
        lines = text.splitlines()
        for line in lines:
            parts = line.split('=')
            if len(parts) > 1:
                self.extras_dict[parts[0]] = parts[1]

    def message_box(self, icon, title, info, buttons):
        msg = QMessageBox()
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(info)
        msg.setStandardButtons(buttons)
        return msg.exec_()

    def palette_to_scss(self):
        lines = []
        lines.append(f'// Palette variables for {self.style}')
        try:
            for i in range(1, self.rows+1):
                var = self[f"var_A{i}"].text()
                if var == '': continue
                code = self[f"code_A{i}"].text()
                lines.append(f"${var}: {code};")
        except AttributeError as error:
            print(error)
            self.statusBar.showMessage("Creation of palette variables failed")
            return None
        lines.append('// Extras')
        self.update_palette_dict()
        try:
            text = self.TextEdit_Extras.toPlainText()
            extras = text.splitlines()
            for extra in extras:
                if extra.startswith('#'): continue
                parts = extra.split('=')
                if len(parts) > 1:
                    val = self.resolve(parts[1])
                    lines.append(f'${parts[0]}: {val};')
        except AttributeError as error:
            print(error)
            self.statusBar.showMessage("Creation of extra variables failed")
            return None
        return lines

    def search_text(self):
        cursor = self.TextView_Stylesheet.textCursor()
        cursor.select(QTextCursor.Document)
        fmt = QTextCharFormat()
        cursor.setCharFormat(fmt)
        search_term = self.lineEdit_search.text()
        if search_term:
            cursor = self.TextView_Stylesheet.textCursor()
            text = self.TextView_Stylesheet.toPlainText()
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(QColor('yellow'))
            cursor.setPosition(0)
            while not cursor.isNull() and cursor.position() < len(text):
                cursor = self.TextView_Stylesheet.document().find(search_term, cursor)
                if cursor.hasSelection():
                    cursor.mergeCharFormat(highlight_format)

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        return setattr(self, item, value)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    if len(sys.argv) == 2:
        w = Create_StyleSheet(sys.argv[1])
    else:
        w = Create_StyleSheet()
    w.show()
    sys.exit( app.exec_() )
