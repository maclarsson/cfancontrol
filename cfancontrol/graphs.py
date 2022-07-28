from typing import List

import numpy as np
import math
import pyqtgraph as pg
from pyqtgraph import PlotWidget, PlotItem, GraphItem

from PyQt5 import QtCore, QtGui, QtWidgets


class FanCurveWidget(PlotWidget):

    def __init__(self, parent: QtWidgets.QFrame, **keywords):
        super().__init__(parent)
        self.setGeometry(QtCore.QRect(10, 45, 360, 300))
        self.setObjectName("graphicsView_fancurve")

        self._graph: EditableGraph = None
        self._line_temp: pg.InfiniteLine = None
        self._line_fan: pg.InfiniteLine = None
        self._copy_data: List = []

        keywords_default = {
            'menuEnabled': False,
            'aspectLocked': False,
            'hideButtons': True,
            'labels': {
                'bottom': [],
                'left': []
            },
            'showGrid': {
                'x': True,
                'y': True,
                'alpha': 0.5
            },
            'tickSpacing': {
                'bottom': False,
                'left': False
            },
            'background': None
        }

        data = dict(keywords_default, **keywords)

        self.setMenuEnabled(data['menuEnabled'])
        self.setLabels(**data['labels'])
        self.setAspectLocked(data['aspectLocked'])
        self.showGrid(**data['showGrid'])
        self.setBackground(data['background'])

        if data['tickSpacing']['bottom'] is not False:
            self.getAxis('bottom').setTickSpacing(data['tickSpacing']['bottom'][0], data['tickSpacing']['bottom'][1])

        if data['tickSpacing']['left'] is not False:
            self.getAxis('left').setTickSpacing(data['tickSpacing']['left'][0], data['tickSpacing']['left'][1])

        if 'hideButtons' in data:
            self.hideButtons()

        if 'limits' in data:
            if len(data['limits']) == 2:
                self.setLimits(
                    xMin=data['limits'][0],
                    yMin=data['limits'][0],
                    xMax=data['limits'][1] + data['limits'][0],
                    yMax=data['limits'][1] + data['limits'][0],
                    minXRange=data['limits'][1],
                    maxXRange=data['limits'][1],
                    minYRange=data['limits'][1],
                    maxYRange=data['limits'][1]
                )

    def contextMenuEvent(self, event):
        if self._graph.pointCount() > 2:
            menu = QtWidgets.QMenu()
            copy_action = menu.addAction('Copy')
            paste_action = menu.addAction('Paste')
            paste_action.setEnabled(False)
            if self._copy_data:
                paste_action.setEnabled(True)
            res = menu.exec_(event.globalPos())
            if res == copy_action:
                self._copy_data = self.get_graph_data()
            elif res == paste_action:
                self._graph.updateData(self._copy_data)

    def reset_graph(self):
        if self._graph is not None:
            self.removeItem(self._graph)
        if self._line_temp is not None:
            self.removeItem(self._line_temp)
        if self._line_fan is not None:
            self.removeItem(self._line_fan)

    def set_graph(self, graph_data: list, draw_lines: bool, accent_color: QtGui.QColor, label_color: QtGui.QColor, line_color: QtGui.QColor):
        self.enableAutoRange()
        self.reset_graph()
        if draw_lines:
            self.draw_lines(label_color, line_color)
        self._graph = EditableGraph(self, data=graph_data, line_color=accent_color, label_color=label_color, static_pos=[100, 100])
        self.disableAutoRange()

    def get_graph_data(self) -> list:
        data = list()
        if self._graph is not None:
            data = self._graph.data['pos'].tolist()
        return data

    def draw_lines(self, label_color: QtGui.QColor, line_color: QtGui.QColor):
        pen = pg.mkPen(line_color, width=1.0, style=QtCore.Qt.DashLine)

        self._line_temp = pg.InfiniteLine(pos=0, pen=pen, name='currTemp', angle=90)
        self._line_fan = pg.InfiniteLine(pos=0, pen=pen, name='currFan', angle=0)

        pg.InfLineLabel(self._line_temp, text="Temp {value} °C", rotateAxis=(-1, 0), anchors=[(1.5, 0), (1.5, 1.0)], color=label_color)
        pg.InfLineLabel(self._line_fan, text="Fan {value} %", position=0.12, color=label_color, anchor=(1, 1))

        self.addItem(self._line_temp)
        self.addItem(self._line_fan)

    def update_line(self, name: str, value):
        if name == 'currTemp':
            if self._line_temp is not None:
                self._line_temp.setValue(value)
        elif name == 'currFan':
            if self._line_fan is not None:
                self._line_fan.setValue(value)
        # self._graph.updateGraph()

    def add_point(self):
        self._graph.addPoint()

    def remove_point(self):
        self._graph.removePoint()


class EditableGraph(GraphItem):
    MIN_POINT_DISTANCE = 16

    def __init__(self, parent: PlotWidget, data: list, line_color: QtGui.QColor, label_color: QtGui.QColor, static_pos=None):
        super().__init__()

        self.plotWidget = parent

        # adds _name attribute similar tto those in plotItem.items
        self._name = 'graph'
        self.staticPos = static_pos

        self._line_color: QtGui.QColor = line_color

        self.dragPoint = None
        self.dragOffset = None

        self.setData(pos=np.stack(data))

        # adds pg.GraphItem to the parent PlotItems
        text_box = pg.TextItem(color=label_color)
        font = QtGui.QFont()
        font.setPointSize(11)
        font.setBold(True)
        text_box.setFont(font)
        parent.addItem(text_box)
        parent.addItem(self)

    def setData(self, **kwds):
        self.data = kwds

        if 'pos' in self.data:
            pos = self.data['pos'].tolist()
            if len(pos) == 1:
                fixed = pos[0]
                pos.insert(0, [0, fixed[1]])
                self.setData(pos=np.stack(pos))
                return

            if len(pos) > 2:
                if pos[0] != [0, 0]:
                    pos.insert(0, [0, 0])
                    self.setData(pos=np.stack(pos))
                    return

                if (self.staticPos is not None) and (pos[len(pos) - 1] != self.staticPos):
                    pos.append(self.staticPos)
                    self.setData(pos=np.stack(pos))
                    return

            npts = self.data['pos'].shape[0]
            self.data['adj'] = np.column_stack((np.arange(0, npts-1), np.arange(1, npts)))
            self.data['data'] = np.empty(npts, dtype=[('index', int)])
            self.data['data']['index'] = np.arange(npts)

            # force array values to be integers
            self.data['pos'] = self.data['pos'].astype(int)

            # set the design of the plot
            # self.data['pen'] = pg.mkPen((203, 0, 0), width=3.0, style=QtCore.Qt.SolidLine)
            self.data['pen'] = pg.mkPen(self._line_color, width=3.0, style=QtCore.Qt.SolidLine)
            self.data['symbol'] = 'o'
            # self.data['symbolPen'] = pg.mkPen((203, 0, 0), width=2.0)
            self.data['symbolPen'] = pg.mkPen(self._line_color, width=2.0)
            self.data['symbolBrush'] = (227, 227, 227)

            self.updateGraph()

    def updateData(self, data: list):
        self.setData(pos=np.stack(data))

    def updateGraph(self):
        super().setData(**self.data)

    def addPoint(self):
        if len(self.data['pos']) == 10:
            # don't add more than 10 points
            return
        # work out where the largest gap occurs and insert the new point in the middle
        inspos = -1
        length = 0
        output = [0, 0]

        for i in range(0, len(self.data['pos']) - 1):
            h = self.getPointDistance(i, i + 1)

            if (h > length):
                inspos = i
                length = h
                output = [
                    int(self.data['pos'][i][0] + ( ( self.data['pos'][ i +1][0] - self.data['pos'][i][0] ) / 2 )),
                    int(self.data['pos'][i][1] + ( ( self.data['pos'][ i +1][1] - self.data['pos'][i][1] ) / 2 ))
                ]

        if length < self.MIN_POINT_DISTANCE:
            return

        flat = self.data['pos'].tolist()
        flat.insert(inspos + 1, output)

        self.setData(pos=np.stack(flat))

    def removePoint(self):
        if len(self.data['pos']) == 3:
            # don't remove the last 3 points
            return

        index = 1
        min_len = self.getPointDistance(0, len(self.data['pos']) - 1)

        for i in range(1, len(self.data['pos']) - 1):
            closest = self.getPointDistance(i - 1, i)

            # LOG.info(f"closest={int(closest)} min_len={int(min_len)} index={index} i={i}")

            if closest < min_len:
                index = i
                min_len = closest

        flat = self.data['pos'].tolist()
        del flat[index]
        self.setData(pos=np.stack(flat))

    def pointCount(self) -> int:
        return len(self.data['pos'])

    def getPointDistance(self, p1, p2):
        return math.sqrt(
            math.pow(self.data['pos'][p2][0] - self.data['pos'][p1][0], 2) +
            math.pow(self.data['pos'][p2][1] - self.data['pos'][p1][1], 2)
        )

    def getCoordWidget(self):
        coordWidget = None
        for item in self.plotWidget.plotItem.items:
            if isinstance(item, pg.graphicsItems.TextItem.TextItem):
                coordWidget = item
                break
        return coordWidget

    def setCoordText(self, text=""):
        coordWidget = self.getCoordWidget()
        if coordWidget is None:
            return
        coordWidget.setText(text)

    def setCoordValues(self, x, y):
        coordWidget = self.getCoordWidget()
        if (coordWidget is None):
            return
        coordWidget.setPos(x, y)

    def mouseDragEvent(self, event):

        self.setCoordText()

        if event.button() != QtCore.Qt.LeftButton:
            event.ignore()
            return
        if event.isStart():
            pos = event.buttonDownPos()
            points = self.scatter.pointsAt(pos)

            if len(points) == 0:
                event.ignore()
                return
            self.dragPoint = points[0]
            index = points[0].data()[0]

            self.dragOffsetX = self.data['pos'][index][0] - pos[0]
            self.dragOffsetY = self.data['pos'][index][1] - pos[1]
        elif event.isFinish():
            self.dragPoint = None
            return
        else:
            if self.dragPoint is None:
                event.ignore()
                return

        index = self.dragPoint.data()[0]

        if (index == 0) or (index == len(self.data['pos']) - 1):
            # disallow moving the first or last points
            event.ignore()
            return

        p = self.data['pos'][index]

        p[0] = event.pos()[0] + self.dragOffsetX
        p[1] = event.pos()[1] + self.dragOffsetY

        minX = self.data['pos'][index - 1][0]
        minY = self.data['pos'][index - 1][1]
        maxX = self.data['pos'][index + 1][0]
        maxY = self.data['pos'][index + 1][1]

        if p[0] < minX: p[0] = minX
        if p[0] > maxX: p[0] = maxX
        if p[1] < minY: p[1] = minY
        if p[1] > maxY: p[1] = maxY

        ps = self.plotWidget.getViewBox().viewPixelSize()

        self.setCoordValues(p[0] - (ps[0] * 24), p[1] + (ps[1] * 24))
        self.setCoordText(f"({p[0]}°C, {p[1]}%)")

        self.updateGraph()
        event.accept()
