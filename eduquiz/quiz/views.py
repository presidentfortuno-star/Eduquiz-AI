from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.db.models import Avg
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
    return render(request, 'quiz/home.html')


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
    quizzes = Quiz.objects.filter(user=request.user).order_by('-created_at')
    attempts = QuizAttempt.objects.filter(user=request.user)

    if request.method == 'POST':
        upload_form = DocumentUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            document = upload_form.save(commit=False)
            document.user = request.user
            document.extracted_text = extract_pdf_text(document.file)
            document.summary = summarize_text(document.extracted_text)
            document.keywords = ', '.join(extract_keywords(document.extracted_text, limit=8))
            document.save()
            messages.success(request, 'PDF chargé avec succès. Le texte a été extrait et analysé.')
            return redirect('quiz:dashboard')
    else:
        upload_form = DocumentUploadForm()

    progress = {
        'attempts_count': attempts.count(),
        'average_score': round(attempts.aggregate(avg=Avg('score'))['avg'] or 0, 1),
        'quizzes_count': quizzes.count(),
    }

    return render(
        request,
        'quiz/dashboard.html',
        {
            'documents': documents,
            'quizzes': quizzes,
            'upload_form': upload_form,
            'progress': progress,
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
def create_quiz(request, document_id):
    document = get_object_or_404(Document, pk=document_id, user=request.user)

    if request.method == 'POST':
        form = QuizCreateForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.user = request.user
            quiz.document = document
            quiz.question_count = int(form.cleaned_data['question_count'])
            quiz.save()

            questions = generate_quiz_questions(
                document.extracted_text,
                count=quiz.question_count,
                level=quiz.level,
                mode='smart',
            )
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

            messages.success(request, 'Quiz généré avec succès.')
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
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, user=request.user)
    questions = quiz.questions.all()

    if request.method == 'POST':
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=request.user,
            started_at=timezone.now(),
            max_score=questions.count(),
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
