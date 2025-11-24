from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image

class TimeSlot(models.Model):
    name = models.CharField(max_length=10)  # e.g., 'I', 'II'
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"

class LessonType(models.Model):
    name = models.CharField(max_length=50)  # e.g., 'Лекц', 'Лаб', 'Семинар'

    def __str__(self):
        return self.name

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=20, unique=True)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.code})"

class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    credit = models.IntegerField()
    teachers = models.ManyToManyField(Teacher)  # Multiple teachers per course
    lesson_type = models.ForeignKey(LessonType, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Group(models.Model):
    name = models.CharField(max_length=100)  # e.g., 'Мэдээллийн систем-1'

    def __str__(self):
        return self.name

class Student(models.Model):
    code = models.CharField(max_length=20, unique=True)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)
    year = models.IntegerField()  # Course/year, e.g., 1, 2, 3, 4

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.code})"

class AttendanceSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.SET_NULL, null=True)
    date = models.DateField(default=timezone.now)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)  # Generated QR
    location_lat = models.FloatField(null=True, blank=True)  # Optional: School lat for validation
    location_long = models.FloatField(null=True, blank=True)  # School long
    location_radius = models.FloatField(default=500)  # Meters for validation

    def __str__(self):
        return f"{self.course} - {self.date} {self.timeslot}"

    def generate_qr_code(self):
        # Generate QR linking to /attend/<session_id>/
        url = f"127.0.0.1/attend/{self.id}/"  # Replace with actual domain
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        file_name = f"qr_{self.id}.png"
        self.qr_code.save(file_name, File(buffer), save=False)
        self.save()

class Attendance(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    student_lat = models.FloatField(null=True, blank=True)  # From geolocation
    student_long = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('session', 'student')  # No duplicates

    def __str__(self):
        return f"{self.student} at {self.session}"