# -*- coding: utf-8 -*-

from django.shortcuts import get_object_or_404, render_to_response, redirect
from django.template import RequestContext
from django.core.context_processors import csrf
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.utils.encoding import smart_str
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseRedirect
from django.db import connections
from django.core.paginator import InvalidPage, EmptyPage, Paginator
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from mezzanine.forms.forms import FormForForm
from mezzanine.forms.signals import form_invalid, form_valid
from mezzanine.pages.page_processors import processor_for
from mezzanine.utils.email import split_addresses, send_mail_template
from mezzanine.utils.views import is_spam
from django.core.mail import send_mail
from .fields import EMAIL


from .models import Form, FormEntry, Payment

from polybanking import PolyBanking


def start_payment(request, pk):
    """Start payment for a form"""

    api = PolyBanking(settings.POLYBANKING_SERVER, settings.POLYBANKING_ID, settings.POLYBANKING_KEY_REQUEST, settings.POLYBANKING_KEY_IPN, settings.POLYBANKING_KEY_API)

    entry = get_object_or_404(FormEntry, pk=pk)

    if not entry.form.need_payment:
        raise Http404

    payment = entry.get_payment()

    error = ''

    url = api.new_transaction(str(entry.form.amount * 100), payment.reference())

    if not entry.form.can_start_payment():
        error = 'form_full'

    if payment.started:
        request.session["current_payment"] = payment.id
        return HttpResponseRedirect(payment.redirect_url)

    if payment.is_valid:
        error = 'payment_already_ok'

    if not error:
        error, url = api.new_transaction(str(entry.form.amount * 100), payment.reference())

    if error != 'OK':
        return render_to_response('forms/error.html', {'error': error}, context_instance=RequestContext(request))
    else:
        payment.redirect_url = url
        payment.started = True
        payment.save()
        request.session["current_payment"] = payment.id
        return HttpResponseRedirect(url)


@csrf_exempt
def ipn(request):

    api = PolyBanking(settings.POLYBANKING_SERVER, settings.POLYBANKING_ID, settings.POLYBANKING_KEY_REQUEST, settings.POLYBANKING_KEY_IPN, settings.POLYBANKING_KEY_API)

    ok, message, ref, status, status_ok, date = api.check_ipn(request.POST)

    if ok:

        payment = get_object_or_404(Payment, pk=ref.split('-')[-1])
        payment.is_valid = status_ok
        payment.save()

        entry = payment.entry

        subject = payment.entry.form.final_confirmation_subject

        context = {
            "message": payment.entry.form.final_confirmation_email,
        }

        email_from = payment.entry.form.email_from or settings.DEFAULT_FROM_EMAIL

        for field in payment.entry.form.fields.all():
            if field.field_type == EMAIL:
                email_to = payment.entry.fields.filter(field_id=field.id).first().value


        if email_to and payment.entry.form.send_email:
            send_mail_template(subject, "email/form_response_paid", email_from,
                               email_to, context)
        headers = None
        if email_to:
            # Add the email entered as a Reply-To header
            headers = {'Reply-To': email_to}
        email_copies = split_addresses(payment.entry.form.email_copies)
        if email_copies:
            send_mail_template(subject, "email/form_response_copies_paid",
                               email_from, email_copies, context, headers=headers)


    return HttpResponse('')


def result_ok(request):
    return render_to_response('forms/payment_ok.html', {'final_confirmation_message': Payment.objects.get(pk=request.session["current_payment"]).entry.form.final_confirmation_message}, context_instance=RequestContext(request))


def result_err(request):
    return render_to_response('forms/payment_error.html', {}, context_instance=RequestContext(request))
