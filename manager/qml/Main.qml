import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import Watchdog 1.0

Kirigami.ApplicationWindow {
    id: root

    title: "Watchdog Manager"
    width: 800
    height: 600
    minimumWidth: 400
    minimumHeight: 400

    // Topic editor dialog
    Kirigami.Dialog {
        id: topicEditor
        title: isNewTopic ? "Add Topic" : "Edit Topic"
        standardButtons: Kirigami.Dialog.Save | Kirigami.Dialog.Cancel
        preferredWidth: Kirigami.Units.gridUnit * 25

        property string originalName: ""
        property bool isNewTopic: false

        onAccepted: {
            if (isNewTopic) {
                backend.addTopicManual(
                    editName.text,
                    editDescription.text,
                    editQueries.text,
                    editUrls.text,
                    editInterval.value
                )
            } else {
                backend.updateTopic(
                    originalName,
                    editName.text,
                    editDescription.text,
                    editQueries.text,
                    editUrls.text,
                    editInterval.value
                )
            }
        }

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Label { text: "Name:" }
            Controls.TextField {
                id: editName
                Layout.fillWidth: true
            }

            Controls.Label { text: "Description:" }
            Controls.TextField {
                id: editDescription
                Layout.fillWidth: true
            }

            Controls.Label { text: "Search Queries (one per line):" }
            Controls.TextArea {
                id: editQueries
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 4
            }

            Controls.Label { text: "URLs to Check (one per line):" }
            Controls.TextArea {
                id: editUrls
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 3
            }

            RowLayout {
                Controls.Label { text: "Check every:" }
                Controls.SpinBox {
                    id: editInterval
                    from: 1
                    to: 168
                    value: 24
                }
                Controls.Label { text: "hours" }
            }
        }

        function openWith(name, description, queries, urls, interval) {
            isNewTopic = (name === "")
            originalName = name
            editName.text = name
            editDescription.text = description
            editQueries.text = queries
            editUrls.text = urls
            editInterval.value = interval
            open()
        }
    }

    ChatBackend {
        id: backend

        onMessageReceived: function(message, isUser) {
            chatModel.append({
                "text": message,
                "isUser": isUser
            })
            chatList.positionViewAtEnd()
        }

        onErrorOccurred: function(error) {
            errorBanner.text = error
            errorBanner.visible = true
        }
    }

    ListModel {
        id: chatModel
    }

    globalDrawer: Kirigami.GlobalDrawer {
        id: drawer
        title: "Topics"
        titleIcon: "view-list-details"
        modal: false
        collapsible: true
        collapsed: false
        width: 280

        header: ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing

            Controls.Label {
                text: "Monitored Topics"
                font.bold: true
                Layout.fillWidth: true
            }

            Controls.Button {
                text: backend.busy ? "Checking..." : "Check All Now"
                icon.name: backend.busy ? "view-refresh" : "media-playback-start"
                Layout.fillWidth: true
                enabled: !backend.busy
                onClicked: backend.checkAllTopics()

                Controls.BusyIndicator {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.rightMargin: Kirigami.Units.smallSpacing
                    width: Kirigami.Units.iconSizes.small
                    height: width
                    running: backend.busy
                    visible: backend.busy
                }
            }

            Controls.Button {
                text: "Add Topic"
                icon.name: "list-add"
                Layout.fillWidth: true
                enabled: !backend.busy
                onClicked: {
                    topicEditor.openWith("", "", "", "", 24)
                }
            }

            Controls.Button {
                text: "Refresh List"
                icon.name: "view-refresh"
                Layout.fillWidth: true
                onClicked: backend.refreshTopics()
            }
        }

        ListView {
            id: topicList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: backend.topicModel
            clip: true

            delegate: Kirigami.SwipeListItem {
                id: topicDelegate

                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing

                    Controls.Label {
                        text: model.name
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Controls.Label {
                        text: model.description
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        color: Kirigami.Theme.disabledTextColor
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Controls.Label {
                        text: "Every " + model.interval
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        color: Kirigami.Theme.positiveTextColor
                    }
                }

                onClicked: {
                    var topic = backend.getTopicDetails(model.name)
                    if (topic) {
                        topicEditor.openWith(
                            topic.name,
                            topic.description,
                            topic.search_queries.join("\n"),
                            topic.urls_to_check.join("\n"),
                            topic.check_interval_hours
                        )
                    }
                }

                actions: [
                    Kirigami.Action {
                        icon.name: "media-playback-start"
                        text: "Check"
                        enabled: !backend.busy
                        onTriggered: backend.checkSingleTopic(model.name)
                    },
                    Kirigami.Action {
                        icon.name: "document-edit"
                        text: "Edit"
                        onTriggered: {
                            var topic = backend.getTopicDetails(model.name)
                            if (topic) {
                                topicEditor.openWith(
                                    topic.name,
                                    topic.description,
                                    topic.search_queries.join("\n"),
                                    topic.urls_to_check.join("\n"),
                                    topic.check_interval_hours
                                )
                            }
                        }
                    },
                    Kirigami.Action {
                        icon.name: "edit-delete"
                        text: "Remove"
                        onTriggered: backend.removeTopic(model.name)
                    }
                ]
            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: topicList.count === 0
                text: "No topics yet"
                explanation: "Use the chat to add topics to monitor"
                icon.name: "view-list-details"
            }
        }
    }

    pageStack.initialPage: Kirigami.Page {
        title: "Chat"

        Kirigami.InlineMessage {
            id: errorBanner
            type: Kirigami.MessageType.Error
            visible: false
            showCloseButton: true
            Layout.fillWidth: true

            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
                margins: Kirigami.Units.smallSpacing
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing

            // Chat messages
            ListView {
                id: chatList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: chatModel
                spacing: Kirigami.Units.smallSpacing
                clip: true

                delegate: RowLayout {
                    width: chatList.width
                    layoutDirection: model.isUser ? Qt.RightToLeft : Qt.LeftToRight

                    Item { Layout.fillWidth: true; visible: !model.isUser }

                    Rectangle {
                        Layout.maximumWidth: chatList.width * 0.75
                        Layout.preferredWidth: messageText.implicitWidth + Kirigami.Units.largeSpacing * 2
                        Layout.preferredHeight: messageText.implicitHeight + Kirigami.Units.largeSpacing
                        radius: Kirigami.Units.smallSpacing
                        color: model.isUser ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                        border.color: Kirigami.Theme.disabledTextColor
                        border.width: model.isUser ? 0 : 1

                        Controls.Label {
                            id: messageText
                            anchors.fill: parent
                            anchors.margins: Kirigami.Units.smallSpacing
                            text: model.text
                            wrapMode: Text.WordWrap
                            color: model.isUser ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            textFormat: Text.MarkdownText
                        }
                    }

                    Item { Layout.fillWidth: true; visible: model.isUser }
                }

                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    visible: chatModel.count === 0
                    text: "Welcome to Watchdog Manager"
                    explanation: "Tell me what you'd like to monitor.\n\nExamples:\n• Watch for Fedora 44 release\n• Monitor AMD GPU driver updates\n• Track KDE Plasma 6.2 news"
                    icon.name: "help-hint"
                }
            }

            // Busy indicator
            Controls.BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                running: backend.busy
                visible: backend.busy
            }

            // Input area
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.TextField {
                    id: inputField
                    Layout.fillWidth: true
                    placeholderText: "Ask me to add topics to monitor..."
                    enabled: !backend.busy

                    onAccepted: {
                        if (text.trim() !== "") {
                            backend.sendMessage(text)
                            text = ""
                        }
                    }
                }

                Controls.Button {
                    icon.name: "document-send"
                    text: "Send"
                    enabled: !backend.busy && inputField.text.trim() !== ""
                    onClicked: {
                        backend.sendMessage(inputField.text)
                        inputField.text = ""
                    }
                }
            }
        }
    }
}
