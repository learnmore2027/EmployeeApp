from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
import json, math
from decimal import Decimal
from datetime import timedelta

from .models import Employee, Attendance, BreakRecord, OfficeLocation, LeaveRequest


# ── helpers ──────────────────────────────────────────────────────────────────

def _total_break_minutes(attendance):
    breaks = BreakRecord.objects.filter(attendance=attendance, break_end__isnull=False)
    return sum(float(b.duration_minutes) for b in breaks)


def _close_open_breaks(attendance, now):
    for b in BreakRecord.objects.filter(attendance=attendance, break_end__isnull=True):
        b.break_end = now
        b.calculate_duration()
        b.save()


# ── AUTH ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
@csrf_exempt
def check_auth(request):
    if request.user.is_authenticated:
        try:
            emp = request.user.employee
            return Response({
                'authenticated': True,
                'is_admin': request.user.is_staff,
                'user': {
                    'name': request.user.get_full_name() or request.user.username,
                    'username': request.user.username,
                    'employee_id': emp.employee_id,
                    'department': emp.department,
                }
            })
        except Employee.DoesNotExist:
            pass
    return Response({'authenticated': False})


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login_view(request):
    data = request.data
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    lat = data.get('latitude')
    lon = data.get('longitude')

    if not username or not password:
        return Response({'error': 'Username aur password zaroori hain.'}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({'error': 'Username ya password galat hai.'}, status=401)
    if not user.is_active:
        return Response({'error': 'Account disable hai.'}, status=403)

    try:
        emp = user.employee
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profile nahi mila.'}, status=404)

    # Face check removed — direct login with username/password

    # Geo-fence check
    distance_m = None
    office = OfficeLocation.objects.filter(is_active=True).first()
    if office:
        if not lat or not lon:
            return Response({'error': 'Location access do. GPS zaroori hai.'}, status=400)
        within, distance_m = office.is_within_radius(float(lat), float(lon))
        if not within:
            return Response({
                'error': f'Aap office se {distance_m}m door hain. 100m ke andar aao.',
                'distance': distance_m,
                'office_radius': office.radius_meters,
            }, status=403)

    login(request, user)

    today = timezone.localdate()
    att, created = Attendance.objects.get_or_create(
        employee=emp, date=today,
        defaults={
            'login_time': timezone.now(),
            'face_verified': True,
            'status': 'present',
            'login_latitude': lat,
            'login_longitude': lon,
            'login_distance_m': distance_m,
        }
    )
    if not created and not att.login_time:
        att.login_time = timezone.now()
        att.face_verified = True
        att.login_latitude = lat
        att.login_longitude = lon
        att.login_distance_m = distance_m
        att.save()

    return Response({
        'success': True,
        'message': f'Welcome {user.get_full_name() or username}!',
        'is_admin': user.is_staff,
        'employee': {
            'id': emp.id,
            'name': user.get_full_name() or username,
            'username': user.username,
            'employee_id': emp.employee_id,
            'department': emp.department,
        },
        'attendance': {
            'id': att.id,
            'date': str(att.date),
            'login_time': att.login_time.isoformat() if att.login_time else None,
            'already_logged_in': not created,
        },
        'distance_m': distance_m,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        emp = request.user.employee
        today = timezone.localdate()
        try:
            att = Attendance.objects.get(employee=emp, date=today)
            now = timezone.now()
            _close_open_breaks(att, now)

            total_break_mins = _total_break_minutes(att)
            att.total_break_hours = Decimal(str(round(total_break_mins / 60, 2)))

            # Check violation
            max_mins = Attendance.MAX_BREAK_HOURS * 60
            if total_break_mins > max_mins:
                att.break_violation = True
                att.break_violation_minutes = int(total_break_mins - max_mins)

            att.logout_time = now
            att.update_status()
            att.save()

            logout(request)
            return Response({
                'success': True,
                'summary': {
                    'date': str(att.date),
                    'login_time': att.login_time.strftime('%I:%M %p') if att.login_time else '-',
                    'logout_time': att.logout_time.strftime('%I:%M %p'),
                    'total_work_hours': float(att.total_work_hours),
                    'total_break_hours': float(att.total_break_hours),
                    'break_violation': att.break_violation,
                    'break_violation_minutes': att.break_violation_minutes,
                    'status': att.status,
                }
            })
        except Attendance.DoesNotExist:
            logout(request)
            return Response({'success': True, 'message': 'Logout ho gaye.'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ── DASHBOARD ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    try:
        emp = request.user.employee
        today = timezone.localdate()
        att_data = None

        try:
            att = Attendance.objects.get(employee=emp, date=today)
            now = timezone.now()
            open_break = BreakRecord.objects.filter(att=att, break_end__isnull=True).first() if False else \
                         BreakRecord.objects.filter(attendance=att, break_end__isnull=True).first()

            total_break_mins = _total_break_minutes(att)
            if open_break:
                total_break_mins += (now - open_break.break_start).total_seconds() / 60

            elapsed = int((now - att.login_time).total_seconds()) if att.login_time else 0

            # Office location
            office = OfficeLocation.objects.filter(is_active=True).first()

            att_data = {
                'id': att.id,
                'date': str(att.date),
                'login_time': att.login_time.isoformat() if att.login_time else None,
                'logout_time': att.logout_time.isoformat() if att.logout_time else None,
                'elapsed_seconds': elapsed,
                'total_break_minutes': round(total_break_mins, 2),
                'on_break': open_break is not None,
                'break_start': open_break.break_start.isoformat() if open_break else None,
                'break_type': open_break.break_type if open_break else None,
                'status': att.status,
                'break_violation': att.break_violation,
                'break_violation_minutes': att.break_violation_minutes,
                'required_hours': Attendance.REQUIRED_HOURS,
                'max_break_hours': Attendance.MAX_BREAK_HOURS,
                'office_lat': office.latitude if office else None,
                'office_lon': office.longitude if office else None,
                'office_radius': office.radius_meters if office else None,
            }
        except Attendance.DoesNotExist:
            office = OfficeLocation.objects.filter(is_active=True).first()
            att_data = {
                'office_lat': office.latitude if office else None,
                'office_lon': office.longitude if office else None,
                'office_radius': office.radius_meters if office else None,
            }

        # Leave balance
        pending_leave = LeaveRequest.objects.filter(employee=emp, status='pending').count()

        return Response({
            'employee': {
                'id': emp.id,
                'name': request.user.get_full_name() or request.user.username,
                'username': request.user.username,
                'employee_id': emp.employee_id,
                'department': emp.department,
                'leave_balance': emp.remaining_leave_days,
                'pending_leave_requests': pending_leave,
                'profile_photo': request.build_absolute_uri(emp.profile_photo.url) if emp.profile_photo else None,
            },
            'attendance': att_data,
        })
    except Employee.DoesNotExist:
        return Response({'error': 'Employee nahi mila.'}, status=404)


# ── GEO-FENCE PING ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def geo_ping(request):
    """
    Called every 30s from frontend with current GPS.
    Auto starts/ends geo break based on office radius.
    """
    lat = request.data.get('latitude')
    lon = request.data.get('longitude')
    if not lat or not lon:
        return Response({'error': 'GPS coordinates missing.'}, status=400)

    office = OfficeLocation.objects.filter(is_active=True).first()
    if not office:
        return Response({'status': 'no_office_set', 'inside': True})

    within, distance_m = office.is_within_radius(float(lat), float(lon))

    try:
        emp = request.user.employee
        today = timezone.localdate()
        att = Attendance.objects.get(employee=emp, date=today, logout_time__isnull=True)
        now = timezone.now()

        open_break = BreakRecord.objects.filter(attendance=att, break_end__isnull=True).first()
        action = None

        if not within and not open_break:
            # Left office → auto start geo break
            b = BreakRecord.objects.create(
                attendance=att,
                break_start=now,
                break_type='geo'
            )
            action = 'break_started'

        elif within and open_break and open_break.break_type == 'geo':
            # Back in office → auto end geo break
            open_break.break_end = now
            open_break.calculate_duration()
            open_break.save()

            # Check violation
            total_break_mins = _total_break_minutes(att)
            att.total_break_hours = Decimal(str(round(total_break_mins / 60, 2)))
            max_mins = Attendance.MAX_BREAK_HOURS * 60
            if total_break_mins > max_mins:
                att.break_violation = True
                att.break_violation_minutes = int(total_break_mins - max_mins)
                att.save()
            else:
                att.save()
            action = 'break_ended'

        return Response({
            'inside': within,
            'distance_m': distance_m,
            'office_radius': office.radius_meters,
            'action': action,
        })

    except Attendance.DoesNotExist:
        return Response({'inside': within, 'distance_m': distance_m, 'action': None})


# ── BREAK MANUAL ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def break_start(request):
    try:
        emp = request.user.employee
        today = timezone.localdate()
        att = Attendance.objects.get(employee=emp, date=today)

        if BreakRecord.objects.filter(attendance=att, break_end__isnull=True).exists():
            return Response({'error': 'Pehle se break chal rahi hai.'}, status=400)

        total_mins = _total_break_minutes(att)
        max_mins = Attendance.MAX_BREAK_HOURS * 60
        remaining = max_mins - total_mins

        if remaining <= 0:
            return Response({'error': f'Break limit ({int(Attendance.MAX_BREAK_HOURS)} hr) khatam ho gayi.'}, status=400)

        b = BreakRecord.objects.create(attendance=att, break_start=timezone.now(), break_type='manual')
        return Response({
            'success': True,
            'break_id': b.id,
            'break_start': b.break_start.isoformat(),
            'remaining_minutes': round(remaining, 1),
        })
    except Attendance.DoesNotExist:
        return Response({'error': 'Pehle login karein.'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def break_end(request):
    try:
        emp = request.user.employee
        today = timezone.localdate()
        att = Attendance.objects.get(employee=emp, date=today)

        b = BreakRecord.objects.filter(attendance=att, break_end__isnull=True).first()
        if not b:
            return Response({'error': 'Koi active break nahi hai.'}, status=400)

        b.break_end = timezone.now()
        b.calculate_duration()
        b.save()

        total_mins = _total_break_minutes(att)
        att.total_break_hours = Decimal(str(round(total_mins / 60, 2)))
        max_mins = Attendance.MAX_BREAK_HOURS * 60
        violation = total_mins > max_mins
        if violation:
            att.break_violation = True
            att.break_violation_minutes = int(total_mins - max_mins)
        att.save()

        return Response({
            'success': True,
            'duration_minutes': float(b.duration_minutes),
            'total_break_minutes': round(total_mins, 1),
            'is_violation': violation,
            'violation_minutes': int(total_mins - max_mins) if violation else 0,
        })
    except Attendance.DoesNotExist:
        return Response({'error': 'Attendance nahi mili.'}, status=404)


# ── ATTENDANCE HISTORY ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_history(request):
    try:
        emp = request.user.employee
        records = Attendance.objects.filter(employee=emp).order_by('-date')[:30]
        data = []
        for a in records:
            data.append({
                'date': str(a.date),
                'login_time': a.login_time.strftime('%I:%M %p') if a.login_time else '-',
                'logout_time': a.logout_time.strftime('%I:%M %p') if a.logout_time else '-',
                'work_hours': float(a.total_work_hours),
                'break_hours': float(a.total_break_hours),
                'status': a.status,
                'face_verified': a.face_verified,
                'break_violation': a.break_violation,
                'violation_minutes': a.break_violation_minutes,
            })
        return Response({'history': data})
    except Employee.DoesNotExist:
        return Response({'error': 'Employee nahi mila.'}, status=404)


# ── LIVE ATTENDANCE (Admin) ───────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def live_attendance(request):
    if not request.user.is_staff:
        return Response({'error': 'Admin access required.'}, status=403)

    today = timezone.localdate()
    all_employees = Employee.objects.filter(is_active=True).select_related('user')
    total = all_employees.count()

    present, on_break_list, absent_list, on_leave_list = [], [], [], []

    for emp in all_employees:
        info = {
            'id': emp.id,
            'name': emp.user.get_full_name() or emp.user.username,
            'employee_id': emp.employee_id,
            'department': emp.department,
        }
        try:
            att = Attendance.objects.get(employee=emp, date=today)
            if att.status == 'on_leave':
                on_leave_list.append(info)
                continue

            open_break = BreakRecord.objects.filter(attendance=att, break_end__isnull=True).first()
            info.update({
                'login_time': att.login_time.strftime('%I:%M %p') if att.login_time else '-',
                'logout_time': att.logout_time.strftime('%I:%M %p') if att.logout_time else None,
                'work_hours': float(att.total_work_hours),
                'break_violation': att.break_violation,
                'violation_minutes': att.break_violation_minutes,
                'on_break': open_break is not None,
                'break_type': open_break.break_type if open_break else None,
            })

            if att.logout_time:
                absent_list.append({**info, 'reason': 'logged_out'})
            elif open_break:
                on_break_list.append(info)
            elif att.login_time:
                present.append(info)
            else:
                absent_list.append({**info, 'reason': 'not_logged_in'})

        except Attendance.DoesNotExist:
            # Check leave
            leave = LeaveRequest.objects.filter(
                employee=emp, from_date__lte=today, to_date__gte=today, status='approved'
            ).first()
            if leave:
                on_leave_list.append({**info, 'leave_type': leave.leave_type})
            else:
                absent_list.append({**info, 'reason': 'not_logged_in'})

    return Response({
        'date': str(today),
        'summary': {
            'total': total,
            'present': len(present),
            'on_break': len(on_break_list),
            'absent': len(absent_list),
            'on_leave': len(on_leave_list),
        },
        'present': present,
        'on_break': on_break_list,
        'absent': absent_list,
        'on_leave': on_leave_list,
    })


# ── BREAK VIOLATIONS (Admin) ──────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def break_violations(request):
    if not request.user.is_staff:
        return Response({'error': 'Admin access required.'}, status=403)

    days = int(request.query_params.get('days', 7))
    from_date = timezone.localdate() - timedelta(days=days)

    violations = Attendance.objects.filter(
        break_violation=True,
        date__gte=from_date
    ).select_related('employee__user').order_by('-date')

    data = []
    for v in violations:
        breaks = BreakRecord.objects.filter(attendance=v)
        data.append({
            'employee': v.employee.user.get_full_name() or v.employee.user.username,
            'employee_id': v.employee.employee_id,
            'department': v.employee.department,
            'date': str(v.date),
            'total_break_minutes': round(float(v.total_break_hours) * 60, 1),
            'allowed_minutes': 60,
            'excess_minutes': v.break_violation_minutes,
            'breaks': [
                {
                    'start': b.break_start.strftime('%I:%M %p'),
                    'end': b.break_end.strftime('%I:%M %p') if b.break_end else 'Open',
                    'duration': float(b.duration_minutes),
                    'type': b.break_type,
                }
                for b in breaks
            ]
        })

    return Response({'violations': data, 'days': days, 'total': len(data)})


# ── LEAVE TRACKER ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def leave_request(request):
    emp = request.user.employee

    if request.method == 'GET':
        leaves = LeaveRequest.objects.filter(employee=emp)
        data = []
        for l in leaves:
            data.append({
                'id': l.id,
                'leave_type': l.leave_type,
                'from_date': str(l.from_date),
                'to_date': str(l.to_date),
                'total_days': l.total_days,
                'reason': l.reason,
                'status': l.status,
                'applied_on': l.applied_on.strftime('%d %b %Y'),
                'review_note': l.review_note,
            })
        return Response({
            'leaves': data,
            'balance': {
                'total': emp.total_leave_days,
                'used': emp.used_leave_days,
                'remaining': emp.remaining_leave_days,
            }
        })

    # POST — apply leave
    data = request.data
    from_date = data.get('from_date')
    to_date = data.get('to_date')
    leave_type = data.get('leave_type', 'casual')
    reason = data.get('reason', '').strip()

    if not from_date or not to_date or not reason:
        return Response({'error': 'from_date, to_date aur reason zaroori hain.'}, status=400)

    from datetime import date
    fd = date.fromisoformat(from_date)
    td = date.fromisoformat(to_date)
    if fd > td:
        return Response({'error': 'from_date, to_date se pehle honi chahiye.'}, status=400)

    days = (td - fd).days + 1

    if leave_type != 'unpaid' and days > emp.remaining_leave_days:
        return Response({
            'error': f'Sirf {emp.remaining_leave_days} din ki leave bachi hai.'
        }, status=400)

    # Check overlap
    overlap = LeaveRequest.objects.filter(
        employee=emp,
        status__in=['pending', 'approved'],
        from_date__lte=td,
        to_date__gte=fd,
    ).exists()
    if overlap:
        return Response({'error': 'In dates pe pehle se leave apply hai.'}, status=400)

    leave = LeaveRequest.objects.create(
        employee=emp,
        leave_type=leave_type,
        from_date=fd,
        to_date=td,
        total_days=days,
        reason=reason,
    )
    return Response({'success': True, 'leave_id': leave.id, 'total_days': days})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_action(request, leave_id):
    """Admin: approve or reject a leave"""
    if not request.user.is_staff:
        return Response({'error': 'Admin only.'}, status=403)

    action = request.data.get('action')  # 'approved' or 'rejected'
    note = request.data.get('note', '')

    if action not in ['approved', 'rejected']:
        return Response({'error': "action 'approved' ya 'rejected' hona chahiye."}, status=400)

    try:
        leave = LeaveRequest.objects.get(id=leave_id)
    except LeaveRequest.DoesNotExist:
        return Response({'error': 'Leave request nahi mili.'}, status=404)

    if leave.status != 'pending':
        return Response({'error': 'Ye request pehle se process ho chuki hai.'}, status=400)

    leave.status = action
    leave.reviewed_by = request.user
    leave.reviewed_on = timezone.now()
    leave.review_note = note
    leave.save()

    if action == 'approved':
        emp = leave.employee
        emp.used_leave_days += leave.total_days
        emp.save()

    return Response({'success': True, 'status': action})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leave_list_admin(request):
    """Admin: see all leave requests"""
    if not request.user.is_staff:
        return Response({'error': 'Admin only.'}, status=403)

    status_filter = request.query_params.get('status', 'pending')
    leaves = LeaveRequest.objects.filter(status=status_filter).select_related('employee__user')
    data = []
    for l in leaves:
        data.append({
            'id': l.id,
            'employee': l.employee.user.get_full_name() or l.employee.user.username,
            'employee_id': l.employee.employee_id,
            'department': l.employee.department,
            'leave_type': l.leave_type,
            'from_date': str(l.from_date),
            'to_date': str(l.to_date),
            'total_days': l.total_days,
            'reason': l.reason,
            'status': l.status,
            'applied_on': l.applied_on.strftime('%d %b %Y'),
        })
    return Response({'leaves': data})


# ── OFFICE LOCATION ───────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def office_location(request):
    if request.method == 'GET':
        office = OfficeLocation.objects.filter(is_active=True).first()
        if not office:
            return Response({'office': None})
        return Response({'office': {
            'id': office.id,
            'name': office.name,
            'latitude': office.latitude,
            'longitude': office.longitude,
            'radius_meters': office.radius_meters,
        }})

    if not request.user.is_staff:
        return Response({'error': 'Admin only.'}, status=403)

    data = request.data
    OfficeLocation.objects.update(is_active=False)
    office = OfficeLocation.objects.create(
        name=data.get('name', 'Main Office'),
        latitude=float(data.get('latitude')),
        longitude=float(data.get('longitude')),
        radius_meters=int(data.get('radius_meters', 100)),
        is_active=True,
    )
    return Response({'success': True, 'office': {
        'id': office.id, 'name': office.name,
        'latitude': office.latitude, 'longitude': office.longitude,
        'radius_meters': office.radius_meters,
    }})


# ── FACE ──────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_credentials(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()
    if not username or not password:
        return Response({'error': 'Username aur password zaroori hain.'}, status=400)
    user = authenticate(request, username=username, password=password)
    if not user:
        return Response({'error': 'Username ya password galat hai.'}, status=401)
    try:
        emp = user.employee
    except Employee.DoesNotExist:
        return Response({'error': 'Employee profile nahi mila.'}, status=404)
    login(request, user)
    return Response({'success': True, 'employee': {
        'name': user.get_full_name() or user.username,
        'employee_id': emp.employee_id,
    }})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_face(request):
    try:
        emp = request.user.employee
        descriptor = request.data.get('face_descriptor')
        if not descriptor:
            return Response({'error': 'Face descriptor missing.'}, status=400)
        emp.face_descriptor = json.dumps(descriptor)
        emp.save()
        return Response({'success': True, 'message': 'Face register ho gaya!'})
    except Employee.DoesNotExist:
        return Response({'error': 'Employee nahi mila.'}, status=404)
