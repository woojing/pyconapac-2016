# -*- coding: utf-8 -*-
import logging
from django.conf import settings
from django.contrib.auth import login as user_login, logout as user_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.flatpages.models import FlatPage
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from datetime import datetime, timedelta
from uuid import uuid4
from .forms import EmailLoginForm, SpeakerForm, ProgramForm, ProposalForm, ProfileForm
from .helper import sendEmailToken, render_json, render_io_error
from .models import (Room,
                     Program, ProgramDate, ProgramTime, ProgramCategory,
                     Speaker, Sponsor, Announcement,
                     EmailToken, Profile, Proposal)
from registration.models import Registration
from iamporter import get_access_token, Iamporter, IamporterError

logger = logging.getLogger(__name__)
payment_logger = logging.getLogger('payment')


def index(request):
    return render(request, 'index.html', {
        'base_content': FlatPage.objects.get(url='/index/').content,
        'recent_announcements': Announcement.objects.all()[:3],
    })


def schedule(request):
    dates = ProgramDate.objects.all()
    times = ProgramTime.objects.all()
    rooms = Room.objects.all()

    wide = {}
    narrow = {}
    processed = set()
    for d in dates:
        wide[d] = {}
        narrow[d] = {}
        for t in times:
            wide[d][t] = {}
            narrow[d][t] = {}
            for r in rooms:
                s = Program.objects.filter(date=d, times=t, rooms=r)
                if s:
                    if s[0].times.all()[0] == t and s[0].id not in processed:
                        wide[d][t][r] = s[0]
                        narrow[d][t][r] = s[0]
                        processed.add(s[0].id)
                else:
                    wide[d][t][r] = None

            if len(narrow[d][t]) == 0:
                del(narrow[d][t])

    contexts = {
        'wide': wide,
        'narrow': narrow,
        'rooms': rooms,
    }
    return render(request, 'schedule.html', contexts)


class RoomDetail(DetailView):
    model = Room


class SponsorList(ListView):
    model = Sponsor


class SponsorDetail(DetailView):
    model = Sponsor


class SpeakerList(ListView):
    model = Speaker


class SpeakerDetail(DetailView):
    model = Speaker

    def get_context_data(self, **kwargs):
        context = super(SpeakerDetail, self).get_context_data(**kwargs)

        if self.request.user.is_authenticated():
            if self.request.user.email == self.object.email:
                context['editable'] = True

        return context


class SpeakerUpdate(UpdateView):
    model = Speaker
    form_class = SpeakerForm

    def get_queryset(self):
        queryset = super(SpeakerUpdate, self).get_queryset()
        return queryset.filter(email=self.request.user.email)


class ProgramList(ListView):
    model = ProgramCategory
    template_name = "pyconkr/program_list.html"


class ProgramDetail(DetailView):
    model = Program

    def get_context_data(self, **kwargs):
        context = super(ProgramDetail, self).get_context_data(**kwargs)

        if self.request.user.is_authenticated():
            for speaker in self.object.speakers.all():
                if self.request.user.email == speaker.email:
                    context['editable'] = True

        return context


class ProgramUpdate(UpdateView):
    model = Program
    form_class = ProgramForm

    def get_queryset(self):
        queryset = super(ProgramUpdate, self).get_queryset()
        return queryset.filter(speakers__email=self.request.user.email)


class AnnouncementList(ListView):
    model = Announcement

    def get_queryset(self):
        now = datetime.now()
        queryset = super(AnnouncementList, self).get_queryset()
        return queryset.filter(Q(announce_after__isnull=True) | Q(announce_after__lt=now))


class AnnouncementDetail(DetailView):
    model = Announcement


def robots(request):
    return render(request, 'robots.txt', content_type='text/plain')


def login(request):
    if request.user.is_authenticated():
        return redirect('profile')

    form = EmailLoginForm()

    if request.method == 'POST':
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            # Remove previous tokens
            email = form.cleaned_data['email']
            EmailToken.objects.filter(email=email).delete()

            # Create new
            token = EmailToken(email=email)
            token.save()

            sendEmailToken(request, token)
            return redirect(reverse('login_mailsent'))

    return render(request, 'login.html', {
        'form': form,
        'title': _('Login'),
    })


@never_cache
def login_req(request, token):
    time_threshold = datetime.now() - timedelta(hours=1)

    try:
        token = EmailToken.objects.get(token=token,
                                       created__gte=time_threshold)
    except ObjectDoesNotExist:
        return render(request, 'login_notvalidtoken.html',
                      {'title': _('Not valid token')})
    email = token.email

    # Create user automatically by email as id, token as password
    try:
        user = User.objects.get(email=email)
    except ObjectDoesNotExist:
        user = User.objects.create_user(email, email, token)
        user.save()

    token.delete()

    # Set backend manually
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    user_login(request, user)

    return redirect(reverse('index'))


@never_cache
def login_mailsent(request):
    return render(request, 'login_mailsent.html', {
        'title': _('Mail sent'),
    })


def logout(request):
    user_logout(request)
    return redirect(reverse('index'))


class ProfileDetail(DetailView):
    model = Profile

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.profile.name:
            return redirect('profile_edit')
        return super(ProfileDetail, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return get_object_or_404(Profile, pk=self.request.user.profile.pk)

    def get_context_data(self, **kwargs):
        context = super(ProfileDetail, self).get_context_data(**kwargs)

        if self.request.user.is_authenticated():
            if self.request.user == self.object.user:
                context['editable'] = True
        is_registered = Registration.objects.filter(
            user=self.request.user,
            payment_status__in=['paid', 'ready']
        ).exists()
        has_proposal = Proposal.objects.filter(user=self.request.user).exists()
        context['is_registered'] = is_registered
        context['has_proposal'] = has_proposal
        context['title'] = _("Profile")
        return context


class ProfileUpdate(SuccessMessageMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    success_message = _("Profile successfully updated.")

    def get_queryset(self):
        queryset = super(ProfileUpdate, self).get_queryset()
        return queryset.filter(user=self.request.user)

    def get_object(self, queryset=None):
        return get_object_or_404(Profile, pk=self.request.user.profile.pk)

    def get_context_data(self, **kwargs):
        context = super(ProfileUpdate, self).get_context_data(**kwargs)
        context['title'] = _("Update profile")
        return context


class ProposalDetail(DetailView):
    def get_object(self, queryset=None):
        return get_object_or_404(Proposal, pk=self.request.user.proposal.pk)

    def dispatch(self, request, *args, **kwargs):
        if not Proposal.objects.filter(user=request.user).exists():
            return redirect('propose')
        return super(ProposalDetail, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProposalDetail, self).get_context_data(**kwargs)
        context['title'] = _("Proposal")
        return context


class ProposalUpdate(SuccessMessageMixin, UpdateView):
    model = Proposal
    form_class = ProposalForm
    success_message = _("Proposal successfully updated.")

    def get_object(self, queryset=None):
        return get_object_or_404(Proposal, pk=self.request.user.proposal.pk)

    def get_context_data(self, **kwargs):
        context = super(ProposalUpdate, self).get_context_data(**kwargs)
        context['title'] = _("Proposal")
        return context

    def get_success_url(self):
        return reverse('proposal')


class ProposalCreate(SuccessMessageMixin, CreateView):
    form_class = ProposalForm
    template_name = "pyconkr/proposal_form.html"
    success_message = _("Proposal successfully created.")

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.save()
        return super(ProposalCreate, self).form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if Proposal.objects.filter(user=request.user).exists():
            return redirect('proposal')
        return super(ProposalCreate, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('proposal')


