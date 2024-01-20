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

try:
    import qtsass
except ImportError as e:
    print(e)
    print("qtsass is required to compile stylesheets")
    print("sudo apt install python3-qtsass")

from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QFile, QTextStream, Qt, pyqtSignal
from PyQt5.QtWidgets import (QLabel, QLineEdit, QColorDialog, QFileDialog,
                             QPlainTextEdit, QMessageBox, QWidget)

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
        self.setWindowTitle("Stylesheet Designer for Qt5")
        self.preview = None
        self.current_label = None
        self.current_line = None
        self.qtsass_installed = True
        self.edit_role = None
        self.rows = 16
        # file paths
        self.palette_file = None
        self.extras_file = None
        self.var_file = None
        self.qtsass_file = None
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

        if self.style is None:
            self.lbl_style.setText("Undefined")
        else:
            self.lbl_style.setText(self.style)
            self.palette_file = os.path.join(self.style, f"{self.style}_palette.txt")
            self.set_paths()

        if not 'qtsass' in sys.modules:
            self.qtsass_installed = False

        # connect the lineEdit signals
        for i in range(1, self.rows+1):
            self[f"lineEdit_B{i}"].line_clicked.connect(self.lineedit_clicked)
            self[f"lineEdit_B{i}"].returnPressed.connect(self.lineedit_return)

        # connect the widget signals
        self.btn_open_palette.pressed.connect(lambda: self.load_palette())
        self.btn_save_palette.pressed.connect(self.save_palette)
        self.btn_save_extras.pressed.connect(self.save_extras)
        self.btn_open_widget.pressed.connect(lambda: self.view_file('widget'))
        self.btn_save_widget.pressed.connect(self.save_widget)
        self.btn_create.pressed.connect(self.create_variables)
        self.btn_compile.pressed.connect(self.compile_stylesheet)
        self.btn_preview.clicked.connect(lambda state:self.preview_stylesheet(state))
        self.btn_openUI.pressed.connect(self.open_uifile)
        self.btn_closeUI.pressed.connect(self.close_uifile)
        self.btn_close.pressed.connect(self.close_program)
        self.text_edit_extras.textChanged.connect(self.editor_extras_changed)
        self.text_edit_widget.textChanged.connect(self.editor_widget_changed)

        self.statusBar.addPermanentWidget(self.lbl_style)
        self.statusBar.addPermanentWidget(self.btn_close)
        self.btn_save_extras.setEnabled(False)
        self.btn_save_widget.setEnabled(False)
        if not self.style is None:
            self.load_palette(self.style)

    # this prevents menubar hovering from clearing the statusBar
    def event(self, event):
        if event.type() == QtCore.QEvent.StatusTip:
            return True
        return super().event(event)

    def preview_stylesheet(self, state):
        if state:
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
#                self.preview.hide()
            
    def load_palette(self, style=None):
        if style is None:
            dialog = QFileDialog(self)
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            caption = 'Open stylesheet palette file'
            _filter = 'Stylesheet palette (*.txt)'
            _dir = os.path.join(HERE, self.style) if not self.style is None else HERE
            fileName, _ =  dialog.getOpenFileName(None, caption, _dir, _filter, options=options)
            if not fileName: return
            if fileName.endswith('_palette.txt'):
                dirname = os.path.dirname(fileName)
                self.style = os.path.basename(dirname)
                self.lbl_style.setText(self.style)
                self.palette_file = fileName
                self.set_paths()
            else:
                self.statusBar.showMessage("Palette file must end with _palette.txt")
                return

        file = QFile(self.palette_file)
        if not file.open(QFile.ReadOnly):
            self.statusBar.showMessage(f"Could not open {self.palette_file}")
            return
        lines = []
        while not file.atEnd():
            line = file.readLine()
            lines.append(str(line.data(), encoding='utf-8'))
        if self.parse_lines(lines):
            self.view_file('extras')
            self.view_file('variables')
            self.view_file('stylesheet')
            self.statusBar.showMessage(f"Loaded palette {self.palette_file}")
        else:
            self.statusBar.showMessage("This is probably not a valid palette file")

    def open_uifile(self):
        if not self.preview is None:
            self.btn_openUI.setChecked(False)
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
        self.btn_preview.setChecked(False)

    def save_palette(self):
        if self.style is None: return
        if not os.path.exists(self.style):
            os.makedirs(self.style)
            with open(self.palette_file, "w") as fn:
                pass
            self.set_paths()
            with open(self.extras_file, "w") as fn:
                pass
            self.view_file('extras')
            self.statusBar.showMessage(f"Created new style folder {self.style}")
        file = QFile(self.palette_file)
        if file.open(QFile.WriteOnly | QFile.Text):
            lines = []
            for i in range(1, self.rows+1):
                color_B = self[f"lineEdit_B{i}"].text()
                var = self[f"label_var_{i}"].text()
                line = f"{color_B}${var}\n"
                lines.append(line)
            for line in lines:
                QTextStream(file) << line
            file.close()
            self.btn_save_palette.setStyleSheet('color: black;')
            self.statusBar.showMessage(f"Saved {self.palette_file}")
        else:
            self.statusBar.showMessage(f"Could not open {self.palette_file}")
 
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
        _filter = "Style Designer Files (*.txt)"
        _dir = HERE
        fileName, _ =  dialog.getSaveFileName(None, caption, _dir, _filter, options=options)
        if not fileName: return
        if fileName.endswith('_palette.txt'):
            dirname = os.path.dirname(fileName)
            self.style = os.path.basename(dirname)
            self.lbl_style.setText(self.style)
            self.palette_file = fileName
            self.set_paths()
        else:
            self.statusBar.showMessage("Palette file must end with _palette.txt")
            return
        self.save_palette()
        self.save_extras()

    def save_extras(self):
        text = self.text_edit_extras.toPlainText()
        file = QFile(self.extras_file)
        if file.open(QFile.WriteOnly):
            QTextStream(file) << text
            self.btn_save_extras.setStyleSheet("color: black;")
            self.statusBar.showMessage(f"Saved {self.extras_file}")
            return True
        else:
            self.statusBar.showMessage(f"Unable to open file {self.extras_file}")
            return False

    def save_widget(self):
        text = self.text_edit_widget.toPlainText()
        file = QFile(self.widget_file)
        if file.open(QFile.WriteOnly):
            QTextStream(file) << text
            self.btn_save_widget.setStyleSheet("color; black;")
            self.statusBar.showMessage(f"Saved {self.widget_file}")
            return True
        else:
            self.statusBar.showMessage(f"Unable to open file {self.widget_file}")
            return False

    def create_variables(self):
        if self.var_file is None: return
        if not os.path.exists(self.var_file):
            with open(self.var_file, "w") as fn:
                pass
        scss = self.palette_to_scss()
        if scss is None: return
        with open(self.extras_file, "r") as file:
            lines = [line.rstrip() for line in file]
        for line in lines:
            if line.startswith('#') or line == '': continue
            else:
                part = line.split("=")
                if len(part) != 2:
                    self.statusBar.showMessage(f"Syntax error - {line}")
                    return
                next_line = f"${part[0]}: {part[1]};"
                scss.append(next_line)

        data = '\n'.join([str(item) for item in scss])
        text = HEADER_SCSS + data
        # save created variables to file
        file = QFile(self.var_file)
        if file.open(QFile.WriteOnly):
            QTextStream(file) << text
            self.text_view_variables.setPlainText(text)
            self.lineEdit_variables.setText(self.var_file)
            self.statusBar.showMessage(f"Created {self.var_file}")
        else:
            self.statusBar.showMessage(f"Could not open {self.var_file}")

    def compile_stylesheet(self):
        if not self.qtsass_installed:
            self.statusBar.showMessage("Cannot compile - qtsass is not installed")
            return
        if self.var_file is None: return
        if not os.path.exists(self.var_file):
            self.statusBar.showMessage(f"Could not find {self.var_file}")
            return
        if self.qtsass_file is None: return
        if not os.path.exists(self.qtsass_file):
            self.statusBar.showMessage(f"Could not find {self.qtsass_file}")
            return
        try:
            qtsass.compile_filename(self.qtsass_file, self.qss_file, output_style='expanded')
            with open(self.qss_file, 'r') as file:
                data = file.read()
            data = HEADER_QSS + data
            with open(self.qss_file, 'w') as file:
                file.write(data)
            self.view_file('stylesheet')
            self.statusBar.showMessage(f"Stylesheet written to {self.qss_file}")
        except Exception as error:
            print(error)
            self.statusBar.showMessage(f"There was an error when compiling {self.qss_file}")

    def view_file(self, view):
        if view == 'extras':  fileName = self.extras_file
        elif view == 'widget':
            dialog = QFileDialog(self)
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            caption = 'Open widget file'
            _filter = "Widget definitions (*.scss)"
            _dir = self.widget_path
            fileName, _ =  dialog.getOpenFileName(None, caption, _dir, _filter, options=options)
            self.widget_file = fileName
        elif view == 'variables': fileName = self.var_file
        elif view == 'stylesheet': fileName = self.qss_file
        else: return
        if fileName is None: return
        if not os.path.exists(fileName):
            self.statusBar.showMessage(f"File {fileName} not found")
            return
        if self.load_file(view):
            self[f"lineEdit_{view}"].setText(fileName)
            if view == 'extras' or view == 'widget':
                self[f"btn_save_{view}"].setEnabled(False)
                self[f"btn_save_{view}"].setStyleSheet('color: black;')

    def view_help(self):
        self.statusBar.showMessage("Not implemented yet")

    def close_program(self):
        if not self.preview is None:
            self.preview.close()
        self.close()

    def parse_lines(self, lines):
        try:
            for i in range(self.rows):
                lines[i] = lines[i].strip()
                part = lines[i].split('$')
                self[f"color_B{i+1}"].setStyleSheet(f"background: {part[0]};")
                self[f"lineEdit_B{i+1}"].setText(part[0])
                self[f"label_var_{i+1}"].setText(part[1])
        except Exception as error:
            print(error)
            return False
        return True

    def lineedit_return(self):
        line = self.sender()
        label = self['color' + line.objectName().strip('lineEdit')]
        color = line.text()
        if color == "" or len(color) != 7 or not color.startswith('#'):
            self.statusBar.showMessage("Invalid color specification")
        else:
            self.set_color_box(label, color)
            self.btn_save_palette.setStyleSheet('color: red;')

    def lineedit_clicked(self):
        line = self.sender()
        self.current_label = self['color' + line.objectName().strip('lineEdit')]
        self.current_line = line
        self.choose_color()
        self.btn_save_palette.setStyleSheet('color: red;')

    def editor_extras_changed(self):
        self.btn_save_extras.setEnabled(True)     
        self.btn_save_extras.setStyleSheet('color: red;')

    def editor_widget_changed(self):
        self.btn_save_widget.setEnabled(True)     
        self.btn_save_widget.setStyleSheet('color: red;')

    def set_color_box(self, box, color):
        self.statusBar.showMessage(f"Set {box.objectName()} to {color}")
        box.setStyleSheet(f"background: {color};")
        
    def load_file(self, name):
        if name == 'extras':
            fname = self.extras_file
            editor = self.text_edit_extras
        elif name == 'widget':
            fname = self.widget_file
            editor = self.text_edit_widget
        elif name == 'variables':
            fname = self.var_file
            editor = self.text_view_variables
        elif name == 'stylesheet':
            fname = self.qss_file
            editor = self.text_view_stylesheet
        else: return
        file = QFile(fname)
        if file.open(QFile.ReadOnly):
            text = file.readAll()
            editor.setPlainText(str(text, encoding='utf8'))
        else:
            self.statusBar.showMessage(f"Could not open {fname}")
            return False
        return True

    def set_paths(self):
        if self.style is None: return
        self.extras_file = os.path.join(self.style, f"{self.style}_extras.txt")
        self.var_file = os.path.join(self.style, "_variables.scss")
        self.qtsass_file = os.path.join(self.style, f"{self.style}.scss")
        self.qss_file = os.path.join(self.style, f"{self.style}.qss")
        self.widget_path = os.path.join(self.style, 'widgets')
        
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
                var = self[f"label_var_{i}"].text()
                color = self[f"lineEdit_B{i}"].text()
                lines.append(f"${var}: {color};")
            lines.append('// Extras')
            return lines
        except AttributeError as error:
            print(error)
            self.statusBar.showMessage("Creation of variables file failed")
            return None

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
