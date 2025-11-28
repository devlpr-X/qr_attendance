import os
import json
import textwrap
import PyPDF2
import docx
import requests

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.db import connection, transaction
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..utils import _is_admin, set_cookie_safe, get_cookie_safe

DOCUMENTS_MEDIA_SUBDIR = 'documents'
MAX_CONTEXT_CHARS = 2000  # chars from a doc to include in prompt


@require_http_methods(["GET"])
def api_docs_list(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, filename, file_path, description, mime_type, uploaded_at
                FROM document
                ORDER BY uploaded_at DESC
                LIMIT 500
            """)
            rows = cursor.fetchall()

        docs = []
        for r in rows:
            doc_id, name, filename, file_path, desc, mime, uploaded = r
            url = f"{settings.MEDIA_URL}{DOCUMENTS_MEDIA_SUBDIR}/{filename}" if filename else ""
            docs.append({
                'id': doc_id,
                'name': name,
                'filename': filename,
                'url': url,
                'description': desc or '',
                'mime': mime or 'application/pdf',
                'uploaded_at': uploaded.isoformat() if uploaded else ''
            })

        return JsonResponse(docs, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def document_upload(request):
    if not _is_admin(request):
        return redirect('index')

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        file = request.FILES.get('file')

        if not name or not file:
            response = redirect('document_upload')
            set_cookie_safe(response, 'flash_msg', 'Нэр болон файл шаардлагатай', 6)
            set_cookie_safe(response, 'flash_status', 400, 6)
            return response

        upload_dir = os.path.join(settings.MEDIA_ROOT, DOCUMENTS_MEDIA_SUBDIR)
        os.makedirs(upload_dir, exist_ok=True)

        # sanitize filename minimally
        filename = os.path.basename(file.name)
        file_path = os.path.join(upload_dir, filename)
        i = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(file_path):
            filename = f"{base}_{i}{ext}"
            file_path = os.path.join(upload_dir, filename)
            i += 1

        with open(file_path, 'wb+') as dst:
            for chunk in file.chunks():
                dst.write(chunk)

        mime_type = file.content_type or 'application/octet-stream'
        extracted_text = ''
        try:
            if filename.lower().endswith('.pdf'):
                extracted_text = extract_pdf_text(file_path)
            elif filename.lower().endswith('.docx'):
                extracted_text = extract_docx_text(file_path)
        except Exception as e:
            extracted_text = f'[Text extraction failed: {str(e)}]'

        try:
            user_id = get_cookie_safe(request, 'user_id')
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO document
                        (name, filename, file_path, description, mime_type, uploaded_by_id, extracted_text, uploaded_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                        RETURNING id
                    """, [name, filename, file_path, description, mime_type, user_id, extracted_text])
                    doc_id = cursor.fetchone()[0]

            response = redirect('index')
            set_cookie_safe(response, 'flash_msg', 'Файл амжилттай нэмэгдлээ', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            response = redirect('document_upload')
            set_cookie_safe(response, 'flash_msg', f'Алдаа: {str(e)}', 6)
            set_cookie_safe(response, 'flash_status', 500, 6)
            return response

    return render(request, 'admin/documents/upload.html', {})


def extract_pdf_text(file_path):
    text = ''
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text() or ''
            text += page_text + '\n'
    return text.strip()


def extract_docx_text(file_path):
    text = ''
    doc = docx.Document(file_path)
    for p in doc.paragraphs:
        text += p.text + '\n'
    return text.strip()


@csrf_exempt
@require_http_methods(["POST"])
def api_chat(request):
    try:
        payload = json.loads(request.body)
        question = (payload.get('question') or '').strip()
        if not question:
            return JsonResponse({'error': 'Асуулт хоосон байна'}, status=400)

        # load candidate docs (recent)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, extracted_text, description
                FROM document
                WHERE extracted_text IS NOT NULL
                ORDER BY uploaded_at DESC
                LIMIT 50
            """)
            cand = cursor.fetchall()

        # naive ranking by token occurrences
        q_lower = question.lower()
        tokens = [t for t in q_lower.split() if len(t) > 1]
        scored = []
        for doc_id, name, txt, desc in cand:
            text_to_search = ' '.join(filter(None, [name or '', desc or '', txt or ''])).lower()
            score = 0
            for t in tokens:
                score += text_to_search.count(t)
            if score > 0:
                scored.append((score, doc_id, name, (txt or ''), (desc or '')))

        scored.sort(reverse=True, key=lambda x: x[0])
        top_docs = scored[:3]

        context = ''
        sources = []
        for idx, t in enumerate(top_docs, start=1):
            _, doc_id, name, txt, desc = t
            snippet = (txt or desc or '')[:MAX_CONTEXT_CHARS]
            context += f"Баримт {idx}: {name}\n{snippet}\n\n"
            sources.append({'id': doc_id, 'name': name})

        prompt = textwrap.dedent(f"""
            Та бол сургуулийн мэдээллийн туслах. Хариултыг монгол хэл дээр товч, ойлгомжтой, хамгийн ихдээ 400 үгэнд өгнө үү.

            Эдгээр баримтууд (хэрвээ байгаа бол) эх сурвалж болно:
            {context}

            Асуулт: {question}

            Хэрвээ баримтад хариулт байхгүй бол: "Уучлаарай, энэ мэдээлэл одоогоор байхгүй байна." гэж хариулна уу.
        """)

        # Try Ollama via helper (utils.ollama_client)
        answer = None
        try:
            from ..utils.ollama_client import ollama_generate
            resp = ollama_generate(prompt, model=getattr(settings, 'ollama3.2', ), )
            if resp and resp.strip():
                answer = resp.strip()
        except Exception:
            answer = None

        # fallback: basic retrieval summary
        if not answer:
            answer = simple_fallback_answer(question, top_docs)
            if not answer:
                answer = "Уучлаарай, энэ мэдээлэл одоогоор байхгүй байна."

        # optional: persist chat history
        try:
            from ..models.chat_store import append_chat
            append_chat({'question': question, 'answer': answer})
        except Exception:
            pass

        return JsonResponse({'answer': answer, 'sources': sources})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def simple_fallback_answer(question, top_docs):
    if not top_docs:
        return None
    _, doc_id, name, txt, desc = top_docs[0]
    snippet = (txt or desc or '')[:1000]
    # simple "first sentences" heuristic
    sentences = snippet.replace('\n', ' ').split('.')
    summary = '.'.join([s.strip() for s in sentences if s.strip()][:2])
    if summary:
        return f"Эх сурвалж: {name}\n\n{summary}."
    return None


def document_delete(request, doc_id):
    if not _is_admin(request):
        return redirect('index')

    if request.method == 'POST':
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT file_path FROM document WHERE id=%s", [doc_id])
                row = cursor.fetchone()
                if row and row[0]:
                    fp = row[0]
                    if os.path.exists(fp):
                        os.remove(fp)
                cursor.execute("DELETE FROM document WHERE id=%s", [doc_id])
            response = redirect('index')
            set_cookie_safe(response, 'flash_msg', 'Файл устгагдлаа', 6)
            set_cookie_safe(response, 'flash_status', 200, 6)
            return response
        except Exception as e:
            response = redirect('index')
            set_cookie_safe(response, 'flash_msg', f'Алдаа: {str(e)}', 6)
            set_cookie_safe(response, 'flash_status', 500, 6)
            return response

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM document WHERE id=%s", [doc_id])
        row = cursor.fetchone()
        if not row:
            return redirect('index')
        doc = {'id': row[0], 'name': row[1]}
    return render(request, 'admin/documents/delete_confirm.html', {'doc': doc})
