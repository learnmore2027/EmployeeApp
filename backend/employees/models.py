from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import math


def haversine_distance(lat1, lon1, lat2, lon2):
    """Distance in meters between two GPS points"""
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


class OfficeLocation(models.Model):
    name = models.CharField(max_length=100, default='Main Office')
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_meters = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_within_radius(self, lat, lon):
        dist = haversine_distance(self.latitude, self.longitude, lat, lon)
        return dist <= self.radius_meters, round(dist)

    def __str__(self):
        return f"{self.name} ({self.latitude:.4f}, {self.longitude:.4f}) — {self.radius_meters}m"

    class Meta:
        verbose_name = 'Office Location'


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    profile_photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)
    face_descriptor = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    # Leave balance
    total_leave_days = models.IntegerField(default=12)
    used_leave_days = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def remaining_leave_days(self):
        return self.total_leave_days - self.used_leave_days

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

    class Meta:
        ordering = ['employee_id']


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On Leave'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    login_time = models.DateTimeField(null=True, blank=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    total_work_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_break_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='absent')
    face_verified = models.BooleanField(default=False)
    # Geo
    login_latitude = models.FloatField(null=True, blank=True)
    login_longitude = models.FloatField(null=True, blank=True)
    login_distance_m = models.IntegerField(null=True, blank=True)
    # Violations
    break_violation = models.BooleanField(default=False)
    break_violation_minutes = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    REQUIRED_HOURS = 8.0
    MAX_BREAK_HOURS = 1.0

    def calculate_work_hours(self):
        if self.login_time and self.logout_time:
            total = (self.logout_time - self.login_time).total_seconds() / 3600
            return round(max(0, total - float(self.total_break_hours)), 2)
        return 0

    def update_status(self):
        hours = self.calculate_work_hours()
        if hours >= self.REQUIRED_HOURS:
            self.status = 'present'
        elif hours >= self.REQUIRED_HOURS / 2:
            self.status = 'half_day'
        else:
            self.status = 'absent'
        self.total_work_hours = hours

    def __str__(self):
        return f"{self.employee} — {self.date}"

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date']


class BreakRecord(models.Model):
    BREAK_TYPE = [
        ('manual', 'Manual'),
        ('geo', 'Geo-fence Auto'),
    ]
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='breaks')
    break_start = models.DateTimeField()
    break_end = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    break_type = models.CharField(max_length=10, choices=BREAK_TYPE, default='manual')
    is_violation = models.BooleanField(default=False)

    def calculate_duration(self):
        if self.break_start and self.break_end:
            self.duration_minutes = round(
                (self.break_end - self.break_start).total_seconds() / 60, 2)
        return self.duration_minutes

    def __str__(self):
        return f"{self.break_type} break @ {self.break_start.strftime('%H:%M')} ({self.duration_minutes}m)"

    class Meta:
        ordering = ['break_start']


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('casual',      'Casual Leave (CL)'),
        ('sick',        'Sick Leave (SL)'),
        ('earned',      'Earned Leave (EL)'),
        ('maternity',   'Maternity Leave'),
        ('paternity',   'Paternity Leave'),
        ('marriage',    'Marriage Leave'),
        ('bereavement', 'Bereavement Leave'),
        ('comp_off',    'Compensatory Off'),
        ('wfh',         'Work From Home'),
        ('half_day',    'Half Day Leave'),
        ('unpaid',      'Unpaid Leave (LWP)'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    from_date = models.DateField()
    to_date = models.DateField()
    total_days = models.IntegerField(default=1)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_on = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_leaves')
    reviewed_on = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.employee} — {self.leave_type} ({self.from_date} to {self.to_date})"

    class Meta:
        ordering = ['-applied_on']
