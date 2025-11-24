from django.core.management.base import BaseCommand
from core.models import TimeSlot
from datetime import time

class Command(BaseCommand):
    help = 'Populates TimeSlot model with 8 time slots'

    def handle(self, *args, **kwargs):
        # Clear existing TimeSlots to avoid duplicates
        TimeSlot.objects.all().delete()

        # Define time slots: 90 minutes each, 10-min breaks, 30-min break between III and IV
        timeslots = [
            ('I', '08:00:00', '09:30:00'),  # 08:00–09:30
            ('II', '09:40:00', '11:10:00'), # 09:40–11:10
            ('III', '11:20:00', '12:50:00'),# 11:20–12:50
            ('IV', '13:20:00', '14:50:00'), # 13:20–14:50
            ('V', '15:00:00', '16:30:00'),  # 15:00–16:30
            ('VI', '16:40:00', '18:10:00'), # 16:40–18:10
            ('VII', '18:20:00', '19:50:00'),# 18:20–19:50
            ('VIII', '20:00:00', '21:30:00'),# 20:00–21:30
        ]

        for name, start, end in timeslots:
            TimeSlot.objects.create(
                name=name,
                start_time=start,
                end_time=end
            )
        self.stdout.write(self.style.SUCCESS('Successfully populated 8 time slots'))