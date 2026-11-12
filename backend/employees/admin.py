from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Employee, Attendance, BreakRecord, OfficeLocation, LeaveRequest


class EmployeeInline(admin.StackedInline):
    model = Employee
    can_delete = False
    fields = ['employee_id', 'department', 'phone', 'total_leave_days', 'used_leave_days', 'is_active']


class CustomUserAdmin(UserAdmin):
    inlines = [EmployeeInline]
    list_display = ['username', 'get_full_name', 'email', 'get_emp_id', 'get_dept', 'is_active']

    def get_emp_id(self, obj):
        try: return obj.employee.employee_id
        except: return '-'
    get_emp_id.short_description = 'EMP ID'

    def get_dept(self, obj):
        try: return obj.employee.department
        except: return '-'
    get_dept.short_description = 'Department'


class BreakInline(admin.TabularInline):
    model = BreakRecord
    extra = 0
    readonly_fields = ['duration_minutes', 'break_type', 'is_violation']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'login_time', 'logout_time',
                    'total_work_hours', 'total_break_hours', 'status',
                    'break_violation', 'face_verified']
    list_filter  = ['status', 'date', 'break_violation', 'face_verified']
    search_fields = ['employee__user__first_name', 'employee__employee_id']
    inlines = [BreakInline]
    date_hierarchy = 'date'


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'get_name', 'department', 'remaining_leave_days', 'is_active']
    list_filter  = ['department', 'is_active']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name']

    def get_name(self, obj): return obj.user.get_full_name()
    get_name.short_description = 'Name'


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'latitude', 'longitude', 'radius_meters', 'is_active', 'updated_at']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'from_date', 'to_date', 'total_days', 'status', 'applied_on']
    list_filter  = ['status', 'leave_type']
    search_fields = ['employee__user__first_name', 'employee__employee_id']
    actions = ['approve_leaves', 'reject_leaves']

    def approve_leaves(self, request, qs):
        for l in qs.filter(status='pending'):
            l.status = 'approved'
            l.reviewed_by = request.user
            from django.utils import timezone
            l.reviewed_on = timezone.now()
            l.save()
            l.employee.used_leave_days += l.total_days
            l.employee.save()
        self.message_user(request, "Leaves approved.")
    approve_leaves.short_description = "Approve selected leaves"

    def reject_leaves(self, request, qs):
        qs.filter(status='pending').update(status='rejected')
        self.message_user(request, "Leaves rejected.")
    reject_leaves.short_description = "Reject selected leaves"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
