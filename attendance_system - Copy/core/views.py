from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import AttendanceSession, Attendance, Student
from django.views import View
from math import radians, sin, cos, sqrt, atan2  # For distance calculation

class AttendView(View):
    def get(self, request, session_id):
        session = get_object_or_404(AttendanceSession, id=session_id)
        return render(request, 'attend.html', {'session': session})

    def post(self, request, session_id):
        session = get_object_or_404(AttendanceSession, id=session_id)
        student_code = request.POST.get('student_code')
        lat = request.POST.get('lat')
        long = request.POST.get('long')

        try:
            student = Student.objects.get(code=student_code)
        except Student.DoesNotExist:
            return HttpResponse("Invalid student code.", status=400)

        # Location check (Haversine formula for distance)
        if session.location_lat and session.location_long and lat and long:
            lat1, lon1 = radians(float(lat)), radians(float(long))
            lat2, lon2 = radians(session.location_lat), radians(session.location_long)
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance = 6371000 * c  # Earth radius in meters
            if distance > session.location_radius:
                return HttpResponse("You are not at the location.", status=400)

        # Register attendance
        Attendance.objects.create(session=session, student=student, student_lat=lat, student_long=long)
        return HttpResponse("Attendance registered successfully.")