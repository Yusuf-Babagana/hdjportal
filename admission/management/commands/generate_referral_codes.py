from django.core.management.base import BaseCommand
from admission.models import ReferralCode
import random
import string

class Command(BaseCommand):
    help = 'Generate referral codes for the admission portal'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, help='Number of referral codes to generate')

    def handle(self, *args, **options):
        count = options['count']
        generated = 0
        
        for _ in range(count):
            # Generate unique 8-character alphanumeric code
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not ReferralCode.objects.filter(code=code).exists():
                    ReferralCode.objects.create(code=code)
                    generated += 1
                    break
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated {generated} referral codes.')
        )