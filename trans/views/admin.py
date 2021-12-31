from collections import defaultdict

import os
import requests
from django.contrib.auth.decorators import permission_required
from django.http.response import HttpResponseBadRequest

from django.core.files import File
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls.base import reverse
from django.views.generic import View
from django.conf import settings

from django.http import HttpResponseNotFound
from trans.forms import UploadFileForm

from trans.models import User, Task, Translation, Contest, UserContest, Country
from trans.utils import is_translate_in_editing, unleash_edit_token
from trans.utils.pdf import build_final_pdf, send_pdf_to_printer
from trans.utils.translation import get_trans_by_user_and_task



class AdminCheckMixin(LoginRequiredMixin,object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(AdminCheckMixin, self).dispatch(request, *args, **kwargs)


class StaffCheckMixin(LoginRequiredMixin, object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser or user.groups.filter(name="staff").exists()

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(StaffCheckMixin, self).dispatch(request, *args, **kwargs)


class ISCEditorCheckMixin(LoginRequiredMixin, object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser or user.groups.filter(name="editor").exists()

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(ISCEditorCheckMixin, self).dispatch(request, *args, **kwargs)


class StaffRequiredMixin(LoginRequiredMixin, object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser or user.is_staff

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(StaffRequiredMixin, self).dispatch(request, *args, **kwargs)


class UserTranslations(StaffCheckMixin, View):
    def get(self, request, username):
        user = User.objects.get(username=username)
        # tasks = Task.objects.filter(contest__public=True).values_list('id', 'title')
        translations = []
        for task in Task.objects.filter(contest__public=True):
            translation = Translation.objects.filter(user=user, task=task).first()
            is_editing = translation and is_translate_in_editing(translation)
            if translation:
                translations.append((task.id, task.name, True, translation.id, translation.frozen, is_editing))
            else:
                translations.append((task.id, task.name, False, 'None', False, False))
        tasks_by_contest = {contest: [] for contest in Contest.objects.all()}
        for task in Task.objects.filter(contest__public=True, contest__frozen=False).order_by('order'):
            translation = Translation.objects.filter(user=user, task=task).first()
            is_editing = translation and is_translate_in_editing(translation)
            frozen = translation and translation.frozen
            translation_id = translation.id if translation else None
            final_pdf_url = translation.final_pdf.url if translation and translation.final_pdf else None
            tasks_by_contest[task.contest].append(
                {'id': task.id, 'name': task.name, 'trans_id': translation_id, 'is_editing': is_editing,
                 'frozen': frozen, 'final_pdf_url': final_pdf_url})
        tasks_lists = [{'title': c.title, 'slug': c.slug, 'id': c.id,
                        'user_contest': UserContest.objects.filter(contest=c, user=user).first(),
                        'tasks': tasks_by_contest[c]} for c in
                       Contest.objects.order_by('-order') if
                       len(tasks_by_contest[c]) > 0]
        can_upload_final_pdf = request.user.has_perm('trans.change_translation')
        form = UploadFileForm()
        return render(request, 'user.html', context={'user_name': username, 'country': user.country.name,
                                                    'is_editor': user.is_editor,
                                                     'tasks_lists': tasks_lists, 'language': user.credentials(),
                                                     'can_upload_final_pdf': can_upload_final_pdf, 'form': form})


class UsersList(StaffCheckMixin, View):
    def _fetch_users(self):
        users = list((User.get_translators() | User.objects.filter(username='ISC')).\
            distinct().values('country', 'language', 'username', 'num_of_contestants'))
        for user in users:
            user['country_name'] = Country.objects.get(code=user['country']).name
        return users

    def _fetch_translations(self, usernames):
        contests = []
        contest_tasks = defaultdict(list)
        for task in Task.objects.filter(contest__public=True, contest__frozen=False).order_by('-contest__order', 'order'):
            contest = task.contest
            contest_tasks[contest.id].append(task)

            if not contests or contests[-1]['id'] != contest.id:
                contests.append({
                    'title': contest.title,
                    'slug': contest.slug,
                    'id': contest.id,
                })
        # Django template doesn't play well with defaultdicts.
        contest_tasks = dict(contest_tasks)

        user_translations = {username: {} for username in usernames}
        for translation in Translation.objects.filter(task__contest__public=True, task__contest__frozen=False):
            user = translation.user
            task = translation.task
            # Task.name is unique, so translation does not need to be keyed by contest.
            if user.username not in user_translations:
                continue
            user_translations[user.username][task.name] = {
                'id': translation.id,
                'is_editing': is_translate_in_editing(translation),
                'frozen': translation.frozen,
                'final_pdf_url': translation.final_pdf.url if translation.final_pdf else None,
                'translating': translation.translating
            }

        user_contests = {username: {} for username in usernames}
        for user_contest in UserContest.objects.filter(contest__public=True, contest__frozen=False):
            user = user_contest.user
            contest = user_contest.contest
            if user.username not in user_contests or not contest:
                continue
            user_contests[user.username][contest.id] = {
                'frozen': user_contest.frozen,
                'note': user_contest.note,
            }

        return (contests, contest_tasks, user_translations, user_contests)

    def get(self, request):
        users = self._fetch_users()
        (contests, contest_tasks, user_translations, user_contests) = \
            self._fetch_translations([user['username'] for user in users])

        return render(request, 'users.html', context={
            'users': users,
            'contests': contests,
            'contest_tasks': contest_tasks,
            'user_translations': user_translations,
            'user_contests': user_contests,
        })


class AddFinalPDF(StaffCheckMixin, View):
    # @permission_required('trans.change_translation')
    def post(self, request):
        id = request.POST['trans_id']
        trans = Translation.objects.filter(id=id).first()
        form = UploadFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponseBadRequest("You should attach a file")

        pdf_file = request.FILES.get('uploaded_file', None)
        if not pdf_file or pdf_file.name.split('.')[-1] != 'pdf':
            return HttpResponseBadRequest("You should attach a pdf file")

        trans.frozen = True
        trans.final_pdf = pdf_file
        trans.save()
#        trans.notify_final_pdf_change()
        return redirect(request.META.get('HTTP_REFERER'))


class FreezeTranslationView(View):
    def _freeze_translation(self, username, task_name, frozen):
        user = User.objects.filter(username=username).first()
        if user is None:
            return HttpResponseNotFound('No such user')

        task = Task.objects.filter(name=task_name).first()
        if task is None:
            return HttpResponseNotFound('No such task')

        trans = get_trans_by_user_and_task(user, task)

        trans.frozen = frozen
        if frozen:
            pdf_path = build_final_pdf(trans)
            with open(pdf_path, 'rb') as f:
                trans.final_pdf = File(f)
                trans.save()
        else:
            trans.final_pdf.delete()
            trans.save()


class UserFreezeTranslation(LoginRequiredMixin, FreezeTranslationView):
    def post(self, request, task_name):
        frozen = request.POST['freeze'] == 'True'
        self._freeze_translation(request.user.username, task_name, frozen)

        # trans.notify_final_pdf_change()
        # return redirect(to=reverse('user_trans', kwargs={'username' : trans.user.username}))
        return redirect(request.META.get('HTTP_REFERER'))


class StaffFreezeTranslation(StaffCheckMixin, FreezeTranslationView):
    def post(self, request, username, task_name):
        frozen = request.POST['freeze'] == 'True'
        self._freeze_translation(username, task_name, frozen)

        # trans.notify_final_pdf_change()
        # return redirect(to=reverse('user_trans', kwargs={'username' : trans.user.username}))
        return redirect(request.META.get('HTTP_REFERER'))


class FreezeUserContest(LoginRequiredMixin, View):
    def post(self, request, username, contest_id):
        note = request.POST.get('note', '')
        user = User.objects.get(username=username)
        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return HttpResponseNotFound("There is no contest")
        user_contest, created = UserContest.objects.get_or_create(contest=contest, user=user)
        user_contest.frozen = True
        user_contest.note = note
        user_contest.save()
        for task in contest.task_set.all():
            get_trans_by_user_and_task(user, task)
#        return redirect(to=reverse('user_trans', kwargs={'username': username}))
        return redirect(request.META.get('HTTP_REFERER'))


class UnfreezeUserContest(LoginRequiredMixin, View):
    def post(self, request, username, contest_id):
        user = User.objects.get(username=username)
        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return HttpResponseNotFound("There is no contest")
        UserContest.objects.filter(contest=contest, user=user).delete()
#        return redirect(to=reverse('user_trans', kwargs={'username': username}))
        return redirect(request.META.get('HTTP_REFERER'))

class UnleashEditTranslationToken(StaffCheckMixin, View):
    def post(self, request, id):
        trans = Translation.objects.get(id=id)
        if trans is None:
            return HttpResponseNotFound("There is no task")
        unleash_edit_token(trans)
        return redirect(to=reverse('user_trans', kwargs={'username': trans.user.username}))

# ADDED by Emil Abbasov, IOI2019

class StaffExtraPrint(StaffCheckMixin, View):
    def post(self, request, pdf_file_path, username, extra_name):
        user = User.objects.get(username=username)
       
        send_pdf_to_printer(pdf_file_path, user.country.code, user.country.name, settings.FINAL_PRINTER, user.num_of_contestants)

        # For Monitor udpates:
        try:
            response = requests.get('{}/extra/done?countrycode={}&extra={}'.format(settings.MONITOR_ADDRESS, user.country.code, extra_name))
        except Exception as e:
            print(type(e))

        return redirect(request.META.get('HTTP_REFERER'))
