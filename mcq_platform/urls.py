"""mcq_platform URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from .views import *
from .mcqlibrary import save_selected_questions


urlpatterns = [
    path("admin/", admin.site.urls),
    path("save-data/", save_data,name = "saveData"),
    path("start-contest/", start_contest, name="start_contest"),
    path("questions/", get_questions, name="get_questions"),
    path("save-questions/", save_question, name="save_question"),
    path("api/assessment/questions/update", update_question, name="update_question"),
    path("finish-contest/", finish_contest,name="finish_contest"),
    path("bulk-upload/",bulk_upload_questions,name="bulkUpload"),
    path("publish/",publish_mcq,name="publish"),
    path("submit_assessment/",submit_mcq_assessment,name="submit_assessment"),
    path("get_mcqquestions/<str:contestId>/",get_mcqquestions,name="get_mcqquestions"),
    path("bulk-upload/",bulk_upload_questions,name="bulkUpload"),
    path("api/save-selected-questions/", save_selected_questions, name="save_selected_question"),
    path("student-report/<str:contestId>/<str:regno>/", get_student_report, name="student_report"),
    path("publish-result/<str:contestId>/", publish_result, name="publish_result")
]
