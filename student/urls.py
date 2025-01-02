from django.urls import path
from .views import *

urlpatterns = [
    path("login/", student_login, name="student_login"),
    path("signup/", student_signup, name="student_signup"),
    path("profile/", student_profile, name="student_profile"),  
    path("", get_students, name="get_students"),
    path("tests", get_tests_for_student, name="get_open_tests"), 
    path("mcq-tests", get_mcq_tests_for_student, name='get_mcq_tests_for_student'),
    path("coding-reports/", get_coding_reports_for_student, name="get_coding_reports_for_student"),
    path("mcq-reports/", get_mcq_reports_for_student, name='get_mcq_reports_for_student'),
    path("check-publish-status/<str:identifier>/", check_publish_status, name="check_publish_status"),
]
