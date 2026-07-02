from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import DocumentUploadForm, QuizCreateForm, UserRegistrationForm
from .models import Answer, Document, Quiz, QuizAttempt, QuizQuestion
from .utils import (
    extract_pdf_text,
    extract_keywords,
    generate_quiz_questions,
    summarize_text,
)


def home(request):
    if request.user.is_authenticated:
        return redirect('quiz:dashboard')

    public_stats = {
        'total_users': User.objects.count(),
        'total_quizzes': Quiz.objects.count(),
        'total_attempts': QuizAttempt.objects.count(),
        'average_score': round(QuizAttempt.objects.aggregate(avg=Avg('score'))['avg'] or 0, 1),
    }
    return render(request, 'quiz/home.html', {'public_stats': public_stats})


def register(request):
    if request.user.is_authenticated:
        return redirect('quiz:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Bienvenue sur EduQuiz AI ! Votre compte est créé.')

            notification_recipient = getattr(settings, 'NOTIFICATION_EMAIL', None)
            if notification_recipient:
                subject = 'Nouvelle inscription EduQuiz'
                message = f"Un nouvel utilisateur vient de s'inscrire sur EduQuiz.\n\nNom d'utilisateur : {user.username}\nEmail : {user.email}"
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [notification_recipient], fail_silently=True)

            return redirect('quiz:dashboard')
    else:
        form = UserRegistrationForm()

    return render(request, 'quiz/register.html', {'form': form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect('quiz:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Connexion réussie.')
            return redirect('quiz:dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'quiz/login.html', {'form': form})


def user_logout(request):
    logout(request)
    messages.success(request, 'Vous êtes déconnecté.')
    return redirect('quiz:home')


@login_required
def dashboard(request):
    documents = Document.objects.filter(user=request.user).order_by('-uploaded_at')
    quizzes = (
        Quiz.objects.filter(user=request.user)
        .select_related('document')
        .order_by('-created_at')
    )
    attempts = QuizAttempt.objects.filter(user=request.user)
    completed_attempts = attempts.filter(completed_at__isnull=False)
    recent_attempts = completed_attempts.select_related('quiz').order_by('-completed_at')[:5]
    best_score = completed_attempts.aggregate(best=Max('score'))['best'] or 0

    total_seconds = 0
    duration_count = 0
    for attempt in completed_attempts:
        if attempt.started_at and attempt.completed_at:
            total_seconds += (attempt.completed_at - attempt.started_at).total_seconds()
            duration_count += 1
    average_duration_seconds = int(total_seconds / duration_count) if duration_count else 0
    average_duration = (
        f"{average_duration_seconds // 60}m {average_duration_seconds % 60}s"
        if duration_count else '—'
    )

    quizzes = (
        Quiz.objects.filter(user=request.user)
        .select_related('document')
        .prefetch_related('attempts')
        .order_by('-created_at')
    )

    quiz_rankings = []
    for quiz in quizzes:
        quiz_attempts = quiz.attempts.filter(completed_at__isnull=False)
        if not quiz_attempts.exists():
            continue
        best_quiz_score = quiz_attempts.aggregate(best=Max('score'))['best'] or 0
        avg_quiz_score = round(quiz_attempts.aggregate(avg=Avg('score'))['avg'] or 0, 1)
        last_attempt = quiz_attempts.order_by('-completed_at').first()
        quiz_rankings.append({
            'title': quiz.title,
            'best_score': best_quiz_score,
            'avg_score': avg_quiz_score,
            'last_score': f"{last_attempt.score}/{last_attempt.max_score}" if last_attempt else '—',
            'last_date': last_attempt.completed_at if last_attempt else None,
            'quiz_id': quiz.id,
        })

    if request.method == 'POST':
        upload_form = DocumentUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            document = upload_form.save(commit=False)
            document.user = request.user
            document.extracted_text = extract_pdf_text(document.file)
            if not document.extracted_text or len(document.extracted_text) < 120:
                messages.error(
                    request,
                    "Impossible d'extraire un texte exploitable depuis ce PDF. Vérifie que le fichier est un PDF texte valide.",
                )
            else:
                document.summary = summarize_text(document.extracted_text)
                document.keywords = ', '.join(extract_keywords(document.extracted_text, limit=8))
                document.save()
                messages.success(
                    request,
                    'PDF chargé avec succès. Analyse intelligente terminée — vous pouvez créer un quiz.',
                )
                return redirect('quiz:dashboard')
    else:
        upload_form = DocumentUploadForm()

    progress = {
        'attempts_count': attempts.count(),
        'average_score': round(attempts.aggregate(avg=Avg('score'))['avg'] or 0, 1),
        'quizzes_count': quizzes.count(),
    }

    global_stats = {
        'total_users': User.objects.count(),
        'active_sessions': Session.objects.filter(expire_date__gt=timezone.now()).count(),
        'total_documents': Document.objects.count(),
        'total_quizzes': Quiz.objects.count(),
    }

    return render(
        request,
        'quiz/dashboard.html',
        {
            'documents': documents,
            'quizzes': quizzes,
            'upload_form': upload_form,
            'progress': progress,
            'recent_attempts': recent_attempts,
            'best_score': best_score,
            'average_duration': average_duration,
            'quiz_rankings': quiz_rankings,
            'global_stats': global_stats,
        },
    )


@login_required
def review_errors(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id, user=request.user)
    wrong_answers = attempt.answers.filter(is_correct=False).select_related('question')
    review_data = None

    if request.method == 'POST':
        corrected = 0
        feedback_lines = []
        for wrong in wrong_answers:
            question = wrong.question
            selected_option = request.POST.get(f'question_{question.id}')
            is_correct = selected_option == question.correct_option
            if is_correct:
                corrected += 1
            chosen_text = dict(question.all_options()).get(selected_option, 'Aucune réponse') if selected_option else 'Aucune réponse'
            feedback_lines.append(
                f'Question : {question.text}\nVotre réponse : {chosen_text}\n'
                f'Bonne réponse : {question.correct_text()}\n{question.explanation}\n'
            )

        review_data = {
            'corrected': corrected,
            'max_score': wrong_answers.count(),
            'feedback': '\n'.join(feedback_lines),
        }

    return render(
        request,
        'quiz/review.html',
        {
            'attempt': attempt,
            'wrong_answers': wrong_answers,
            'review_data': review_data,
        },
    )


@login_required
@transaction.atomic
def create_quiz(request, document_id):
    document = get_object_or_404(Document, pk=document_id, user=request.user)

    if request.method == 'POST':
        form = QuizCreateForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.user = request.user
            quiz.document = document
            quiz.title = f'Quiz : {document.title}'
            quiz.question_count = int(form.cleaned_data['question_count'])
            quiz.save()

            questions = generate_quiz_questions(
                document.extracted_text,
                count=quiz.question_count,
                level=quiz.level,
                mode='smart',
            )
            if not questions:
                quiz.delete()
                messages.error(
                    request,
                    'Impossible de générer le quiz. Vérifiez que le PDF contient assez de texte.',
                )
                return redirect('quiz:create_quiz', document_id=document.id)

            for q in questions:
                QuizQuestion.objects.create(
                    quiz=quiz,
                    text=q['text'],
                    option_a=q['options'][0],
                    option_b=q['options'][1],
                    option_c=q['options'][2],
                    option_d=q['options'][3],
                    correct_option=q['correct'],
                    explanation=q['explanation'],
                )

            messages.success(
                request,
                f'Quiz généré avec succès ({len(questions)} questions). Bonne révision !',
            )
            return redirect('quiz:take_quiz', quiz_id=quiz.id)
    else:
        form = QuizCreateForm()

    return render(
        request,
        'quiz/create_quiz.html',
        {
            'document': document,
            'form': form,
        },
    )


@login_required
@transaction.atomic
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    questions = list(quiz.questions.all())

    if request.method == 'POST':
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=request.user,
            started_at=timezone.now(),
            max_score=len(questions),
        )
        score = 0
        feedback_lines = []

        for question in questions:
            selected_option = request.POST.get(f'question_{question.id}')
            is_correct = selected_option == question.correct_option
            if is_correct:
                score += 1
            answer = Answer.objects.create(
                attempt=attempt,
                question=question,
                selected_option=selected_option or '',
                is_correct=is_correct,
            )
            chosen_text = answer.selected_text() if selected_option else 'Aucune réponse'
            feedback_lines.append(
                f'Question : {question.text}\nVotre réponse : {chosen_text}\n'
                f'Bonne réponse : {question.correct_text()}\n{question.explanation}\n'
            )

        attempt.score = score
        attempt.completed_at = timezone.now()
        attempt.feedback = '\n'.join(feedback_lines)
        attempt.save()

        return redirect('quiz:results', attempt_id=attempt.id)

    return render(
        request,
        'quiz/take_quiz.html',
        {
            'quiz': quiz,
            'questions': questions,
        },
    )


@login_required
def results(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id, user=request.user)
    return render(request, 'quiz/results.html', {'attempt': attempt})
