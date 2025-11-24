from django.db import models
from django.contrib.auth.models import User
from datetime import date
import uuid


# ===============================
# Location - Байршил
# ===============================
class Location(models.Model):
    name = models.CharField(max_length=100, verbose_name="Нэр")
    latitude = models.FloatField(verbose_name="Өргөрөг")
    longitude = models.FloatField(verbose_name="Уртраг")
    radius_m = models.PositiveIntegerField(default=100, verbose_name="Радиус (м)")

    class Meta:
        verbose_name = "Байршил"
        verbose_name_plural = "Байршлууд"

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"


# ===============================
# Student - Оюутан
# ===============================
class Student(models.Model):
    student_code = models.CharField(max_length=50, unique=True, verbose_name="Оюутны код")
    full_name = models.CharField(max_length=200, verbose_name="Нэр")

    class Meta:
        verbose_name = "Оюутан"
        verbose_name_plural = "Оюутнууд"

    def __str__(self):
        return f"{self.full_name} ({self.student_code})"


# ===============================
# Course - Хичээл
# ===============================
class Course(models.Model):
    name = models.CharField(max_length=200, verbose_name="Хичээлийн нэр")
    code = models.CharField(max_length=50, blank=True, verbose_name="Хичээлийн код")

    class Meta:
        verbose_name = "Хичээл"
        verbose_name_plural = "Хичээлүүд"

    def __str__(self):
        return f"{self.name} ({self.code})"


# ===============================
# TeacherProfile - Багш
# ===============================
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=256, verbose_name="Нэр")

    class Meta:
        verbose_name = "Багш"
        verbose_name_plural = "Багш нар"

    def __str__(self):
        return self.name


# ===============================
# WeeklySchedule - Долоо хоногийн хуваарь
# ===============================
class WeeklySchedule(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Даваа'),
        (1, 'Мягмар'),
        (2, 'Лхагва'),
        (3, 'Пүрэв'),
        (4, 'Баасан'),
        (5, 'Бямба'),
        (6, 'Ням'),
    ]
    
    TIME_CHOICES = [
        ('I', '08:00-09:30'),
        ('II', '09:40-11:10'),
        ('III', '11:20-12:50'),
        ('IV', '13:20-14:50'),
        ('V', '15:00-16:30'),
        ('VI', '16:40-18:10'),
        ('VII', '18:20-19:50'),
        ('VIII', '20:00-21:30'),
    ]

    FORM_CHOICES = [
        ('Lecture', 'Лекц'),
        ('Seminar', 'Семинар'),
        ('Lab', 'Лаборатори'),
        ('Practice', 'Дадлага'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Хичээл")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, verbose_name="Багш")
    day_of_week = models.IntegerField(choices=WEEKDAY_CHOICES, verbose_name="Гараг")
    start_time = models.CharField(max_length=20, choices=TIME_CHOICES, verbose_name="Цаг")
    form = models.CharField(max_length=20, choices=FORM_CHOICES, verbose_name="Хичээлийн төрөл")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Байршил")
    week_start = models.DateField(verbose_name="Долоо хоногийн эхлэх өдөр")
    week_end = models.DateField(verbose_name="Долоо хоногийн дуусах өдөр")
    is_active = models.BooleanField(default=True, verbose_name="Идэвхтэй эсэх")
    
    class Meta:
        verbose_name = "Долоо хоногийн хуваарь"
        verbose_name_plural = "Долоо хоногийн хуваарь"
        ordering = ['week_start', 'day_of_week', 'start_time']
        unique_together = ['course', 'teacher', 'day_of_week', 'start_time', 'week_start']
    
    def __str__(self):
        return f"{self.course} - {self.get_day_of_week_display()} {self.start_time} ({self.week_start} - {self.week_end})"
    
    def is_current_week(self):
        """Одоогийн долоо хоногт хамаарах эсэхийг шалгах"""
        today = date.today()
        return self.week_start <= today <= self.week_end


# ===============================
# ClassSession - Хичээлийн сесс (QR код үүсгэх)
# ===============================
class ClassSession(models.Model):
    TIME_CHOICES = [
        ('I', '08:00-09:30'),
        ('II', '09:40-11:10'),
        ('III', '11:20-12:50'),
        ('IV', '13:20-14:50'),
        ('V', '15:00-16:30'),
        ('VI', '16:40-18:10'),
        ('VII', '18:20-19:50'),
        ('VIII', '20:00-21:30'),
    ]

    FORM_CHOICES = [
        ('Lecture', 'Лекц'),
        ('Seminar', 'Семинар'),
        ('Lab', 'Лаборатори'),
        ('Practice', 'Дадлага'),
    ]

    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, verbose_name="Багш")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Хичээл")
    start_time = models.CharField(max_length=20, choices=TIME_CHOICES, verbose_name="Цаг")
    form = models.CharField(max_length=20, choices=FORM_CHOICES, verbose_name="Төрөл")
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="QR Token")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Байршил")
    week_schedule = models.ForeignKey(
        WeeklySchedule, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Долоо хоногийн хуваарь"
    )
    session_date = models.DateField(auto_now_add=True, verbose_name="Хичээл орсон өдөр")
    is_active = models.BooleanField(default=True, verbose_name="QR идэвхтэй эсэх")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Үүссэн огноо")

    class Meta:
        verbose_name = "Хичээлийн сесс"
        verbose_name_plural = "Хичээлийн сессүүд"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.course} [{self.start_time}] by {self.teacher} - {self.session_date}"


# ===============================
# Enrollment - Бүртгэл (Оюутан хичээл сонгосон)
# ===============================
class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Оюутан")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Хичээл")

    class Meta:
        verbose_name = "Бүртгэл"
        verbose_name_plural = "Бүртгэлүүд"
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student} in {self.course}"


# ===============================
# Attendance - Ирц
# ===============================
class Attendance(models.Model):
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, verbose_name="Хичээл")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Оюутан")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Бүртгүүлсэн цаг")
    lat = models.FloatField(null=True, blank=True, verbose_name="Latitude")
    lon = models.FloatField(null=True, blank=True, verbose_name="Longitude")
    success = models.BooleanField(default=False, verbose_name="Ирсэн эсэх")
    note = models.CharField(max_length=255, blank=True, verbose_name="Тэмдэглэл")

    class Meta:
        verbose_name = "Ирц"
        verbose_name_plural = "Ирцүүд"
        unique_together = ('session', 'student')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.student} @ {self.session} -> {'Ирсэн' if self.success else 'Тасалсан'}"
    
    def distance_from_location(self):
        """Зөвшөөрөгдсөн байршлаас хэр зайтай байсныг тооцоолох (метрээр)"""
        if not self.session.location or not (self.lat and self.lon):
            return None
        
        from math import radians, sin, cos, sqrt, asin
        R = 6371000.0
        lat1, lon1 = self.session.location.latitude, self.session.location.longitude
        lat2, lon2 = self.lat, self.lon
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return int(R * c)
    
    @property
    def status_display(self):
        """Ирцийн төлөв харуулах"""
        if self.success:
            return "Ирсэн"
        elif "not enrolled" in self.note:
            return "Бүртгэлгүй"
        elif "location" in self.note:
            return "Байршил буруу"
        else:
            return "Тасалсан"


# ===============================
# AttendanceReport - Ирцийн тайлан
# ===============================
class AttendanceReport(models.Model):
    EXPORT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
    ]
    
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, verbose_name="Багш")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Хичээл")
    session = models.ForeignKey(ClassSession, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Хичээлийн сесс")
    format = models.CharField(max_length=10, choices=EXPORT_FORMAT_CHOICES, verbose_name="Формат")
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="Үүссэн огноо")
    file = models.FileField(upload_to='reports/', null=True, blank=True, verbose_name="Файл")
    
    class Meta:
        verbose_name = "Ирцийн тайлан"
        verbose_name_plural = "Ирцийн тайлангууд"
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"{self.course} - {self.format} - {self.generated_at.strftime('%Y-%m-%d %H:%M')}"
# ClassSession model дотор:
def get_start_time_display(self):
    return dict(self.TIME_CHOICES).get(self.start_time, self.start_time)
