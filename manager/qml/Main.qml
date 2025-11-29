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
                    pageStack.push(editorPage, {
                        isNewTopic: true,
                        originalName: "",
                        topicName: "",
                        topicDescription: "",
                        topicQueries: "",
                        topicUrls: "",
                        topicInterval: 24
                    })
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
                        pageStack.push(editorPage, {
                            isNewTopic: false,
                            originalName: topic.name,
                            topicName: topic.name,
                            topicDescription: topic.description,
                            topicQueries: topic.search_queries.join("\n"),
                            topicUrls: topic.urls_to_check.join("\n"),
                            topicInterval: topic.check_interval_hours
                        })
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
                                pageStack.push(editorPage, {
                                    isNewTopic: false,
                                    originalName: topic.name,
                                    topicName: topic.name,
                                    topicDescription: topic.description,
                                    topicQueries: topic.search_queries.join("\n"),
                                    topicUrls: topic.urls_to_check.join("\n"),
                                    topicInterval: topic.check_interval_hours
                                })
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

    // Editor page component
    Component {
        id: editorPage

        Kirigami.ScrollablePage {
            id: editPage
            title: isNewTopic ? "Add Topic" : "Edit Topic"

            property bool isNewTopic: false
            property string originalName: ""
            property alias topicName: editName.text
            property alias topicDescription: editDescription.text
            property alias topicQueries: editQueries.text
            property alias topicUrls: editUrls.text
            property alias topicInterval: editInterval.value

            actions: [
                Kirigami.Action {
                    text: "Save"
                    icon.name: "document-save"
                    onTriggered: {
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
                        pageStack.pop()
                    }
                },
                Kirigami.Action {
                    text: "Cancel"
                    icon.name: "dialog-cancel"
                    onTriggered: pageStack.pop()
                }
            ]

            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

                Kirigami.FormLayout {
                    Layout.fillWidth: true

                    Controls.TextField {
                        id: editName
                        Kirigami.FormData.label: "Name:"
                        Layout.fillWidth: true
                        placeholderText: "e.g., Fedora 44 Release"
                    }

                    Controls.TextField {
                        id: editDescription
                        Kirigami.FormData.label: "Description:"
                        Layout.fillWidth: true
                        placeholderText: "What to monitor for"
                    }

                    Controls.TextArea {
                        id: editQueries
                        Kirigami.FormData.label: "Search Queries:"
                        Layout.fillWidth: true
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 5
                        placeholderText: "One search query per line\ne.g., Fedora 44 release date 2025"
                    }

                    Controls.TextArea {
                        id: editUrls
                        Kirigami.FormData.label: "URLs to Check:"
                        Layout.fillWidth: true
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 4
                        placeholderText: "One URL per line (optional)\ne.g., https://fedoramagazine.org/"
                    }

                    RowLayout {
                        Kirigami.FormData.label: "Check Interval:"

                        Controls.SpinBox {
                            id: editInterval
                            from: 1
                            to: 168
                            value: 24
                        }

                        Controls.Label {
                            text: "hours"
                        }
                    }
                }

                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    type: Kirigami.MessageType.Information
                    text: "Tip: Include years (2024, 2025) in search queries for better recency filtering"
                    visible: editQueries.text.length > 0 && !editQueries.text.includes("202")
                }
            }
        }
    }

    // Chat page
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
