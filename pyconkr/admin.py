from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.flatpages.models import FlatPage
from django.db import models
from django_summernote.admin import SummernoteModelAdmin
from django_summernote.widgets import SummernoteWidget
from modeltranslation.admin import TranslationAdmin
from sorl.thumbnail.admin import AdminImageMixin
from .models import (Room, Program, ProgramTime, ProgramDate, ProgramCategory,
                     Speaker, Sponsor, SponsorLevel,
                     Profile, Announcement, EmailToken, Proposal, Banner)


class RoomAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'name',)
    list_editable = ('name',)
    search_fields = ('name',)
admin.site.register(Room, RoomAdmin)


class ProgramDateAdmin(admin.ModelAdmin):
    list_display = ('id', 'day',)
admin.site.register(ProgramDate, ProgramDateAdmin)


class ProgramTimeAdmin(TranslationAdmin):
    list_display = ('id', 'name', 'begin', 'end',)
    list_editable = ('name',)
    ordering = ('begin',)
admin.site.register(ProgramTime, ProgramTimeAdmin)


class ProgramCategoryAdmin(TranslationAdmin):
    list_display = ('id', 'name', 'slug',)
    list_editable = ('name', 'slug',)
admin.site.register(ProgramCategory, ProgramCategoryAdmin)


class SponsorAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'slug', 'name',)
    ordering = ('name',)
    list_editable = ('slug', 'name',)
    search_fields = ('name',)
admin.site.register(Sponsor, SponsorAdmin)


class SponsorLevelAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'order', 'name', 'slug',)
    list_editable = ('order', 'name', 'slug',)
    ordering = ('order',)
    search_fields = ('name',)
admin.site.register(SponsorLevel, SponsorLevelAdmin)


class SpeakerAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'slug', 'name', 'email',)
    list_editable = ('slug', 'name', 'email',)
    ordering = ('name',)
    search_fields = ('name', 'slug', 'email',)
admin.site.register(Speaker, SpeakerAdmin)


class ProgramAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'name', 'date', 'room', 'get_speakers', 'category', 'is_recordable',)
    list_editable = ('name', 'category', 'is_recordable',)
    ordering = ('id',)
    filter_horizontal = ('times', )
    search_fields = ('name', 'speakers__name', 'desc',)
admin.site.register(Program, ProgramAdmin)


class AnnouncementAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'title', 'created', 'modified')
    ordering = ('id',)
    search_fields = ('title',)
admin.site.register(Announcement, AnnouncementAdmin)


class EmailTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'token', 'created')
    search_fields = ('email',)
admin.site.register(EmailToken, EmailTokenAdmin)


class SummernoteWidgetWithCustomToolbar(SummernoteWidget):
    def template_contexts(self):
        contexts = super(SummernoteWidgetWithCustomToolbar, self).template_contexts()
        contexts['width'] = '960px'
        contexts['toolbar'] = [
            ['style', ['style', 'bold', 'italic', 'underline', 'clear']],
            ['para', ['ul', 'ol', 'height']],
            ['insert', ['link', 'hr', 'picture', 'video']],
            ['misc', ['fullscreen', 'codeview']],
        ]
        return contexts


class FlatPageAdmin(TranslationAdmin):
    formfield_overrides = {models.TextField: {'widget': SummernoteWidgetWithCustomToolbar}}


admin.site.unregister(FlatPage)
admin.site.register(FlatPage, FlatPageAdmin)


class ProfileInline(AdminImageMixin, admin.StackedInline):
    model = Profile
    can_delete = False


class ProposalAdminForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = '__all__'
        widgets = {
            'desc': SummernoteWidgetWithCustomToolbar(),
            'comment': SummernoteWidgetWithCustomToolbar(),
        }


class ProposalAdmin(admin.ModelAdmin):
    form = ProposalAdminForm
    list_display = ('user', 'title', 'difficulty', 'duration', 'language')
admin.site.register(Proposal, ProposalAdmin)


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline, )

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class BannerAdmin(SummernoteModelAdmin, TranslationAdmin):
    list_display = ('id', 'name', 'url', 'begin', 'end')
    ordering = ('id',)
    search_fields = ('name', 'url')
admin.site.register(Banner, BannerAdmin)
