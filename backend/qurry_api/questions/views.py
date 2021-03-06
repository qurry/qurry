import json

from django.core.exceptions import ValidationError, PermissionDenied, RequestAborted
from django.http import JsonResponse

from media.models import Document, Image, DocumentAttach, ImageAttach
from qurry_api.base import AuthenticatedView, ownership_required, object_existence_required
from .models import Question, Answer, Comment, Tag


DEFAULT_LIMIT = 20


def extract_errors(validation_exception):
    error_list = []
    error_dict = eval(str(validation_exception))
    for field in error_dict:
        for error in error_dict[field]:
            error_list.append('%s: %s' % (field, error))
    return error_list


def reference_files(files, attach_model, obj):
    attach_model().attaches_from(obj).clear()

    for file in files:
        attach_model().attaches_from(obj).add(attach_model(file=file), bulk=False)


class AbstractView(AuthenticatedView):
    Model = None

    # different HTTP requests
    @object_existence_required
    def get(self, request, *args, **kwargs):
        if 'id' in kwargs:
            obj = self.Model.objects.get(id=kwargs['id'])
            if 'vote' in request.GET:
                return self.vote(obj, request.GET['vote'])

            return self.view_detailed(obj)

        return self.view_list(**({**request.GET.dict(), ** kwargs}))

    def post(self, request, *args, **kwargs):
        try:
            # extract arguments from body and create element with these arguments
            id = self.create(json.loads(request.body.decode('utf-8') or '{}'))
            return JsonResponse({'%sId' % self.Model.__name__.lower(): str(id)}, status=201)
        except ValidationError as exc:
            return JsonResponse({'errors': extract_errors(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({'errors': self.handle(exc)}, status=400)

    @object_existence_required
    @ownership_required
    def patch(self, request, *args, **kwargs):
        if 'id' not in kwargs:
            return JsonResponse(
                {'errors': [
                    'you can not patch to %ss, you have to add id to the url' % self.Model.__name__]},
                status=405)
        obj = self.Model.objects.get(id=kwargs['id'])
        try:
            # extract arguments from body and change element with these arguments
            self.change(obj, json.loads(request.body.decode('utf-8') or '{}'))
            return JsonResponse({'%sId' % self.Model.__name__.lower(): str(kwargs['id'])}, status=200)
        except ValidationError as exc:
            return JsonResponse({'errors': extract_errors(exc)}, status=400)
        except PermissionDenied as exc:
            return JsonResponse({'errors': [str(exc)]}, status=401)
        except Exception as exc:
            return JsonResponse({'errors': self.handle(exc)}, status=400)

    @object_existence_required
    @ownership_required
    def delete(self, request, *args, **kwargs):
        if 'id' not in kwargs:
            return JsonResponse(
                {'errors': [
                    'you can not delete to %ss, you have to add id to the url' % self.Model.__name__]},
                status=405)
        obj = self.Model.objects.get(id=kwargs['id'])
        try:
            obj.delete()
            return JsonResponse({'%sId' % self.Model.__name__.lower(): str(kwargs['id'])}, status=200)
        except Exception as exc:
            return JsonResponse({'errors': [str(exc)]}, status=500)

    def view_list(self, **kwargs):  # in preview format
        pass

    def view_detailed(self, obj):
        pass

    def create(self, body):
        pass

    def change(self, obj, body):
        pass

    def vote(self, obj, action):
        if self.user == obj.user:
            return JsonResponse({'errors': ['you can not vote your own %s' % self.Model.__name__.lower()]}, status=400)
        # remove user from voters
        try:
            obj.vote_up_users.get(id=self.user.id)
            obj.vote_up_users.remove(self.user)
            obj.score_up(reverse=True)
        except:
            pass

        try:
            obj.vote_down_users.get(id=self.user.id)
            obj.vote_down_users.remove(self.user)
            obj.score_down(reverse=True)
        except:
            pass

        if action == '1':
            obj.vote_up_users.add(self.user)
            obj.score_up()
        if action == '-1':
            obj.vote_down_users.add(self.user)
            obj.score_down()

        return JsonResponse({'%sId' % self.Model.__name__.lower(): str(obj.id)})


class QuestionView(AbstractView):
    Model = Question

    def view_list(self, **kwargs):  # in preview format
        # parse arguments
        try:
            limit = abs(int(kwargs.get('limit', DEFAULT_LIMIT)))
            offset = abs(int(kwargs.get('offset', 0)))
            
            search_words = kwargs.get('search', '')
            if search_words != '':
                search_words = search_words.split(' ')
            else:
                search_words = []
            
            tag_id_list = kwargs.get('tags', '')
            filter_tags = Tag.objects.none()
            if tag_id_list != '':
                filter_tags = Tag.objects.filter(id__in=list(
                    int(id) for id in tag_id_list.split(',')))
        except:
            return JsonResponse({'errors': ['get arguments are invalid. be sure that limit and offset are integers and tagIds are seperated with a ´,´']}, status=400)

        questions = Question.objects.all().tag_filter(filter_tags).search(search_words)

        return JsonResponse(list(question.as_preview(self.user) for question in questions[offset: offset + limit]),
                            safe=False)

    def view_detailed(self, question):
        return JsonResponse(question.as_detailed(self.user))

    def create(self, body):
        tag_ids = list(int(tag_id) for tag_id in body['tagIds'])
        tags = Tag.objects.filter(id__in=tag_ids)

        image_ids = body['imageIds']
        images = Image.objects.filter(id__in=image_ids)

        document_ids = body['documentIds']
        documents = Document.objects.filter(id__in=document_ids)

        creation_data = {'title': body['title'],
                         'body': body['body'], 'user': self.user}

        new_question = Question(**creation_data)
        new_question.full_clean()
        new_question.save()

        new_question.tags.set(tags)
        reference_files(images, ImageAttach, new_question)
        reference_files(documents, DocumentAttach, new_question)
        return new_question.id

    def change(self, question, body):

        if 'title' in body:
            question.title = body['title']
        if 'body' in body:
            question.body = body['body']

        question.full_clean()
        question.save()

        if 'tagIds' in body:
            tag_ids = list(int(tag_id) for tag_id in body['tagIds'])
            tags = Tag.objects.filter(id__in=tag_ids)
            question.tags.set(tags)

        if 'imageIds' in body:
            image_ids = body['imageIds']
            images = Image.objects.filter(id__in=image_ids)
            # remove_files_from(question, Image)
            reference_files(images, ImageAttach, question)

        if 'documentIds' in body:
            document_ids = body['documentIds']
            documents = Document.objects.filter(id__in=document_ids)
            # remove_files_from(question, Document)
            reference_files(documents, DocumentAttach, question)

    def handle(self, bad_request_exception):
        # fields are not valid
        message_dict = {
            # one argument is not given
            KeyError: 'request must contain title, body, tagIds, imageIds and documentIds, even if they are blank.',
            # tagIds is not a list
            TypeError: 'tagIds, imageIds and documentIds should be a list of strings.',
        }
        return [message_dict.get(type(bad_request_exception), str(bad_request_exception))]


class AnswerView(AbstractView):
    Model = Answer
    question = None

    def setup(self, request, *args, **kwargs):
        if 'qid' in kwargs:
            try:
                self.question = Question.objects.get(id=kwargs['qid'])
            except:
                pass
        return super().setup(request, *args, **kwargs)

    def view_list(self, **kwargs):  # in preview format
        if self.question:
            return JsonResponse(list(answer.as_preview(self.user) for answer in self.question.answer_set.all()),
                                safe=False)
        return JsonResponse(list(answer.as_preview(self.user) for answer in Answer.objects.all()), safe=False)

    def view_detailed(self, answer):
        return JsonResponse(answer.as_detailed(self.user))

    def create(self, body):

        if not self.question:
            raise RequestAborted(
                'you can create an answer with questions/<id>/answers/')

        image_ids = body['imageIds']
        images = Image.objects.filter(id__in=image_ids)

        document_ids = body['documentIds']
        documents = Document.objects.filter(id__in=document_ids)

        creation_data = {
            'body': body['body'], 'user': self.user, 'question': self.question}

        new_answer = Answer(**creation_data)
        new_answer.full_clean()
        new_answer.save()

        reference_files(images, ImageAttach, new_answer)
        reference_files(documents, DocumentAttach, new_answer)

        return new_answer.id

    def change(self, answer, body):

        if 'body' in body:
            answer.body = body['body']

        answer.full_clean()
        answer.save()

    def handle(self, bad_request_exception):
        # fields are not valid

        message_dict = {
            # one argument is not given
            KeyError: 'request must contain body',
        }
        return [message_dict.get(type(bad_request_exception), str(bad_request_exception))]


class CommentView(AbstractView):
    Model = Comment
    reference = None

    def setup(self, request, *args, **kwargs):
        if 'qid' in kwargs:
            try:
                self.reference = Question.objects.get(id=kwargs['qid'])
            except:
                pass
        if 'aid' in kwargs:
            try:
                self.reference = Answer.objects.get(id=kwargs['aid'])
            except:
                pass
        return super().setup(request, *args, **kwargs)

    def view_list(self, **kwargs):  # in preview format
        if self.reference:
            return JsonResponse(list(comment.as_preview() for comment in self.reference.comments.all()), safe=False)
        return JsonResponse(list(comment.as_preview() for comment in Comment.objects.all()), safe=False)

    def view_detailed(self, comment):
        return JsonResponse(comment.as_detailed())

    def create(self, body):

        if not self.reference:
            raise RequestAborted(
                'you can create a comment with questions/<id>/comments/ or answers/<id>/comments')

        creation_data = {
            'body': body['body'], 'user': self.user, 'reference_object': self.reference}

        new_comment = Comment(**creation_data)
        new_comment.full_clean()
        new_comment.save()

        return new_comment.id

    def change(self, comment, body):

        if 'body' in body:
            comment.body = body['body']

        comment.full_clean()
        comment.save()

    def vote(self, answer, action):
        return JsonResponse({'error': ['you can not vote comments now']}, status=405)

    def handle(self, bad_request_exception):
        # fields are not valid

        message_dict = {
            # one argument is not given
            KeyError: 'request must contain body',
        }
        return [message_dict.get(type(bad_request_exception), str(bad_request_exception))]


class TagView(AuthenticatedView):

    def get(self, request, *args, **kwargs):
        return self.view_list()

    def view_list(self):
        return JsonResponse(Tag.all_as_preview(), safe=False)
