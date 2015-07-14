import json, difflib
import os.path

from PySide import QtGui, QtCore

from contextual_node_list import ContextualNodeList, ContextualNewNodeWidget
from graph_view.graph_view_widget import GraphViewWidget
from kgraph_view import KGraphView
from kraken.ui.undoredo.undo_redo_manager import UndoRedoManager
import graph_commands

from kraken.core.objects.rig import Rig
from kraken import plugins


def GetHomePath():
    homeDir = os.path.expanduser("~")
    return homeDir


class KGraphViewWidget(GraphViewWidget):

    rigNameChanged = QtCore.Signal()

    def __init__(self, parent=None):

        # constructors of base classes
        super(KGraphViewWidget, self).__init__(parent)


        graphView = KGraphView(parent=self)
        graphView.nodeAdded.connect(self.__onNodeAdded)
        graphView.nodeRemoved.connect(self.__onNodeRemoved)
        graphView.beginConnectionManipulation.connect(self.__onBeginConnectionManipulation)
        graphView.endConnectionManipulation.connect(self.__onEndConnectionManipulationSignal)
        graphView.connectionAdded.connect(self.__onConnectionAdded)
        graphView.connectionRemoved.connect(self.__onConnectionRemoved)

        graphView.beginNodeSelection.connect(self.__onBeginNodeSelection)
        graphView.endNodeSelection.connect(self.__onEndNodeSelection)
        graphView.nodeSelected.connect(self.__onNodeSelected)
        graphView.nodeDeselected.connect(self.__onNodeDeselected)
        graphView.selectionChanged.connect(self.__onSelectionChanged)
        graphView.endSelectionMoved.connect(self.__onSelectionMoved)

        graphView.beginDeleteSelection.connect(self.__onBeginDeleteSelection)
        graphView.endDeleteSelection.connect(self.__onEndDeleteSelection)
        
        self.setGraphView(graphView)

        #########################
        ## Setup hotkeys for the following actions.

        undoShortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_Z), self)
        undoShortcut.activated.connect(self.undo)

        redoShortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_Y), self)
        redoShortcut.activated.connect(self.redo)

        openContextualNodeListShortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_QuoteLeft), self)
        openContextualNodeListShortcut.activated.connect(self.openContextualNodeList)

        self.newRigPreset()

        self.__contextualNodeList = None

    def getContextualNodeList(self):
        return self.__contextualNodeList

    def editRigName(self):
        dialog = QtGui.QInputDialog(self)
        dialog.setObjectName('RigNameDialog')
        text, ok = dialog.getText(self, 'Edit Rig Name', 'New Rig Name', text=self.guideRig.getName())

        if ok is True:
            self.setRigName(text)


    def setRigName(self, text):
        self.guideRig.setName(text)
        self.rigNameChanged.emit()


    def newRigPreset(self):
        # TODO: clean the rig from the scene if it has been built.
        self.guideRig = Rig()
        self.getGraphView().displayGraph(self.guideRig)
        self.setRigName('MyRig')


    def saveRigPreset(self):
        lastSceneFilePath = os.path.join(GetHomePath(), self.guideRig.getName() )
        (filePath, filter) = QtGui.QFileDialog.getSaveFileName(self, 'Save Rig Preset', lastSceneFilePath, 'Kraken Rig (*.krg)')
        if len(filePath) > 0:
            self.synchGuideRig()
            self.guideRig.writeRigDefinitionFile(filePath)


    def loadRigPreset(self):
        lastSceneFilePath = GetHomePath()
        (filePath, filter) = QtGui.QFileDialog.getOpenFileName(self, 'Load Rig Preset', lastSceneFilePath, 'Kraken Rig (*.krg)')
        if len(filePath) > 0:
            self.guideRig = Rig()
            self.guideRig.loadRigDefinitionFile(filePath)
            self.graphView.displayGraph( self.guideRig )
            # self.nameWidget.setText( self.guideRig.getName() )


    def buildGuideRig(self):

        self.window().statusBar().showMessage('Building Guide')

        builder = plugins.getBuilder()

        if self.guideRig.getName().endswith('_guide') is False:
            self.guideRig.setName(self.guideRig.getName() + '_guide')

        builder.build(self.guideRig)
        self.window().statusBar().showMessage('Ready')


    def synchGuideRig(self):
        synchronizer = plugins.getSynchronizer()
        synchronizer.setTarget(self.guideRig)
        synchronizer.sync()


    def buildRig(self):

        self.window().statusBar().showMessage('Building Rig')

        self.synchGuideRig()

        rigBuildData = self.guideRig.getRigBuildData()
        rig = Rig()
        rig.loadRigDefinition(rigBuildData)

        rig.setName(rig.getName().replace('_guide', ''))

        builder = plugins.getBuilder()
        builder.build(rig)

        self.window().statusBar().showMessage('Ready')

    # =========
    # Shortcuts
    # =========
    def copy(self):
        graph = self.graphView.getGraph()
        pos = graph.getSelectedNodesCentroid()
        self.graphView.__class__._clipboardData = graph.copySettings(pos)


    def paste(self):
        graph = self.graphView.getGraph()
        clipboardData = self.graphView.__class__._clipboardData

        pos = clipboardData['copyPos'] + QtCore.QPoint(20, 20)
        graph.pasteSettings(clipboardData, pos, mirrored=False, createConnectionsToExistingNodes=True)


    def pasteUnconnected(self):
        graph = self.graphView.getGraph()
        clipboardData = self.graphView.__class__._clipboardData

        pos = clipboardData['copyPos'] + QtCore.QPoint(20, 20)
        graph.pasteSettings(clipboardData, pos, mirrored=False, createConnectionsToExistingNodes=False)


    def pasteMirrored(self):
        graph = self.graphView.getGraph()
        clipboardData = self.graphView.__class__._clipboardData

        pos = clipboardData['copyPos'] + QtCore.QPoint(20, 20)
        graph.pasteSettings(clipboardData, pos, mirrored=True, createConnectionsToExistingNodes=False)


    def pasteMirroredConnected(self):
        graph = self.graphView.getGraph()
        clipboardData = self.graphView.__class__._clipboardData

        pos = clipboardData['copyPos'] + QtCore.QPoint(20, 20)
        graph.pasteSettings(clipboardData, pos, mirrored=True, createConnectionsToExistingNodes=True)


    def undo(self):
        UndoRedoManager.getInstance().undo()

    def redo(self):
        UndoRedoManager.getInstance().redo()


    def openContextualNodeList(self):
        pos = self.mapFromGlobal(QtGui.QCursor.pos());
        if not self.__contextualNodeList:
            self.__contextualNodeList = ContextualNodeList(self)
        else:
            # Ensures that the node list is reset to list all components
            self.__contextualNodeList.showClosestNames()

        scenepos = self.graphView.mapToScene(pos)
        self.__contextualNodeList.showAtPos(pos, scenepos, self.graphView)

    # ===============
    # Signal Handlers
    # ===============

    def __onNodeAdded(self, node):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.AddNodeCommand(self.graphView, self.guideRig, node)
            UndoRedoManager.getInstance().addCommand(command)


    def __onNodeRemoved(self, node):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.RemoveNodeCommand(self.graphView, self.guideRig, node)
            UndoRedoManager.getInstance().addCommand(command)


    def __onBeginConnectionManipulation(self):
        UndoRedoManager.getInstance().openBracket('Connect Ports')


    def __onEndConnectionManipulationSignal(self):
        UndoRedoManager.getInstance().closeBracket()


    def __onConnectionAdded(self, connection):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.ConnectionAddedCommand(self.graphView, self.guideRig, connection)
            UndoRedoManager.getInstance().addCommand(command)


    def __onConnectionRemoved(self, connection):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.ConnectionRemovedCommand(self.graphView, self.guideRig, connection)
            UndoRedoManager.getInstance().addCommand(command)


    def __onBeginNodeSelection(self):
        UndoRedoManager.getInstance().openBracket('Select Nodes')


    def __onEndNodeSelection(self):
        UndoRedoManager.getInstance().closeBracket()


    def __onNodeSelected(self, node):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.SelectionChangeCommand(self.graphView, [node], [])
            UndoRedoManager.getInstance().addCommand(command)


    def __onNodeDeselected(self, node):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.SelectionChangeCommand(self.graphView, [], [node])
            UndoRedoManager.getInstance().addCommand(command)


    def __onSelectionChanged(self, selectedNodes, deselectedNodes):
        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.SelectionChangeCommand(self.graphView, selectedNodes, deselectedNodes)
            UndoRedoManager.getInstance().addCommand(command)


    def __onSelectionMoved(self, nodes, delta):
        for node in nodes:
            node.pushGraphPosToComponent()

        if not UndoRedoManager.getInstance().isUndoingOrRedoing():
            command = graph_commands.NodesMoveCommand(self.graphView, nodes, delta)
            UndoRedoManager.getInstance().addCommand(command)


    def __onBeginDeleteSelection(self):
        UndoRedoManager.getInstance().openBracket('Delete Nodes')


    def __onEndDeleteSelection(self):
        UndoRedoManager.getInstance().closeBracket()