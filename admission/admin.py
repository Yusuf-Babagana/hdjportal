from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.http import HttpResponse
from django.urls import path
from django.shortcuts import render
import csv
from .models import *

# Customize Admin Site
admin.site.site_header = "CHSTH Admission Portal"
admin.site.site_title = "CHSTH Admin"
admin.site.index_title = "College of Health Sciences and Technology Hadejia"

class StudentInline(admin.StackedInline):
    model = Student
    can_delete = False
    verbose_name_plural = 'Student Information'

class UserAdmin(BaseUserAdmin):
    inlines = (StudentInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_phone', 'get_payment_status')
    
    def get_phone(self, obj):
        try:
            return obj.student.phone
        except:
            return '-'
    get_phone.short_description = 'Phone'
    
    def get_payment_status(self, obj):
        try:
            if obj.student.has_paid:
                return format_html('<span style="color: green;">Paid</span>')
            elif obj.student.referral_code:
                return format_html('<span style="color: blue;">Referral Used</span>')
            else:
                return format_html('<span style="color: red;">Unpaid</span>')
        except:
            return '-'
    get_payment_status.short_description = 'Payment Status'

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_used', 'used_by', 'used_at', 'created_at')
    list_filter = ('is_used', 'created_at')
    search_fields = ('code', 'used_by__username', 'used_by__email')
    readonly_fields = ('used_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('used_by')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_email', 'phone', 'has_paid', 'get_referral_code', 'can_apply', 'created_at')
    list_filter = ('has_paid', 'can_apply', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone')
    readonly_fields = ('created_at',)
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Full Name'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_referral_code(self, obj):
        return obj.referral_code.code if obj.referral_code else '-'
    get_referral_code.short_description = 'Referral Code'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('get_student_name', 'amount', 'status', 'reference', 'paystack_reference', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('reference', 'student__user__username', 'student__user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['mark_as_successful', 'mark_as_failed']
    
    def mark_as_successful(self, request, queryset):
        """Mark selected payments as successful and update student status"""
        updated = 0
        for payment in queryset:
            if payment.status != 'success':
                payment.status = 'success'
                payment.save()
                
                # Update student status
                student = payment.student
                student.has_paid = True
                student.can_apply = True
                student.save()
                updated += 1
        
        self.message_user(request, f"{updated} payments marked as successful and student access granted.")
    mark_as_successful.short_description = "Mark selected payments as successful"
    
    def mark_as_failed(self, request, queryset):
        """Mark selected payments as failed"""
        updated = queryset.update(status='failed')
        self.message_user(request, f"{updated} payments marked as failed.")
    mark_as_failed.short_description = "Mark selected payments as failed"
    
    def get_student_name(self, obj):
        return obj.student.user.get_full_name()
    get_student_name.short_description = 'Student'

class SchoolAttendedInline(admin.TabularInline):
    model = SchoolAttended
    extra = 0
    max_num = 3

class SSCEResultInline(admin.StackedInline):
    model = SSCEResult
    extra = 0
    max_num = 2

class UploadedDocumentInline(admin.TabularInline):
    model = UploadedDocument
    extra = 0

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_number', 'get_student_name', 'first_choice', 'status', 'is_submitted', 'submitted_at')
    list_filter = ('status', 'is_submitted', 'first_choice', 'created_at')
    search_fields = ('application_number', 'student__user__username', 'student__user__email', 'first_name', 'surname')
    readonly_fields = ('application_number', 'created_at', 'updated_at', 'submitted_at')
    inlines = [SchoolAttendedInline, SSCEResultInline, UploadedDocumentInline]
    
    fieldsets = (
        ('Application Info', {
            'fields': ('application_number', 'status', 'is_submitted', 'submitted_at')
        }),
        ('Personal Information', {
            'fields': ('passport_photo', 'first_name', 'surname', 'other_name', 'date_of_birth', 
                      'phone', 'email', 'address', 'lga', 'state_of_origin')
        }),
        ('Guardian Information', {
            'fields': ('guardian_name', 'guardian_phone', 'guardian_address', 'guardian_relationship')
        }),
        ('Course Selection', {
            'fields': ('first_choice', 'second_choice')
        }),
        ('Declaration', {
            'fields': ('declaration_text',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_student_name(self, obj):
        return obj.student.user.get_full_name()
    get_student_name.short_description = 'Student'
    
    actions = ['export_to_csv', 'approve_applications', 'reject_applications']
    
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="applications.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Application Number', 'Student Name', 'Email', 'Phone', 'First Choice', 
            'Second Choice', 'Status', 'Date Submitted'
        ])
        
        for application in queryset:
            writer.writerow([
                application.application_number,
                application.student.user.get_full_name(),
                application.student.user.email,
                application.phone,
                application.get_first_choice_display(),
                application.get_second_choice_display(),
                application.get_status_display(),
                application.submitted_at
            ])
        
        return response
    export_to_csv.short_description = "Export selected applications to CSV"
    
    def approve_applications(self, request, queryset):
        queryset.update(status='approved')
        self.message_user(request, f"{queryset.count()} applications approved.")
    approve_applications.short_description = "Approve selected applications"
    
    def reject_applications(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f"{queryset.count()} applications rejected.")
    reject_applications.short_description = "Reject selected applications"