import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from PIL import Image

class ReferralCode(models.Model):
    code = models.CharField(max_length=10, unique=True)
    is_used = models.BooleanField(default=False)
    used_by = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.code} - {'Used' if self.is_used else 'Available'}"

    class Meta:
        verbose_name = "Referral Code"
        verbose_name_plural = "Referral Codes"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number format: '+999999999'. Up to 15 digits allowed.")
    phone = models.CharField(validators=[phone_regex], max_length=17)
    has_paid = models.BooleanField(default=False)
    referral_code = models.OneToOneField(ReferralCode, on_delete=models.SET_NULL, null=True, blank=True)
    can_apply = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.user.email}"

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"

class Payment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    paystack_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.user.get_full_name()} - ₦{self.amount} ({self.status})"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

def upload_passport(instance, filename):
    return f'passports/{instance.student.user.id}/{filename}'

def upload_document(instance, filename):
    return f'documents/{instance.application.student.user.id}/{filename}'

class Application(models.Model):
    COURSE_CHOICES = [
        ('diploma_community_health', 'Diploma in Community Health (SCHEW)'),
        ('certificate_community_health', 'Certificate in Community Health (JCHEW)'),
        ('diploma_health_info', 'Diploma in Health Information Management'),
        ('diploma_environmental_health', 'Diploma in Environmental Health'),
        ('diploma_xray', 'Diploma in X-Ray and Imaging'),
        ('diploma_nutrition', 'Diploma in Nutrition and Dietetics'),
        ('retraining_community_health', 'Retraining in Community Health (JCHEW holders)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('incomplete', 'Incomplete'),
    ]

    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    application_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # Section A - Personal Information
    passport_photo = models.ImageField(upload_to=upload_passport, help_text="Upload passport photograph")
    first_name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    other_name = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=17)
    email = models.EmailField()
    address = models.TextField()
    lga = models.CharField(max_length=100, verbose_name="Local Government Area")
    state_of_origin = models.CharField(max_length=50)
    
    # Guardian/Next of Kin
    guardian_name = models.CharField(max_length=100)
    guardian_phone = models.CharField(max_length=17)
    guardian_address = models.TextField()
    guardian_relationship = models.CharField(max_length=50)
    
    # Section D - Courses
    first_choice = models.CharField(max_length=50, choices=COURSE_CHOICES)
    second_choice = models.CharField(max_length=50, choices=COURSE_CHOICES)
    
    # Section E - Declaration
    declaration_text = models.TextField(help_text="Type your full name and declaration statement")
    
    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.application_number:
            # Generate unique application number
            year = timezone.now().year
            count = Application.objects.filter(created_at__year=year).count() + 1
            self.application_number = f"CHSTH/{year}/{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_number} - {self.student.user.get_full_name()}"

    class Meta:
        verbose_name = "Application"
        verbose_name_plural = "Applications"

class SchoolAttended(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='schools_attended')
    school_name = models.CharField(max_length=200)
    from_year = models.CharField(max_length=4)
    to_year = models.CharField(max_length=4)

    def __str__(self):
        return f"{self.school_name} ({self.from_year}-{self.to_year})"

    class Meta:
        verbose_name = "School Attended"
        verbose_name_plural = "Schools Attended"

class SSCEResult(models.Model):
    EXAM_TYPE_CHOICES = [
        ('waec', 'WAEC'),
        ('neco', 'NECO'),
        ('nabteb', 'NABTEB'),
        ('nbais', 'NBAIS'),
    ]
    
    GRADE_CHOICES = [
        ('A1', 'A1'),
        ('B2', 'B2'),
        ('B3', 'B3'),
        ('C4', 'C4'),
        ('C5', 'C5'),
        ('C6', 'C6'),
        ('D7', 'D7'),
        ('E8', 'E8'),
        ('F9', 'F9'),
        ('awaiting', 'Awaiting Result'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='ssce_results')
    sitting_number = models.IntegerField(choices=[(1, 'First Sitting'), (2, 'Second Sitting')])
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    exam_number = models.CharField(max_length=50)
    registration_number = models.CharField(max_length=50)
    centre_number = models.CharField(max_length=20)
    centre_name = models.CharField(max_length=200)
    year = models.CharField(max_length=4)

    # Required subjects
    english_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    mathematics_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    biology_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    chemistry_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    physics_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)

    # Other subjects (4 additional)
    subject_1 = models.CharField(max_length=50)
    subject_1_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    subject_2 = models.CharField(max_length=50)
    subject_2_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    subject_3 = models.CharField(max_length=50)
    subject_3_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)
    subject_4 = models.CharField(max_length=50)
    subject_4_grade = models.CharField(max_length=10, choices=GRADE_CHOICES)

    def __str__(self):
        return f"{self.exam_type} - Sitting {self.sitting_number} ({self.year})"

    class Meta:
        verbose_name = "SSCE Result"
        verbose_name_plural = "SSCE Results"
        unique_together = ['application', 'sitting_number']

class UploadedDocument(models.Model):
    DOCUMENT_TYPES = [
        ('ssce_result', 'SSCE Results'),
        ('primary_cert', 'Primary School Certificate'),
        ('indigene_cert', 'Indigene Certificate'),
        ('birth_cert', 'Birth Certificate/Declaration of Age'),
        ('other_credentials', 'Other Credentials'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document = models.FileField(upload_to=upload_document)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.application.student.user.get_full_name()}"

    class Meta:
        verbose_name = "Uploaded Document"
        verbose_name_plural = "Uploaded Documents"
        unique_together = ['application', 'document_type']