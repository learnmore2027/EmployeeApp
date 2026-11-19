import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employeeapp.settings')
django.setup()

from django.contrib.auth.models import User
from employees.models import Employee

# Create employee profile for admin
try:
    user = User.objects.get(username='admin')
    if not hasattr(user, 'employee'):
        Employee.objects.create(
            user=user,
            employee_id='EMP000',
            department='IT Admin'
        )
        print("Employee profile created for admin!")
    else:
        print("Employee profile already exists!")
except User.DoesNotExist:
    print("Admin user not found!")
