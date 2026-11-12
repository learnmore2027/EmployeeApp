from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

# Wrap all views with csrf_exempt for cross-origin frontend
def ex(view): return csrf_exempt(view)

urlpatterns = [
    # Auth
    path('auth/login/',         ex(views.login_view),        name='login'),
    path('auth/logout/',        ex(views.logout_view),       name='logout'),
    path('auth/check/',         ex(views.check_auth),        name='check_auth'),
    # Dashboard
    path('dashboard/',          ex(views.dashboard_view),    name='dashboard'),
    # Break
    path('break/start/',        ex(views.break_start),       name='break_start'),
    path('break/end/',          ex(views.break_end),         name='break_end'),
    # Geo-fence
    path('geo/ping/',           ex(views.geo_ping),          name='geo_ping'),
    path('geo/office/',         ex(views.office_location),   name='office_location'),
    # Attendance
    path('attendance/history/', ex(views.attendance_history),name='attendance_history'),
    path('attendance/live/',    ex(views.live_attendance),   name='live_attendance'),
    # Violations
    path('violations/',         ex(views.break_violations),  name='break_violations'),
    # Leave
    path('leave/',              ex(views.leave_request),     name='leave_request'),
    path('leave/admin/',        ex(views.leave_list_admin),  name='leave_list_admin'),
    path('leave/<int:leave_id>/action/', ex(views.leave_action), name='leave_action'),
    # Face
    path('face/register/',      ex(views.register_face),     name='register_face'),
    path('face/verify-credentials/', ex(views.verify_credentials), name='verify_credentials'),
]
