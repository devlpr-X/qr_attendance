# app_core/urls.py
from django.urls import path
from app_core.views import export_views, documents
urlpatterns = [
    # Export
    path('admin/session/<int:session_id>/export/csv/', export_views.session_export_csv, name='session_export_csv'),
    path('admin/session/<int:session_id>/export/pdf/', export_views.session_export_pdf, name='session_export_pdf'),
    path('admin/schedule/export/daily/csv/', export_views.daily_schedule_export_csv, name='daily_schedule_export_csv'),
    path('admin/schedule/export/daily/pdf/', export_views.daily_schedule_export_pdf, name='daily_schedule_export_pdf'),

    # documents
    path('api/docs/', documents.api_docs_list, name='api_docs_list'),
    path('api/chat/', documents.api_chat, name='api_chat'),
    path('admin/documents/upload/', documents.document_upload, name='document_upload'),
    path('admin/documents/<int:doc_id>/delete/', documents.document_delete, name='document_delete'),
]
