import io
import random
import re
from collections import Counter
from PyPDF2 import PdfReader

FRENCH_STOPWORDS = {
    'et', 'la', 'le', 'les', 'des', 'un', 'une', 'de', 'du', 'dans', 'pour', 'sur',
    'avec', 'sans', 'est', 'sont', 'qui', 'que', 'par', 'au', 'aux', 'ce', 'cet',
    'cette', 'ces', 'ceci', 'cela', 'ça', 'se', 'sa', 'son', 'ses', 'en', 'comme',
    'ou', 'où', 'a', 'il', 'elle', 'nous', 'vous', 'ils', 'elles', 'on', 'leur',
    'lui', 'eux', 'celui', 'celle', 'ceux', 'ci', 'ça', 'mais', 'donc', 'or', 'ni',
    'car', 'si', 'non', 'plus', 'moins', 'très', 'tout', 'tous', 'être', 'avoir',
    'faire', 'peut', 'entre', 'avant', 'après', 'pendant', 'sous', 'parmi', 'fait',
    'été', 'aussi', 'nouveau', 'nouvelle',
}
GENERIC_TERM_HEADS = {
    'système', 'secteur', 'service', 'partie', 'processus', 'fonction', 'élément',
    'éléments', 'domaine', 'approche', 'aspect', 'méthode', 'groupe', 'ensemble',
    'état', 'mécanisme', 'structure', 'exercice', 'organisation', 'organisationnel',
}
WEAK_KEYWORDS = {
    'obligatoire', 'proche', 'couramment', 'souvent', 'responsable', 'garantir',
    'assurer', 'obtenir', 'organiser', 'appelée', 'appelé', 'appelées', 'appelés',
    'servir', 'utilisé', 'utilisée', 'utilisées', 'utilisés', 'sécurisation', 'sécurité',
    'titre', 'title', 'document', 'page', 'content', 'balise', 'balises', 'doctype',
    'language', 'langage', 'première', 'premiere', 'générale', 'generale', 'section',
    'permet', 'analyse', 'théorie', 'concept', 'principe', 'message', 'texte',
    'suivant', 'vidéo', 'video', 'simulation', 'cette', 'chaque', 'celui', 'celle',
}
ENGLISH_STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was', 'were', 'will',
    'can', 'not', 'have', 'has', 'had', 'but', 'you', 'your', 'their', 'them', 'they',
    'what', 'which', 'when', 'where', 'how', 'why', 'all', 'any', 'one', 'two', 'three',
}


def extract_pdf_text(uploaded_file):
    uploaded_file.seek(0)
    try:
        reader = PdfReader(uploaded_file)
        pages = [page.extract_text() or '' for page in reader.pages]
        raw_text = '\n'.join(pages)
    except Exception:
        uploaded_file.seek(0)
        content = uploaded_file.read()
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or '' for page in reader.pages]
        raw_text = '\n'.join(pages)
    return _clean_extracted_pdf_text(raw_text)


def _clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def _is_noise_pdf_line(line):
    low = line.lower()
    if len(re.findall(r'[a-zà-ÿ]', low)) < 5:
        return True
    if re.search(r'table des matières|table des matieres|table of contents|sommaire|tableau des matières|tableau des matieres', low):
        return True
    if re.search(r'^(page|page\s*\d+)$', low):
        return True
    if re.search(r'\b(equipe pédagogique|equipe pedagogique|uvci|version\s*\d|201\d|202\d|copyright|©|@)\b', low):
        return True
    if re.search(r'\b(objectifs?|introduction|contenu|annexe|références|references|bibliographie|index|sommaire)\b.*\d+$', low):
        return True
    if re.match(r'^[0-9\.\-\sivxlcdm]+$', low):
        return True
    if re.search(r'\b(Leçon|Lecon|Chapitre|Section|Titre|Annexe|Partie)\b', line) and ':' in line and len(line.split()) < 15:
        return True
    if re.search(r'\bI{1,3}\b\s*[-–]\s*\w+', line) and re.search(r'\d{1,3}', line):
        return True
    if len(re.findall(r'\d+', line)) >= 3 and len(line.split()) < 20:
        return True
    return False


def _clean_extracted_pdf_text(text):
    text = text.replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned = []
    for line in lines:
        if _is_noise_pdf_line(line):
            continue
        if re.search(r'\d+\s*$|\s+\d+\s*$', line) and len(line.split()) < 8:
            continue
        if re.match(r'^(?:[IVXLCDM]+\.)?\s*\d+[\.)]?\s*.+$', line):
            continue
        cleaned.append(line)
    return ' '.join(cleaned)


def _is_noise_text_segment(text):
    low = text.lower()
    if re.search(r'table des matières|table des matieres|table of contents|sommaire|tableau des matières|tableau des matieres|source\s*:\s*wiki(?:pedia|pé|pédia)|travaux pratique|objectif(?:s)?|index|annexe|bibliographie|lien hypertexte', low):
        return True
    if re.search(r'^(page|page\s*\d+|page:\s*\d+)\b', low):
        return True
    if len(re.findall(r'\d+', text)) >= 3 and len(text.split()) < 20:
        return True
    if re.search(r'\b(Leçon|Lecon|Chapitre|Section|Titre|Annexe|Partie)\b', text) and ':' in text and len(text.split()) < 15:
        return True
    if _is_noise_pdf_line(text):
        return True
    return False


def _normalize_term(term):
    term = term.strip()
    term = re.sub(r"^(?:le|la|les|l'|un|une|des|du|de)\s+", '', term, flags=re.IGNORECASE)
    term = re.sub(r"^['\"“”«»]+|['\"“”«»]+$", '', term).strip()
    return term.lower()


def _display_term(term):
    term = term.strip()
    term = re.sub(r"^(?:le|la|les|l'|un|une|des|du|de)\s+", '', term, flags=re.IGNORECASE)
    term = re.sub(r"^['\"“”«»]+|['\"“”«»]+$", '', term).strip()
    return term


def _is_generic_definition_term(term):
    normalized = _normalize_term(term)
    tokens = [w.lower() for w in re.findall(r"[\wÀ-ÿ']+", normalized) if w]
    if not tokens:
        return True
    if tokens[0] in {'ce', 'cet', 'cette', 'ces', 'ceci', 'cela'} and len(tokens) > 1:
        return tokens[1] in GENERIC_TERM_HEADS
    return any(token in GENERIC_TERM_HEADS and len(tokens) <= 4 for token in tokens)


def _is_valid_term(term):
    if _is_generic_definition_term(term):
        return False
    normalized = _normalize_term(term)
    if any(char.isdigit() for char in normalized):
        return False
    tokens = [w.lower() for w in re.findall(r"[\wÀ-ÿ']+", normalized) if w]
    tokens = [w for w in tokens if w not in FRENCH_STOPWORDS and w not in ENGLISH_STOPWORDS]
    if len(tokens) == 0 or len(tokens) > 8:
        return False
    if len(tokens) == 1 and len(tokens[0]) <= 4:
        return False
    if any(token in WEAK_KEYWORDS for token in tokens):
        return False
    if sum(1 for token in tokens if token in GENERIC_TERM_HEADS) > 0 and len(tokens) <= 5:
        return False
    return any(len(w) > 3 for w in tokens)


DEFINITION_INVALID_STARTS = {
    'très proche de', 'le plus souvent', 'plus souvent', 'souvent', 'couramment', 'fréquemment',
    'utilisé pour', 'utilisé par', 'peut être utilisé', 'permet de', 'lié à',
    'liée à', 'concerne', 'est basé sur', 'est nécessaire pour', 'sert à', 'est très',
}


def _is_valid_definition(definition):
    normalized = definition.strip().lower()
    if not normalized or len(normalized) < 15:
        return False
    if normalized.startswith('est '):
        return False
    if any(normalized.startswith(prefix) for prefix in DEFINITION_INVALID_STARTS):
        return False
    if 'proche de' in normalized and normalized.startswith('très'):  # weak comparative phrasing
        return False
    if normalized.count(' ') < 2:
        return False
    return True


def _find_definition_candidates(text):
    text = text.replace('\n', ' ')
    patterns = [
        r'(?:^|[\.\?!]\s*)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_\-\'’ ]{2,79}?)\s+est\s+(?:un|une|le|la|l\'|des|du|de la|de l\'|aux?)\s+([^\.\?!]{15,120})',
        r'(?:^|[\.\?!]\s*)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_\-\'’ ]{2,79}?)\s+signifie\s+([^\.\?!]{15,120})',
    ]
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            term = _clean_text(match.group(1))
            definition = _clean_text(match.group(2)).rstrip(' .;')
            if len(term) > 2 and len(definition) > 10 and _is_valid_term(term) and _is_valid_definition(definition):
                candidates.append((term, definition))
    return candidates


def _clean_keyword(word):
    return re.sub(r"[^A-Za-zÀ-ÿ0-9\-']", '', word).strip().lower()


def extract_keywords(text, limit=20):
    words = re.findall(r"\b[\wÀ-ÿ']{4,}\b", text.lower())
    filtered = []
    for word in words:
        clean_word = _clean_keyword(word)
        if not clean_word:
            continue
        normalized_word = _normalize_term(clean_word)
        if not normalized_word:
            continue
        if normalized_word in FRENCH_STOPWORDS or normalized_word in ENGLISH_STOPWORDS or normalized_word.isdigit():
            continue
        if normalized_word in WEAK_KEYWORDS or normalized_word in GENERIC_TERM_HEADS:
            continue
        if any(char.isdigit() for char in normalized_word):
            continue
        filtered.append(normalized_word)

    counts = Counter(filtered)
    repeated = [word for word, count in counts.most_common() if count > 1]
    if repeated:
        return repeated[:limit]
    return [word for word, _ in counts.most_common(limit)]


def _is_valid_keyword(keyword):
    normalized = _normalize_term(keyword)
    if len(normalized) <= 3:
        return False
    if normalized in FRENCH_STOPWORDS or normalized in ENGLISH_STOPWORDS or normalized in WEAK_KEYWORDS:
        return False
    tokens = [w for w in re.findall(r"[\wÀ-ÿ']+", normalized) if w]
    if any(token in WEAK_KEYWORDS or token in GENERIC_TERM_HEADS for token in tokens):
        return False
    if any(token.endswith('ment') for token in tokens):
        return False
    if len(tokens) == 1:
        return len(tokens[0]) > 4
    return True


def _question_hash(text, options, correct):
    normalized_options = [opt.strip().lower() for opt in options]
    normalized_options.sort()
    return f"{text.strip().lower()}|{'|'.join(normalized_options)}|{correct}"


def _is_html_course(text):
    low = text.lower()
    html_signals = ['<html', '<body', '<head', '<title', 'doctype', 'balise', 'balises', 'html', 'body>', 'href', '<a', '<img', 'css', 'html5']
    count = sum(1 for s in html_signals if s in low)
    return count >= 2


def _generate_html_quiz(text, count=10, level='easy'):
    # A set of canonical HTML questions useful for introductory courses
    pool = [
        {
            'text': 'Qui est le concepteur du langage HTML ?',
            'options': ['Microsoft', 'Tim Berners-Lee', 'Netscape', 'Le W3C'],
            'correct': 'b',
            'explanation': "Tim Berners-Lee a créé le HTML.",
        },
        {
            'text': "Que signifie l'acronyme HTML ?",
            'options': ['Hyper Technology Mixed Language', 'HyperText Markup Language', 'Hot Text Mapping Language', 'Hyper Tool Machine Language'],
            'correct': 'b',
            'explanation': 'HTML = HyperText Markup Language.',
        },
        {
            'text': 'Dans une page HTML, la balise <body> sert à :',
            'options': ["Définir l'en-tête du document", 'Définir le corps du document', 'Définir le titre du document', 'Ajouter des commentaires'],
            'correct': 'b',
            'explanation': 'La balise <body> contient le corps visible de la page.',
        },
        {
            'text': "Quelle est la règle absolue concernant l'imbrication des balises HTML ?",
            'options': ['La première balise ouverte est la dernière fermée', 'Les balises peuvent rester ouvertes indéfiniment', 'Les balises doivent être écrites en majuscules', 'Les balises doivent toujours être auto-fermantes'],
            'correct': 'a',
            'explanation': "Les balises doivent être correctement imbriquées (LIFO).",
        },
        {
            'text': "La balise <title> permet d'afficher le texte dans :",
            'options': ['Le corps de la page', "La barre de titre ou l'onglet du navigateur", 'La barre d\'état du navigateur', 'Le pied de page du document'],
            'correct': 'b',
            'explanation': "La balise <title> définit le titre affiché dans l'onglet du navigateur.",
        },
    ]

    questions = []
    for i, q in enumerate(pool):
        if len(questions) >= count:
            break
        questions.append(q)

    # If need more, generate simple keyword questions from text but filtered
    if len(questions) < count:
        keywords = extract_keywords(text, limit=30)
        added = set()
        for kw in keywords:
            if len(questions) >= count:
                break
            if not _is_valid_keyword(kw):
                continue
            if kw in added:
                continue
            distractors = _keyword_distractors(kw, keywords)
            prompt = _keyword_prompt(level, len(questions))
            questions.append(_build_keyword_question(kw, distractors, prompt, level))
            added.add(kw)

    return questions[:count]


def _keyword_distractors(correct, keywords):
    distractors = [k for k in keywords if k != correct]
    random.shuffle(distractors)
    result = []
    for keyword in distractors:
        if len(result) >= 3:
            break
        normalized = _normalize_term(keyword)
        if normalized == _normalize_term(correct) or _normalize_term(correct) in normalized or normalized in _normalize_term(correct):
            continue
        if not _is_valid_keyword(keyword):
            continue
        result.append(keyword)
    fallback = ['analyse', 'théorie', 'concept']
    idx = 0
    while len(result) < 3:
        candidate = fallback[idx % len(fallback)]
        if candidate != correct and candidate not in result:
            result.append(candidate)
        idx += 1
    return result


def summarize_text(text, sentence_count=4):
    text = _clean_text(text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) <= sentence_count:
        return text

    keywords = extract_keywords(text, limit=15)
    scored = []
    for index, sentence in enumerate(sentences):
        score = sum(1 for keyword in keywords if keyword in sentence.lower())
        scored.append((score, index, sentence))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(scored[:sentence_count], key=lambda item: item[1])
    return ' '.join([sentence for _, _, sentence in selected]).strip()


def _build_question(term, definition, distractors, level='easy'):
    wrong_options = list(distractors)
    random.shuffle(wrong_options)
    options = [definition] + wrong_options[:3]
    random.shuffle(options)
    correct_index = options.index(definition)
    labels = ['a', 'b', 'c', 'd']
    if level == 'easy':
        prompt = f'Que signifie « {term} » dans ce cours ?'
    elif level == 'medium':
        prompt = f'Parmi les choix suivants, quelle définition correspond le mieux à « {term} » ?'
    else:
        prompt = f'Dans le contexte du cours, « {term} » désigne :'
    return {
        'text': prompt,
        'options': options,
        'correct': labels[correct_index],
        'explanation': f'« {term} » correspond à : {definition}.',
    }


def _keyword_prompt(level='easy', index=0):
    easy_templates = [
        'Quel mot-clé est lié au contenu du cours ?',
        'Quel terme parmi la liste est important pour ce cours ?',
        'Lequel de ces mots reflète le mieux le sujet étudié ?'
    ]
    medium_templates = [
        'Parmi ces termes, lequel est le plus pertinent pour le cours ?',
        'Quel mot illustre le mieux le thème du texte ?',
        'Lequel de ces mots est le plus lié au contenu ?'
    ]
    hard_templates = [
        'Quel terme incarne le concept principal du cours ?',
        'Lequel de ces mots est le plus central dans cette leçon ?',
        'Quel terme représente le mieux les notions abordées ?'
    ]
    if level == 'medium':
        return medium_templates[index % len(medium_templates)]
    if level == 'hard':
        return hard_templates[index % len(hard_templates)]
    return easy_templates[index % len(easy_templates)]


def _build_keyword_question(keyword, distractors, prompt, level='easy'):
    wrong_options = list(distractors)
    random.shuffle(wrong_options)
    options = [keyword] + wrong_options[:3]
    random.shuffle(options)
    labels = ['a', 'b', 'c', 'd']
    return {
        'text': prompt,
        'options': options,
        'correct': labels[options.index(keyword)],
        'explanation': f'Le mot-clé correct est « {keyword} », qui apparaît dans le cours.',
    }


def _build_true_false_question(statement, is_true=True):
    options = ['Vrai', 'Faux']
    correct = 'a' if is_true else 'b'
    return {
        'text': f'Vrai ou faux : {statement}',
        'options': options + ['Pas sûr', 'Aucun des deux'],
        'correct': correct,
        'explanation': 'La phrase est ' + ('vraie.' if is_true else 'fausse.'),
    }


def generate_quiz_questions(text, count=10, level='easy', mode='default'):
    text = _clean_text(text)
    # If the course is clearly about HTML, generate targeted HTML questions first
    if _is_html_course(text):
        return _generate_html_quiz(text, count, level)
    # Mode 'smart' force un générateur plus intelligent quel que soit le PDF
    if mode == 'smart':
        return _generate_smart_quiz(text, count, level)
    # Evaluate quality: if too low, return an actionable single-item result
    score, reasons = assess_text_quality(text)
    if score < 0.45 and mode != 'force':
        prompt = "Le texte fourni semble insuffisant pour générer des questions de qualité. Souhaitez-vous : (1) téléverser plus de contenu, (2) activer le mode 'smart' ou (3) demander une validation manuelle ?"
        options = ["Téléverser plus de contenu", "Activer mode 'smart'", "Demander validation manuelle", "Générer quand même"]
        return [{
            'text': prompt,
            'options': options,
            'correct': 'd',
            'explanation': 'Score qualité faible: ' + ', '.join(reasons)
        }]
    definitions = _find_definition_candidates(text)
    questions = []
    used_terms = set()
    keywords = extract_keywords(text, limit=30)

    question_texts = set()
    for term, definition in definitions:
        if len(questions) >= count:
            break
        display_term = _display_term(term)
        if not _is_valid_term(display_term):
            continue
        normalized_term = _normalize_term(display_term)
        if normalized_term in used_terms:
            continue
        used_terms.add(normalized_term)
        distractors = [d for _, d in definitions if d != definition]
        unique_distractors = []
        for item in distractors:
            if item not in unique_distractors and item.lower() != definition.lower():
                unique_distractors.append(item)
        distractors = unique_distractors
        if len(distractors) < 3:
            distractors.extend([x for x in keywords if x.lower() != definition.lower()])
        distractors = [d for i, d in enumerate(distractors) if d not in distractors[:i]]
        if len(distractors) < 3:
            distractors.extend(['Une expression', 'Un concept', 'Une notion'])
        question_data = _build_question(display_term, definition, distractors, level)
        question_key = _question_hash(question_data['text'], question_data['options'], question_data['correct'])
        if question_key in question_texts:
            continue
        question_texts.add(question_key)
        questions.append(question_data)

    if len(questions) < count:
        remaining_keywords = [k for k in keywords if _is_valid_keyword(k)]
        used_keywords = set()
        for keyword in remaining_keywords:
            if len(questions) >= count:
                break
            normalized_keyword = _normalize_term(keyword)
            if normalized_keyword in used_keywords or normalized_keyword in used_terms:
                continue
            used_keywords.add(normalized_keyword)
            used_terms.add(normalized_keyword)
            distractors = _keyword_distractors(keyword, keywords)
            prompt = _keyword_prompt(level, len(questions))
            question_data = _build_keyword_question(keyword, distractors, prompt, level)
            question_key = _question_hash(question_data['text'], question_data['options'], question_data['correct'])
            if question_key in question_texts:
                continue
            question_texts.add(question_key)
            questions.append(question_data)

    if len(questions) < count:
        fallback_keywords = [k for k in keywords if k not in used_terms and _is_valid_keyword(k)]
        for keyword in fallback_keywords:
            if len(questions) >= count:
                break
            distractors = _keyword_distractors(keyword, keywords)
            question_data = _build_keyword_question(keyword, distractors, _keyword_prompt(level, len(questions)), level)
            question_key = _question_hash(question_data['text'], question_data['options'], question_data['correct'])
            if question_key in question_texts:
                continue
            question_texts.add(question_key)
            questions.append(question_data)

    if len(questions) < count:
        default_terms = ['structure', 'balise', 'formulaire', 'connexion', 'algorithme', 'machine']
        for default in default_terms:
            if len(questions) >= count:
                break
            distractors = _keyword_distractors(default, default_terms)
            questions.append(_build_keyword_question(default, distractors, _keyword_prompt(level, len(questions)), level))

    return questions[:count]


def _generate_smart_quiz(text, count=10, level='easy'):
    text = _clean_text(text)
    # Use FULL TEXT, not summary - critical for quality
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    sentences = [s for s in sentences if not _is_noise_text_segment(s) and len(s.split()) >= 8]
    keywords = extract_keywords(text, limit=50)
    questions = []
    used_answers = set()

    def sentence_score(sentence):
        score = 0
        score += min(5, len(sentence.split()) // 5)
        score += sum(1 for kw in keywords if kw in sentence.lower())
        if re.search(r'\b(est|sont|signifie|désigne|consiste|comprend|permet|fonctionne|utilise)\b', sentence, flags=re.IGNORECASE):
            score += 2
        if len(re.findall(r'[A-ZÀ-Ÿ]', sentence)) < 2:
            score -= 1
        return score

    sentences.sort(key=lambda s: (-sentence_score(s), -len(s)))

    # Extract definitions from full text with multiple patterns
    for s in sentences:
        if len(questions) >= count:
            break
        m = re.search(r"([A-ZÀ-Ÿ][A-Za-zÀ-ÿ0-9_''\- ]{2,80}?)\s+(?:ne\s+)?(?:est|sont|désigne|designent|signifie|consiste|correspond à|permet de|permet|comprend|utilise|utilisent)\s+([^\.\?!]{15,200})", s, flags=re.IGNORECASE)
        if m:
            term = _display_term(m.group(1))
            definition = _clean_text(m.group(2)).rstrip(' .;')
            if _is_valid_term(term) and _is_valid_definition(definition):
                distractors = [k for k in keywords if k.lower() != definition.lower()][:10]
                distractors = [d for d in distractors if _is_valid_keyword(d)][:3]
                while len(distractors) < 3:
                    distractors.append('Une notion')
                questions.append(_build_question(term, definition, distractors, level))
                used_answers.add(_normalize_term(term))

    # Generate some true/false statements from good sentences
    for s in sentences:
        if len(questions) >= count:
            break
        if len(questions) >= count or len(questions) >= 3:
            break
        m = re.search(r"([A-ZÀ-Ÿ][A-Za-zÀ-ÿ0-9_''\- ]{3,80}?)\s+(?:est|sont|signifie|désigne|consiste|comprend|permet|utilise)\s+([^\.\?!]{15,120})", s, flags=re.IGNORECASE)
        if m and len(s.split()) > 10:
            if not _is_noise_text_segment(s):
                questions.append(_build_true_false_question(s, True))

    # Then create cloze / keyword questions from top sentences
    for s in sentences:
        if len(questions) >= count:
            break
        if _is_noise_text_segment(s):
            continue
        if len(s.split()) < 10:
            continue
        candidates = []
        for token in re.findall(r"[\wÀ-ÿ'’\-]{4,}", s):
            if token.lower() in FRENCH_STOPWORDS or token.lower() in ENGLISH_STOPWORDS:
                continue
            if not _is_valid_keyword(token):
                continue
            norm = _normalize_term(token)
            if norm in used_answers:
                continue
            candidates.append((token, norm))
        if not candidates:
            continue
        candidates.sort(key=lambda item: (-len(item[0]), item[1] in keywords, item[0].lower()))
        answer, norm = candidates[0]
        if not re.search(re.escape(answer), s, flags=re.IGNORECASE):
            continue
        used_answers.add(norm)
        prompt = f"Complétez la phrase : {re.sub(re.escape(answer), '_____', s, count=1, flags=re.IGNORECASE)}"
        distractors = _keyword_distractors(answer, keywords)
        questions.append(_build_keyword_question(answer, distractors, prompt, level))

    # If still short, fall back to keyword questions (filtered)
    if len(questions) < count:
        remaining = [k for k in keywords if _is_valid_keyword(k) and _normalize_term(k) not in used_answers]
        for kw in remaining:
            if len(questions) >= count:
                break
            distractors = _keyword_distractors(kw, keywords)
            prompt = _keyword_prompt(level, len(questions))
            questions.append(_build_keyword_question(kw, distractors, prompt, level))

    return questions[:count]


def assess_text_quality(text):
    """Return (score, reasons list). Score 0..1. Reasons are short strings."""
    t = _clean_text(text)
    reasons = []
    length = len(t)
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', t) if s.strip()]
    sentence_count = len(sentences)
    definitions = _find_definition_candidates(t)
    keywords = extract_keywords(t, limit=40)

    # length score
    len_score = min(1.0, length / 3000.0)
    if length < 500:
        reasons.append('texte court')
    # sentence variety
    sent_score = min(1.0, sentence_count / 8.0)
    if sentence_count < 4:
        reasons.append('peu de phrases')
    # definition presence
    def_score = min(1.0, len(definitions) / 3.0)
    if len(definitions) == 0:
        reasons.append('aucune définition détectée')
    # keyword richness
    kw_score = min(1.0, len(keywords) / 10.0)
    if len(keywords) < 6:
        reasons.append('peu de mots-clés significatifs')

    # weighted average
    score = (0.4 * len_score) + (0.2 * sent_score) + (0.2 * def_score) + (0.2 * kw_score)
    # normalize reasons (unique)
    reasons = list(dict.fromkeys(reasons))
    return score, reasons
