from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils import timezone
from django.forms import formset_factory
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import json
import requests
import uuid
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.units import inch
import os
from PIL import Image as PILImage
from .models import *
from .forms import *

def home(request):
    """Homepage view"""
    context = {
        'application_fee': settings.APPLICATION_FEE,
    }
    return render(request, 'admission/home.html', context)

def register(request):
    """Student registration view"""
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            referral_code_str = form.cleaned_data.get('referral_code')
            
            # Create student profile
            student = Student.objects.create(
                user=user,
                phone=form.cleaned_data['phone']
            )
            
            # Handle referral code
            if referral_code_str:
                try:
                    referral_code = ReferralCode.objects.get(code=referral_code_str, is_used=False)
                    referral_code.is_used = True
                    referral_code.used_by = user
                    referral_code.used_at = timezone.now()
                    referral_code.save()
                    
                    student.referral_code = referral_code
                    student.can_apply = True
                    student.save()
                    
                    messages.success(request, 'Registration successful! You can now proceed to fill your application form.')
                except ReferralCode.DoesNotExist:
                    pass
            else:
                messages.success(request, 'Registration successful! Please make payment to access the application form.')
            
            login(request, user)
            return redirect('dashboard')
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'admission/register.html', {'form': form})

@login_required
def dashboard(request):
    """Student dashboard"""
    student = get_object_or_404(Student, user=request.user)
    
    context = {
        'student': student,
        'application_fee': settings.APPLICATION_FEE,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    }
    
    # Check if student has application
    try:
        application = Application.objects.get(student=student)
        context['application'] = application
    except Application.DoesNotExist:
        pass
    
    return render(request, 'admission/dashboard.html', context)

@login_required
def initiate_payment(request):
    """Initiate Paystack payment"""
    if request.method == 'POST':
        student = get_object_or_404(Student, user=request.user)
        
        if student.has_paid or student.can_apply:
            return JsonResponse({'error': 'Payment already completed or not required'}, status=400)
        
        # Check if there's already a pending payment
        existing_payment = Payment.objects.filter(
            student=student,
            status='pending'
        ).first()
        
        if existing_payment:
            reference = existing_payment.reference
        else:
            # Create new payment record
            reference = str(uuid.uuid4())
            payment = Payment.objects.create(
                student=student,
                reference=reference,
                amount=settings.APPLICATION_FEE
            )
        
        # Paystack payment data
        return JsonResponse({
            'reference': reference,
            'amount': settings.APPLICATION_FEE_KOBO,
            'email': student.user.email,
            'public_key': settings.PAYSTACK_PUBLIC_KEY,
            'callback_url': request.build_absolute_uri(reverse('verify_payment')),
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def verify_payment(request):
    """Verify Paystack payment"""
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, 'Invalid payment reference')
        return redirect('dashboard')
    
    try:
        payment = Payment.objects.get(reference=reference)
        student = payment.student
        
        # Check if this payment belongs to the current user
        if student.user != request.user:
            messages.error(request, 'Invalid payment reference for this account')
            return redirect('dashboard')
        
        # Verify payment with Paystack
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.get(
                f'https://api.paystack.co/transaction/verify/{reference}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] and data['data']['status'] == 'success':
                    # Verify the amount matches
                    paid_amount = data['data']['amount']  # Amount in kobo
                    expected_amount = settings.APPLICATION_FEE_KOBO
                    
                    if paid_amount >= expected_amount:
                        # Payment successful
                        payment.status = 'success'
                        payment.paystack_reference = data['data']['reference']
                        payment.save()
                        
                        # Update student status
                        student.has_paid = True
                        student.can_apply = True
                        student.save()
                        
                        messages.success(request, 'Payment successful! You can now fill your application form.')
                    else:
                        payment.status = 'failed'
                        payment.save()
                        messages.error(request, 'Payment amount verification failed.')
                else:
                    payment.status = 'failed'
                    payment.save()
                    messages.error(request, f'Payment failed: {data.get("message", "Unknown error")}')
            else:
                payment.status = 'failed'
                payment.save()
                messages.error(request, 'Payment verification failed. Please contact support.')
        except requests.exceptions.RequestException as e:
            messages.error(request, 'Network error during payment verification. Please try again.')
        except Exception as e:
            messages.error(request, 'An error occurred during payment verification. Please contact support.')
    
    except Payment.DoesNotExist:
        messages.error(request, 'Payment record not found.')
    
    return redirect('dashboard')

@login_required
def application_form(request):
    """Application form view"""
    student = get_object_or_404(Student, user=request.user)
    
    if not student.can_apply:
        messages.error(request, 'Please complete payment or use referral code to access application form.')
        return redirect('dashboard')
    
    # Get or create application
    application, created = Application.objects.get_or_create(
        student=student,
        defaults={
            'first_name': student.user.first_name,
            'surname': student.user.last_name,
            'email': student.user.email,
            'phone': student.phone,
        }
    )
    
    # Create formsets for related models
    SchoolFormSet = formset_factory(SchoolAttendedForm, extra=3, max_num=3)
    SSCEFormSet = formset_factory(SSCEResultForm, extra=2, max_num=2)
    DocumentFormSet = formset_factory(DocumentUploadForm, extra=5, max_num=5)
    
    if request.method == 'POST':
        # Process different sections
        section = request.POST.get('section')
        
        if section == 'personal':
            personal_form = ApplicationPersonalInfoForm(request.POST, request.FILES, instance=application)
            guardian_form = GuardianInfoForm(request.POST, instance=application)
            
            if personal_form.is_valid() and guardian_form.is_valid():
                personal_form.save()
                guardian_form.save()
                messages.success(request, 'Personal information saved successfully!')
                return redirect('application_form')
        
        elif section == 'schools':
            school_formset = SchoolFormSet(request.POST, prefix='schools')
            if school_formset.is_valid():
                # Delete existing schools
                SchoolAttended.objects.filter(application=application).delete()
                # Save new schools
                for form in school_formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                        school = form.save(commit=False)
                        school.application = application
                        school.save()
                messages.success(request, 'Schools information saved successfully!')
                return redirect('application_form')
        
        elif section == 'ssce':
            ssce_formset = SSCEFormSet(request.POST, prefix='ssce')
            if ssce_formset.is_valid():
                # Delete existing SSCE results
                SSCEResult.objects.filter(application=application).delete()
                # Save new SSCE results
                for form in ssce_formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                        ssce = form.save(commit=False)
                        ssce.application = application
                        ssce.save()
                messages.success(request, 'SSCE results saved successfully!')
                return redirect('application_form')
        
        elif section == 'courses':
            course_form = CourseSelectionForm(request.POST, instance=application)
            if course_form.is_valid():
                course_form.save()
                messages.success(request, 'Course selection saved successfully!')
                return redirect('application_form')
        
        elif section == 'declaration':
            declaration_form = DeclarationForm(request.POST, instance=application)
            if declaration_form.is_valid():
                declaration_form.save()
                messages.success(request, 'Declaration saved successfully!')
                return redirect('application_form')
        
        elif section == 'documents':
            document_formset = DocumentFormSet(request.POST, request.FILES, prefix='documents')
            if document_formset.is_valid():
                for form in document_formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                        document = form.save(commit=False)
                        document.application = application
                        # Check if document type already exists
                        existing_doc = UploadedDocument.objects.filter(
                            application=application,
                            document_type=document.document_type
                        ).first()
                        if existing_doc:
                            existing_doc.document = document.document
                            existing_doc.save()
                        else:
                            document.save()
                messages.success(request, 'Documents uploaded successfully!')
                return redirect('application_form')
        
        elif section == 'submit':
            # Final submission
            if application.passport_photo and application.declaration_text:
                application.is_submitted = True
                application.submitted_at = timezone.now()
                application.save()
                messages.success(request, 'Application submitted successfully!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Please complete all required sections before submitting.')
    
    # Initialize forms
    personal_form = ApplicationPersonalInfoForm(instance=application)
    guardian_form = GuardianInfoForm(instance=application)
    course_form = CourseSelectionForm(instance=application)
    declaration_form = DeclarationForm(instance=application)
    
    # Initialize formsets with existing data
    school_initial = [
        {'school_name': school.school_name, 'from_year': school.from_year, 'to_year': school.to_year}
        for school in application.schools_attended.all()
    ]
    school_formset = SchoolFormSet(prefix='schools', initial=school_initial)
    
    ssce_initial = []
    for result in application.ssce_results.all():
        ssce_initial.append({
            'sitting_number': result.sitting_number,
            'exam_type': result.exam_type,
            'exam_number': result.exam_number,
            'registration_number': result.registration_number,
            'centre_number': result.centre_number,
            'centre_name': result.centre_name,
            'year': result.year,
            'english_grade': result.english_grade,
            'mathematics_grade': result.mathematics_grade,
            'biology_grade': result.biology_grade,
            'chemistry_grade': result.chemistry_grade,
            'physics_grade': result.physics_grade,
            'subject_1': result.subject_1,
            'subject_1_grade': result.subject_1_grade,
            'subject_2': result.subject_2,
            'subject_2_grade': result.subject_2_grade,
            'subject_3': result.subject_3,
            'subject_3_grade': result.subject_3_grade,
            'subject_4': result.subject_4,
            'subject_4_grade': result.subject_4_grade,
        })
    ssce_formset = SSCEFormSet(prefix='ssce', initial=ssce_initial)
    
    document_formset = DocumentFormSet(prefix='documents')
    
    context = {
        'application': application,
        'personal_form': personal_form,
        'guardian_form': guardian_form,
        'school_formset': school_formset,
        'ssce_formset': ssce_formset,
        'course_form': course_form,
        'declaration_form': declaration_form,
        'document_formset': document_formset,
        'existing_documents': application.documents.all(),
    }
    
    return render(request, 'admission/application_form.html', context)

@login_required
def download_application_pdf(request):
    """Generate and download application form as PDF"""
    student = get_object_or_404(Student, user=request.user)
    
    try:
        application = Application.objects.get(student=student)
    except Application.DoesNotExist:
        messages.error(request, 'Application not found.')
        return redirect('dashboard')
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="CHSTH_Application_{application.application_number}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Header
    header = Paragraph("COLLEGE OF HEALTH SCIENCES AND TECHNOLOGY HADEJIA", styles['Title'])
    story.append(header)
    story.append(Spacer(1, 12))
    
    subheader = Paragraph("ADMISSION APPLICATION FORM", styles['Heading1'])
    story.append(subheader)
    story.append(Spacer(1, 12))
    
    # Application Number
    app_num = Paragraph(f"<b>Application Number:</b> {application.application_number}", styles['Normal'])
    story.append(app_num)
    story.append(Spacer(1, 12))
    
    # Personal Information
    personal_data = [
        ['<b>SECTION A: PERSONAL INFORMATION</b>', ''],
        ['First Name:', application.first_name],
        ['Surname:', application.surname],
        ['Other Name:', application.other_name or 'N/A'],
        ['Date of Birth:', str(application.date_of_birth)],
        ['Phone:', application.phone],
        ['Email:', application.email],
        ['Address:', application.address],
        ['LGA:', application.lga],
        ['State of Origin:', application.state_of_origin],
    ]
    
    personal_table = Table(personal_data, colWidths=[2.5*inch, 4*inch])
    personal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(personal_table)
    story.append(Spacer(1, 12))
    
    # Guardian Information
    guardian_data = [
        ['<b>GUARDIAN/NEXT OF KIN INFORMATION</b>', ''],
        ['Full Name:', application.guardian_name],
        ['Phone:', application.guardian_phone],
        ['Address:', application.guardian_address],
        ['Relationship:', application.guardian_relationship],
    ]
    
    guardian_table = Table(guardian_data, colWidths=[2.5*inch, 4*inch])
    guardian_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(guardian_table)
    story.append(Spacer(1, 12))
    
    # Course Selection
    course_data = [
        ['<b>SECTION D: COURSE SELECTION</b>', ''],
        ['First Choice:', application.get_first_choice_display()],
        ['Second Choice:', application.get_second_choice_display()],
    ]
    
    course_table = Table(course_data, colWidths=[2.5*inch, 4*inch])
    course_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(course_table)
    story.append(Spacer(1, 12))
    
    # Declaration
    if application.declaration_text:
        declaration_header = Paragraph("<b>SECTION E: DECLARATION</b>", styles['Heading2'])
        story.append(declaration_header)
        story.append(Spacer(1, 6))
        
        declaration_text = Paragraph(application.declaration_text, styles['Normal'])
        story.append(declaration_text)
        story.append(Spacer(1, 12))
    
    # Footer
    footer = Paragraph("This is a computer-generated document.", styles['Normal'])
    story.append(footer)
    
    doc.build(story)
    return response

def about(request):
    """About page"""
    return render(request, 'admission/about.html')

def contact(request):
    """Contact page"""
    return render(request, 'admission/contact.html')

def courses(request):
    """Courses page"""
    return render(request, 'admission/courses.html')