# Ispirato a opengisch/qgis-linking-relation-editor (Copyright (C) 2022
# Damiano Lombardi, https://github.com/opengisch/qgis-linking-relation-editor,
# licenza GNU GPL v2) - reimplementazione su misura (non un porting 1:1:
# l'originale registra un intero QgsEditorWidgetFactory con supporto a
# relazioni n:m, editing della tabella di giunzione, selezione rettangolare
# sulla mappa e filtro con expression builder). Qui e' stato ridotto a un
# semplice ANALIZZATORE di sola lettura: mostra quali feature del layer
# figlio sono collegate/non collegate al padre selezionato, senza scrivere
# nulla sul layer - su richiesta esplicita dell'utente, che non vuole un
# editor delle chiavi esterne, solo uno strumento di analisi.
#
# Licenza: GNU GPL v2 (come il progetto originale che l'ha ispirato).

from qgis.core import (
    QgsFeature,
    QgsProject,
    QgsRelation,
    QgsVectorLayer,
    QgsVectorLayerUtils,
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QVBoxLayout,
)


class LinkManagerDialog(QDialog):
    """Dialogo di sola analisi: elenca le feature del layer figlio collegate
    e non collegate al padre selezionato per una data relazione 1:n. Non
    modifica nulla - niente chiave esterna viene letta/scritta oltre alla
    query iniziale di sola lettura."""

    def __init__(self, relation: QgsRelation, parent_feature: QgsFeature, parent=None):
        super().__init__(parent)
        self.relation = relation
        self.referencing_layer = relation.referencingLayer()

        display_value = QgsVectorLayerUtils.getFeatureDisplayString(relation.referencedLayer(), parent_feature)
        self.setWindowTitle(
            self.tr("Collegamenti di {0} per \"{1}\"").format(self.referencing_layer.name(), display_value)
        )
        self.resize(700, 450)

        request = relation.getRelatedFeaturesRequest(parent_feature)
        linked_features = list(self.referencing_layer.getFeatures(request))
        linked_ids = {f.id() for f in linked_features}
        unlinked_features = [f for f in self.referencing_layer.getFeatures() if f.id() not in linked_ids]

        layout = QVBoxLayout()

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(self.tr("Filtra le feature non collegate..."))
        self.filter_edit.textChanged.connect(self._filter_left)
        layout.addWidget(self.filter_edit)

        lists_layout = QHBoxLayout()

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(self.tr("Non collegate ({0})").format(len(unlinked_features))))
        self.list_left = QListWidget()
        self._populate_list(self.list_left, unlinked_features)
        left_col.addWidget(self.list_left)
        lists_layout.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel(self.tr("Collegate ({0})").format(len(linked_features))))
        self.list_right = QListWidget()
        self._populate_list(self.list_right, linked_features)
        right_col.addWidget(self.list_right)
        lists_layout.addLayout(right_col)

        layout.addLayout(lists_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _populate_list(self, list_widget, features):
        for feature in features:
            list_widget.addItem(QgsVectorLayerUtils.getFeatureDisplayString(self.referencing_layer, feature))

    def _filter_left(self, text):
        text_lower = text.lower()
        for row in range(self.list_left.count()):
            item = self.list_left.item(row)
            item.setHidden(text_lower not in item.text().lower())


def open_link_manager_for_active_layer(iface):
    """Punto di ingresso: opera sulla feature selezionata del layer attivo,
    trovando tra le relazioni gia' registrate da setup_relations_and_joins
    quelle in cui il layer attivo e' il lato 'padre' (referenced)."""
    layer = iface.activeLayer()
    if not isinstance(layer, QgsVectorLayer):
        QMessageBox.information(iface.mainWindow(), "Analizza collegamenti", "Seleziona prima un layer vettoriale.")
        return

    selected = layer.selectedFeatures()
    if len(selected) != 1:
        QMessageBox.information(
            iface.mainWindow(), "Analizza collegamenti",
            "Seleziona esattamente una feature sul layer attivo (quella per cui analizzare i collegamenti).")
        return
    parent_feature = selected[0]

    relations = QgsProject.instance().relationManager().referencedRelations(layer)
    if not relations:
        QMessageBox.information(
            iface.mainWindow(), "Analizza collegamenti",
            "Nessuna relazione trovata per questo layer (deve essere il lato 'padre' di una relazione).")
        return

    if len(relations) == 1:
        relation = relations[0]
    else:
        names = [r.name() for r in relations]
        name, ok = QInputDialog.getItem(
            iface.mainWindow(), "Analizza collegamenti", "Relazione:", names, 0, False)
        if not ok:
            return
        relation = relations[names.index(name)]

    dialog = LinkManagerDialog(relation, parent_feature, iface.mainWindow())
    # exec(), non exec_(): PyQt6 (QGIS 4) ha rimosso gli alias con underscore
    # finale - exec_() lancia AttributeError appena si apre il dialogo.
    dialog.exec()
