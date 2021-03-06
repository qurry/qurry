import json
import jwt
import time
import secrets

from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.mail import send_mail
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode


from questions.views import extract_errors
from qurry_api import settings
from qurry_api.base import AuthenticatedView, active_user_existence_required

from .forms import UserCreationForm
from .models import User, ActivationToken


# aux func
def activation_token_for(user):
    return ActivationToken.objects.create(user=user).token


def is_token_valid(user, token):
    try:
        ActivationToken.objects.get(user=user.id, token=token).delete()
    except ActivationToken.DoesNotExist:
        return False
    return True


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            mail_subject = 'Activate your account.'
            message = render_to_string('email_template.html', {
                'user': user,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': activation_token_for(user),
                'domain': get_current_site(request),
            })
            to_email = form.cleaned_data.get('email')
            send_mail(mail_subject, message, settings.EMAIL_HOST_USER, [to_email], html_message=message)

            return JsonResponse({}, status=201)
        else:
            response_json = {'errors': {}}
            for field, errors in form.errors.items():
                response_json['errors'][field] = ' '.join(errors)

            return JsonResponse(response_json, status=409)

    return JsonResponse({'message': 'request is not post'}, status=400)


def login(request):
    if request.method == 'POST':

        try:
            body = json.loads(request.body.decode('utf-8'))
            email = body['email']
            password = body['password']

            if not email or not password:
                raise ValueError

            user = User.objects.get(email=email)
            if not user.check_password(password):
                raise PermissionDenied()

        except ValueError:
            return JsonResponse({'errors': ['request must contain email and password as strings']}, status=400)

        except (User.DoesNotExist, PermissionDenied):
            return JsonResponse({'errors': ['This user does not exist, has not confirmed their email or the password is invalid.']}, status=400)

        token = jwt.encode({
            "token_type": "access",
            "exp": int(time.time()) + settings.JWT_VALIDITY_PERIOD,
            "jti": secrets.token_urlsafe(15),
            "user_id": str(user.id),
        }, settings.SECRET_KEY, algorithm="HS256").decode('ascii')

        return JsonResponse({'access': token})

    return JsonResponse({'errors': ['only post method is allowed']}, status=405)


def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and is_token_valid(user, token):
        user.is_active = True
        user.save()
        return redirect('/register/success')
    else:
        return redirect('/register/invalid')


class UserView(AuthenticatedView):
    Model = User
    mode = None

    @active_user_existence_required
    def get(self, *_, **kwargs):
        if self.mode == 'profile':
            return self.profile()

        if 'id' in kwargs:
            user = User.objects.get(id=kwargs['id'])
            return JsonResponse(user.as_detailed())

        return JsonResponse(list(user.as_detailed() for user in User.objects.all_active()), safe=False)

    def patch(self, request, *_, **__):
        if self.mode != 'profile':
            return JsonResponse({'errors': ['if you need to edit your profile, PATCH to profile/']}, status=405)
        try:
            self.change(**json.loads(request.body.decode('utf-8') or '{}'))
        except ValidationError as exc:
            return JsonResponse({'errors': extract_errors(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({'errors': [str(exc)]}, status=400)

        return JsonResponse({'userId': self.user.id})

    def profile(self):
        return JsonResponse({**self.user.as_detailed(), **{
            'email': self.user.email,
            'registeredAt': timezone.localtime(self.user.registered_at)
        }})

    def change(self, **kwargs):
        if 'username' in kwargs:
            self.user.username = kwargs['username']

        if 'password' in kwargs:
            self.user.set_password(kwargs['password'])

        self.user.full_clean()
        self.user.save()
