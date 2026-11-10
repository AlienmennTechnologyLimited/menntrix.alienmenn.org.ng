from django.urls import path
from . import views

urlpatterns = [
    # Folders
    path("messages/", views.inbox, {"folder": "inbox"}, name="message_inbox"),
    path("messages/inbox/", views.inbox, {"folder": "inbox"}, name="message_inbox_folder"),
    path("messages/sent/", views.inbox, {"folder": "sent"}, name="message_sent"),
    path("messages/drafts/", views.inbox, {"folder": "drafts"}, name="message_drafts"),
    path("messages/trash/", views.inbox, {"folder": "trash"}, name="message_trash_folder"),
    path("messages/starred/", views.inbox, {"folder": "starred"}, name="message_starred"),

    # Compose / view
    path("messages/compose/", views.message_compose, name="message_compose"),
    path("messages/view/<int:message_id>/", views.message_view, name="message_view"),

    # Draft actions
    path("messages/draft/<int:message_id>/send/", views.draft_send, name="draft_send"),
    path("messages/draft/<int:message_id>/delete/", views.draft_delete, name="draft_delete"),

    # Star / trash / restore
    path("messages/star/<int:message_id>/", views.message_star, name="message_star"),
    path("messages/trash/<int:message_id>/", views.message_trash, name="message_trash"),
    path("messages/restore/<int:message_id>/", views.message_restore, name="message_restore"),
    path("messages/delete/<int:message_id>/", views.message_delete_forever, name="message_delete_forever"),
    path("messages/trash/empty/", views.trash_empty, name="trash_empty"),
        # Group management
    path("messages/groups/", views.group_list, name="group_list"),
    path("messages/groups/create/", views.group_create, name="group_create"),
    path("messages/groups/<int:group_id>/", views.group_detail, name="group_detail"),
    path("messages/groups/<int:group_id>/rename/", views.group_rename, name="group_rename"),
    path("messages/groups/<int:group_id>/delete/", views.group_delete, name="group_delete"),
    path("messages/groups/<int:group_id>/leave/", views.group_leave, name="group_leave"),
    path("messages/groups/<int:group_id>/add/", views.group_add_member, name="group_add_member"),
    path("messages/groups/<int:group_id>/remove/<int:user_id>/", views.group_remove_member, name="group_remove_member"),
]