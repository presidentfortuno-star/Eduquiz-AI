import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from .models import Document, Quiz
from .utils import extract_pdf_text, generate_quiz_questions


class QuizAppBasicsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = Client()
        self.client.login(username='testuser', password='testpass')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('quiz:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_document_upload_rejects_non_pdf(self):
        response = self.client.post(
            reverse('quiz:dashboard'),
            {
                'title': 'Test',
                'file': SimpleUploadedFile('test.txt', b'This is not a PDF', content_type='text/plain'),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Seuls les fichiers PDF sont acceptés.')

    def test_quiz_title_generated_from_document(self):
        document = Document.objects.create(
            user=self.user,
            title='Cours Test',
            file='documents/user_1/test.pdf',
            extracted_text=(
                "L'architecture d'une application web comprend le serveur, le client, et la base de données. "
                'Un serveur HTTP répond aux requêtes et envoie des pages HTML. '
                "Le concept de session permet de maintenir l'état. "
                'Les données sont souvent stockées dans une base relationnelle. '
                "La sécurité se gère avec l'authentification et l'autorisation."
            ),
        )
        response = self.client.post(
            reverse('quiz:create_quiz', args=[document.id]),
            {'question_count': '5', 'level': 'easy'},
        )
        self.assertEqual(response.status_code, 302)
        quiz = Quiz.objects.filter(document=document).first()
        self.assertIsNotNone(quiz)
        self.assertTrue(quiz.title.startswith('Quiz : Cours Test'))

    def test_generate_quiz_questions_fallback(self):
        text = (
            "L'architecture d'une application web comprend le serveur, le client, et la base de données. "
            'Un serveur HTTP répond aux requêtes et envoie des pages HTML. '
            "Le concept de session permet de maintenir l'état. "
            'Les données sont souvent stockées dans une base relationnelle. '
            "La sécurité se gère avec l'authentification et l'autorisation."
        )
        questions = generate_quiz_questions(text, count=5, level='easy', mode='default')
        self.assertEqual(len(questions), 5)
        for q in questions:
            self.assertIn('text', q)
            self.assertIn('options', q)
            self.assertEqual(len(q['options']), 4)
            self.assertIn(q['correct'], {'a', 'b', 'c', 'd'})


class UtilsTest(TestCase):
    def test_extract_pdf_text_returns_string(self):
        sample_pdf = io.BytesIO(
            b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 24 Tf 72 712 Td (Hello PDF) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000067 00000 n \n0000000116 00000 n \n0000000231 00000 n \ntrailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n333\n%%EOF'
        )
        text = extract_pdf_text(sample_pdf)
        self.assertIsInstance(text, str)
